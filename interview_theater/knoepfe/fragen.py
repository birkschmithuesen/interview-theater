"""Phase 2: der Fragenvorschlag, der Ueberblick mit Richtungsfrage, die
Fragen einzeln durchgehen, und der Leitfaden.

Padua, 02.10.2026 (zweiter Umbau nach dem vom 06.09.2026): der Bot schlaegt
fuenf Fragen je Begriff vor und prueft sie **im selben Modellzug** auf
sensible Themen (``VORSCHLAG FRAGENAUSWAHL:`` + optional
``VORSCHLAG FRAGEN WEICH:``). Darunter steht ein Ueberblick mit einer
deterministischen Richtungsfrage ("Gehen die Fragen in die richtige
Richtung? Wollen wir sie einzeln durchgehen?"); "Ja" fuehrt **Frage fuer
Frage** durch die Liste (Annehmen / Verwerfen / Schaerfen), "Andere
Richtung" fragt zuerst nach der Richtung und stoesst dann einen neuen
Vorschlag an. Eine freie Nachricht waehrend eine Frage die aktuelle ist,
zaehlt immer als Schaerfungswunsch fuer genau diese Frage -- ohne
Knopfdruck und ohne Erkenner-Lauf (``nimm_offene_frage_text``).

Die Nummernwahl aus dem ersten Umbau (``lies_fragennummern``) und ihre
Knoepfe (``ART_FRAGE_WAHL``, ``ART_FRAGEN_UEBERNEHMEN``, ``ART_FRAGEN_EIGENE``)
sind damit Geschichte. Ihre Handler bleiben in ``wirkung.py`` stehen, damit
ein Druck aus einer schon verschickten alten Nachricht nicht ins Leere
laeuft -- angeboten werden sie nicht mehr.
"""

from interview_theater import anweisungen, erkenner, leitfaden, repo

from interview_theater.knoepfe.texte import (
    ART_FRAGE_ANNEHMEN, ART_FRAGE_SCHAERFEN, ART_FRAGE_VERWERFEN,
    ART_FRAGEN_ANDERE, ART_FRAGEN_EINZELN, ART_FRAGEN_WEICH_LASSEN,
    ART_FRAGEN_WEICH_UEBERNEHMEN, ART_LEITFADEN, T,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _nimm_alte_leiste_ab, _sende_knoepfe,
    _starte_auftrag, sende_notiert_nur_undo,
)


# --- Die vorgeschlagene Liste und ihr Zustand ------------------------------


def _auswahlfragen(conn, chat_id: int) -> list[str]:
    """Die zuletzt vorgeschlagenen Fragen, eine je Zeile ("Begriff: Frage")."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_auswahl"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    from interview_theater import vorschlag

    return vorschlag.zeilen(roh)


def _setze_frage_zeile(conn, chat_id: int, nummer: int, neuer_text: str) -> None:
    """Ersetzt genau eine Zeile der vorgeschlagenen Liste -- fuer "Schaerfen",
    das nie die ganze Liste neu schreibt."""
    zeilen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(zeilen):
        return
    zeilen[nummer - 1] = neuer_text
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", "\n".join(zeilen))


def _weich_dict(conn, chat_id: int) -> dict[int, str]:
    """``arbeitsstand.fragen_weich`` als ``{Nummer: Text}`` -- derselbe Leser
    wie im Leitfaden (``leitfaden.einleitungen``), weil es dasselbe
    Zeilenformat ist ("<Nummer> — <Text>")."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_weich"] if stand else "") or ""
    except (IndexError, KeyError):
        return {}
    return leitfaden.einleitungen(roh)


def _setze_weich(conn, chat_id: int, zuordnung: dict[int, str]) -> None:
    if not zuordnung:
        repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", None)
        return
    zeilen = [f"{n} — {t}" for n, t in sorted(zuordnung.items())]
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "\n".join(zeilen))


def _decisions(conn, chat_id: int) -> list[str]:
    """Der Entscheidungsstand, eine Position je Zeile aus ``fragen_auswahl``
    -- "ja" / "nein" / "" (noch offen). Kuerzer als die Fragenliste heisst:
    der Rest ist offen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_entschieden"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    if not roh:
        return []
    return roh.split(",")


def _setze_entscheidung(conn, chat_id: int, nummer: int, wert: str) -> None:
    entschieden = _decisions(conn, chat_id)
    while len(entschieden) < nummer:
        entschieden.append("")
    entschieden[nummer - 1] = wert
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", ",".join(entschieden))


def _naechste_offene(conn, chat_id: int, gesamt: int) -> int | None:
    """Die erste Frage ohne Entscheidung, oder None, wenn alle entschieden
    sind."""
    entschieden = _decisions(conn, chat_id)
    for nummer in range(1, gesamt + 1):
        wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
        if not wert:
            return nummer
    return None


def _aktuelle_offene_nummer(conn, chat_id: int) -> int | None:
    """Die Frage, die gerade vorgelegt ist UND noch unentschieden ist --
    genau die Bedingung, unter der eine freie Nachricht als Schaerfungswunsch
    gilt (``nimm_offene_frage_text``). Entschieden heisst: die naechste
    Frage ist schon unterwegs, eine Nachricht dazwischen gehoert nicht mehr
    hierher."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_aktuell"] if stand else "") or ""
    except (IndexError, KeyError):
        return None
    if not roh.strip().isdigit():
        return None
    nummer = int(roh)
    entschieden = _decisions(conn, chat_id)
    wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
    return nummer if not wert else None


def einzeln_aktiv(conn, chat_id: int) -> bool:
    """True, solange die Stufe "Fragen einzeln durchgehen" laeuft --
    ``fragen_aktuell`` traegt eine Fragennummer (Fund 02.10.2026, Padua-Live,
    web_post 73/74: aufnahme 70 lief waehrend genau dieser Stufe und
    ueberschrieb ``arbeitsstand.fragen`` mit der einen gerade geschaerften
    Zeile).

    ``fragen_aktuell`` bleibt gesetzt vom ersten ``starte_durchgehen`` bis
    zur letzten Entscheidung -- auch waehrend einer Schaerfung (Knopfdruck,
    freier Aenderungswunsch, die Modellantwort darauf): genau das Fenster, in
    dem der Erkenner nicht parallel ``fragen`` schreiben darf
    (``erkenner._wende_arbeitsstand_an``) und keine zweite, generische
    Speicherleiste fuer ``fragen`` haengen darf (``erkenner._sende_meldung``)
    -- die Leiste unter der gerade vorgelegten Frage ist die einzige."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_aktuell"] if stand else "") or ""
    except (IndexError, KeyError):
        return False
    return roh.strip().isdigit()


# --- Der Ueberblick ---------------------------------------------------------


def fragenliste(conn, chat_id: int) -> str:
    """Die vorgeschlagenen Fragen ausgeschrieben und nummeriert, eine je
    Zeile, nach Begriffen gruppiert -- unveraendert seit dem 06.09.2026."""
    zeilen: list[str] = []
    letzter_begriff = None
    for nummer, frage in enumerate(_auswahlfragen(conn, chat_id), start=1):
        begriff, trenner, rest = frage.partition(":")
        if trenner and 0 < len(begriff.strip()) <= 30 and rest.strip():
            if begriff.strip() != letzter_begriff:
                letzter_begriff = begriff.strip()
                zeilen.append(("\n" if zeilen else "") + f"{letzter_begriff}")
            zeilen.append(f"{nummer}. {rest.strip()}")
        else:
            zeilen.append(f"{nummer}. {frage}")
    return "\n".join(zeilen)


def biete_fragenauswahl(conn, tg, chat_id: int, wert: str,
                        weich_wert: str | None = None,
                        text: str | None = None) -> int:
    """Legt einen frischen Vorschlag ab und zeigt den Ueberblick mit der
    Richtungsfrage (02.10.2026).

    ``wert`` ist der Inhalt von ``VORSCHLAG FRAGENAUSWAHL:``, ``weich_wert``
    der von ``VORSCHLAG FRAGEN WEICH:`` aus demselben Modellzug (oder None,
    wenn keine Frage sensibel war). Eine neue Runde ersetzt die vorige
    vollstaendig -- Entscheidungsstand und laufende Frage werden
    zurueckgesetzt, eine Entscheidung zu einer inzwischen ersetzten Frage
    waere bedeutungslos."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", wert)
    _setze_weich(
        conn, chat_id, leitfaden.einleitungen(weich_wert) if weich_wert else {},
    )
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)

    vorspann = (text or "").strip()
    nachricht = "\n\n".join(
        teil for teil in (vorspann, fragenliste(conn, chat_id),
                          T._TEXT_FRAGEN_RICHTUNG_FRAGE)
        if teil
    )
    leiste = [
        (T._TEXT_FRAGEN_EINZELN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_EINZELN, None))),
        (T._TEXT_FRAGEN_ANDERE_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_ANDERE, None))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, nachricht, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def frage_fuer_andere_richtung(conn, chat_id: int, richtung: str = "") -> str:
    """Die fertige ``ANWEISUNG_FRAGEN_ANDERE`` -- ein Ort fuer beide Aufrufer
    ("Andere Richtung" mit gesagter Richtung, "keine Frage angenommen" ohne)."""
    alte = _auswahlfragen(conn, chat_id)
    richtung_satz = (
        T._TEXT_FRAGEN_RICHTUNG_SATZ.format(richtung=richtung.strip())
        if richtung.strip() else ""
    )
    return T.ANWEISUNG_FRAGEN_ANDERE.format(
        alte="\n".join(f"- {f}" for f in alte), richtung_satz=richtung_satz,
    )


# --- Frage fuer Frage --------------------------------------------------------


def _zeige_frage(conn, tg, chat_id: int, nummer: int) -> int:
    """Legt eine Frage als die aktuelle fest und zeigt sie -- Kopf, Frage,
    darunter Annehmen / Verwerfen / Schaerfen.

    Zeigt die weiche Fassung NICHT mehr pro Frage (Birk, Padua-Live
    02.10.2026: "Warum kommt bei Frage 5/25 ein Vorschlag, es softer zu
    formulieren? Mach die softere Formulierung nicht direkt bei der Frage,
    sondern als Angebot am Ende von allen Fragen.") -- die weiche Fassung
    bleibt in ``arbeitsstand.fragen_weich`` gespeichert und wird erst nach
    der letzten Entscheidung angeboten (``_biete_weiche_fassungen_an``,
    aufgerufen aus ``_schliesse_fragen_ab``).

    Kein Modellaufruf: die Darstellung ist immer deterministisch, auch nach
    einer Ueberarbeitung."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", str(nummer))
    fragen = _auswahlfragen(conn, chat_id)
    gesamt = len(fragen)
    zeile = fragen[nummer - 1]
    begriff, trenner, rest = zeile.partition(":")
    if trenner and rest.strip():
        kopf = T._TEXT_FRAGE_KOPF.format(
            nummer=nummer, gesamt=gesamt, begriff=begriff.strip(),
        )
        frage_text = rest.strip()
    else:
        kopf = T._TEXT_FRAGE_KOPF_OHNE_BEGRIFF.format(nummer=nummer, gesamt=gesamt)
        frage_text = zeile

    text = f"{kopf}\n\n{frage_text}"

    leiste = [
        (T._TEXT_FRAGE_ANNEHMEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_ANNEHMEN, str(nummer)))),
        (T._TEXT_FRAGE_VERWERFEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_VERWERFEN, str(nummer)))),
        (T._TEXT_FRAGE_SCHAERFEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_SCHAERFEN, str(nummer)))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def starte_durchgehen(conn, tg, chat_id: int) -> bool:
    """"Ja, einzeln durchgehen" -- zeigt Frage 1. Liefert False, wenn es
    nichts zu zeigen gibt (eine ueberholte Nachricht)."""
    if not _auswahlfragen(conn, chat_id):
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
    _zeige_frage(conn, tg, chat_id, 1)
    return True


def frage_warten_auf_richtung(conn, tg, chat_id: int) -> None:
    """"Andere Richtung" -- fragt deterministisch nach der Richtung; die
    naechste freie Nachricht loest den neuen Vorschlag aus
    (``nimm_offene_frage_text``)."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", "richtung")
    tg.sende(chat_id, T._TEXT_FRAGEN_RICHTUNG_GEFRAGT)


def entscheide(conn, tg, klm, e, chat_id: int, nummer: int, wert: str) -> str:
    """Annehmen ("ja") oder Verwerfen ("nein") fuer eine Frage -- zeigt die
    naechste offene Frage, oder schliesst ab, wenn keine mehr offen ist.

    Liefert die sichtbare Quittung (Web-Toast/Telegram
    ``answerCallbackQuery``) -- seit dem Fund 02.10.2026 (Birk) die
    tatsaechliche Entscheidung (``✓ Angenommen``/``✗ Verworfen``) statt des
    vorher immer gleichen, nichtssagenden ``T._TEXT_FRAGE_ENTSCHIEDEN``
    ("Notiert")."""
    fragen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(fragen):
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return T._TEXT_FRAGEN_KEINE_AUSWAHL
    _setze_entscheidung(conn, chat_id, nummer, wert)
    quittung = T._TEXT_FRAGE_ANGENOMMEN if wert == "ja" else T._TEXT_FRAGE_VERWORFEN
    naechste = _naechste_offene(conn, chat_id, len(fragen))
    if naechste is None:
        _schliesse_fragen_ab(conn, tg, klm, e, chat_id)
        return quittung
    _zeige_frage(conn, tg, chat_id, naechste)
    return quittung


def frage_waehlt_schaerfen(conn, tg, chat_id: int, nummer: int) -> str:
    """"Schaerfen" -- fragt deterministisch, was sich aendern soll. Die
    Antwort kommt als normale Nachricht und wird ueber
    ``nimm_offene_frage_text`` abgefangen, weil ``fragen_aktuell`` hier
    defensiv (erneut) auf diese Frage gesetzt wird -- derselbe Schutz wie
    eine aus Versehen verschobene Reihenfolge."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", str(nummer))
    tg.sende(chat_id, T._TEXT_FRAGE_WAS_AENDERN)
    return T._TEXT_FRAGE_WAS_AENDERN


def _starte_schaerfung(conn, tg, klm, e, chat_id: int, nummer: int, wunsch: str) -> None:
    fragen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(fragen):
        return
    frage = fragen[nummer - 1]
    weich = _weich_dict(conn, chat_id).get(nummer, "")
    sensibel_hinweis = (
        T._TEXT_FRAGE_SCHAERFEN_SENSIBEL_HINWEIS.format(weich=weich) if weich else ""
    )
    anweisung = T.ANWEISUNG_FRAGE_SCHAERFEN.format(
        nummer=nummer, frage=frage, wunsch=wunsch, sensibel_hinweis=sensibel_hinweis,
    )
    _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)


def uebernimm_schaerfung(conn, tg, chat_id: int, frage_block: str,
                         weich_block: str | None) -> int:
    """Die Antwort auf eine Schaerfung: ersetzt genau die aktuelle Frage
    (Text und, falls vorhanden, ihre weiche Fassung) und zeigt sie wieder --
    erst Annehmen oder Verwerfen bringt die naechste.

    Liefert die ``message_id`` der neu gezeigten (oder der Fehler-)Nachricht,
    NICHT den Quittungstext (Fund 02.10.2026, Padua-Live: ``basis.
    sende_mit_speicherleiste`` reicht genau diesen Rueckgabewert als
    ``message_id`` an ``repo.merke_nachricht`` weiter -- ein Text statt einer
    Zahl landete dort in der Spalte ``message_id``, SQLite sortiert TEXT ueber
    jedem INTEGER, und ``erkenner.erkenne`` (``max(n[\"message_id\"] ...)``)
    stolperte seitdem bei JEDEM Lauf dieser Gruppe ueber einen TypeError --
    der Erkenner blieb fuer die Gruppe fuer immer stumm)."""
    from interview_theater import vorschlag

    nummer = _aktuelle_offene_nummer(conn, chat_id)
    if nummer is None:
        return tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
    zeilen = vorschlag.zeilen(frage_block)
    neue_frage = zeilen[0] if zeilen else frage_block.strip()
    if neue_frage:
        _setze_frage_zeile(conn, chat_id, nummer, neue_frage)
    weich = _weich_dict(conn, chat_id)
    neue_weich = leitfaden.einleitungen(weich_block).get(nummer) if weich_block else None
    if neue_weich:
        weich[nummer] = neue_weich
    else:
        weich.pop(nummer, None)
    _setze_weich(conn, chat_id, weich)
    return _zeige_frage(conn, tg, chat_id, nummer)


def nimm_offene_frage_text(conn, tg, klm, e, chat_id: int, text: str) -> bool:
    """Die deterministische Weiche fuer eine freie Nachricht in Phase 2
    (aufgerufen aus ``ablauf._war_die_erwartete_antwort`` wie zuvor
    ``nimm_fragennummern``). Liefert True, wenn die Nachricht hier verarbeitet
    wurde -- dann geht sie NICHT zusaetzlich in den Gespraechszug.

    Zwei Faelle, beide ohne Erkenner-Lauf (kein Modellaufruf nur zum
    Klassifizieren):

    1. Nach "Andere Richtung" wartet ``fragen_warte_auf == 'richtung'`` --
       die Nachricht ist die gewuenschte Richtung.
    2. Steht eine Frage aktuell und unentschieden da, ist die Nachricht ihr
       Schaerfungswunsch -- mit oder ohne vorherigen Druck auf "Schaerfen"."""
    text = (text or "").strip()
    if not text:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return False
    try:
        warte = (stand["fragen_warte_auf"] or "").strip()
    except (IndexError, KeyError):
        warte = ""
    if warte == "richtung":
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
        anweisung = frage_fuer_andere_richtung(conn, chat_id, richtung=text)
        _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)
        return True

    nummer = _aktuelle_offene_nummer(conn, chat_id)
    if nummer is not None:
        _starte_schaerfung(conn, tg, klm, e, chat_id, nummer, text)
        return True
    return False


def _schliesse_fragen_ab(conn, tg, klm, e, chat_id: int) -> str:
    """Alle Fragen sind entschieden: aus den angenommenen wird
    ``arbeitsstand.fragen``, ihre weichen Fassungen wandern auf die neue
    Nummerierung um -- und die Kette geht weiter zur Eroeffnung. Ohne eine
    einzige Annahme gibt es keine Frageliste; stattdessen sagt der Bot das
    und schlaegt neue Fragen vor.

    Hat mindestens eine angenommene Frage eine weiche Fassung, kommt VOR der
    Eroeffnung noch ein eigenes Angebot (``_biete_weiche_fassungen_an``,
    Birk 02.10.2026) -- die Eroeffnung startet dann erst, wenn die Gruppe
    das Angebot beantwortet hat (``fragen_weich_angebot`` in
    ``_WEICH_ANGEBOT_WIRKUNGEN``)."""
    fragen = _auswahlfragen(conn, chat_id)
    entschieden = _decisions(conn, chat_id)
    weich = _weich_dict(conn, chat_id)

    angenommen: list[str] = []
    neue_weich: dict[int, str] = {}
    for i, frage in enumerate(fragen, start=1):
        if i <= len(entschieden) and entschieden[i - 1] == "ja":
            angenommen.append(frage)
            if i in weich:
                neue_weich[len(angenommen)] = weich[i]

    if not angenommen:
        repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_ANGENOMMEN)
        anweisung = frage_fuer_andere_richtung(conn, chat_id)
        _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)
        return T._TEXT_FRAGEN_KEINE_ANGENOMMEN

    wert = "\n".join(angenommen)

    def _schreibe():
        repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen", wert)
        if neue_weich:
            _setze_weich(conn, chat_id, neue_weich)
        else:
            # Leerer String, nicht NULL: "keine der Fragen ist sensibel" ist
            # ein Ergebnis der Pruefung, kein fehlender Wert
            # (``phasen._feld_geprueft``) -- sonst haelt die leere Pruefung
            # Phase 3 fuer immer zurueck.
            repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")

    text = (
        T._TEXT_FRAGEN_ABGESCHLOSSEN.format(anzahl=len(angenommen)) + "\n"
        + "\n".join(f"{n}. {f}" for n, f in enumerate(angenommen, start=1))
    )
    # Derselbe Undo-Knopf wie unter "Ja, speichern" (UX-Knoepfe-Karte,
    # Abschnitt 2): ein Druck macht die Fragen wieder zum offenen, einzeln
    # entschiedenen Zustand -- nicht nur leer.
    lauf_id = erkenner.lauf_fuer_knopf(conn, e, chat_id, text, _schreibe)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_FRAGEN.format(wert=wert),
        quelle="knopf",
    )
    if lauf_id is None:
        tg.sende(chat_id, text, system=True)
    else:
        sende_notiert_nur_undo(conn, tg, chat_id, text, lauf_id)
    if neue_weich:
        _biete_weiche_fassungen_an(conn, tg, angenommen, neue_weich, chat_id)
    else:
        starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_QUITTUNG


def _biete_weiche_fassungen_an(
    conn, tg, angenommen: list[str], neue_weich: dict[int, str], chat_id: int,
) -> int:
    """Das Angebot nach der letzten Entscheidung, EINMAL fuer alle sensiblen
    Fragen zusammen (Birk, Padua-Live 02.10.2026): listet jede angenommene
    Frage mit weicher Fassung auf, mit den zwei Knoepfen "Weiche Fassungen
    uebernehmen" / "Wie sie sind lassen". Erst die Antwort darauf setzt die
    Kette zur Eroeffnung fort (``_wirkung_fragen_weich_*`` in wirkung.py)."""
    zeilen = [
        T._TEXT_FRAGEN_WEICH_ZEILE.format(
            nummer=n, frage=angenommen[n - 1], weich=weich,
        )
        for n, weich in sorted(neue_weich.items())
    ]
    text = T._TEXT_FRAGEN_WEICH_ANGEBOT + "\n\n" + "\n\n".join(zeilen)
    leiste = [
        (T._TEXT_FRAGEN_WEICH_UEBERNEHMEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_WEICH_UEBERNEHMEN, None))),
        (T._TEXT_FRAGEN_WEICH_LASSEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_WEICH_LASSEN, None))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def frage_weich_uebernehmen(conn, tg, klm, e, chat_id: int) -> str:
    """"Weiche Fassungen uebernehmen" -- ``fragen_weich`` bleibt stehen (der
    Leitfaden nutzt es bereits, siehe ``leitfaden.py``); nur die Kette geht
    jetzt weiter."""
    starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_WEICH_UEBERNOMMEN


def frage_weich_lassen(conn, tg, klm, e, chat_id: int) -> str:
    """"Wie sie sind lassen" -- die Fragen bleiben in der Originalformulierung,
    ``fragen_weich`` wird geleert, damit der Leitfaden keine weichen
    Fassungen mehr zeigt, die die Gruppe explizit abgelehnt hat."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")
    starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_WEICH_BEHALTEN


# --- Eroeffnung und Abschluss (unveraendert seit dem 06.09.2026) ----------


def starte_eroeffnung(conn, tg, klm, e, chat_id: int) -> bool:
    """Der Schritt nach den Fragen: Eroeffnungs- und Abschlusstext. Laeuft
    automatisch, sobald die Frageliste steht -- wieder ein Auftragszug im
    eigenen Thread, wieder die Grundleiste darunter."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = (stand["fragen"] if stand else "") or ""
    return _starte_auftrag(
        conn, tg, klm, e, chat_id,
        anweisungen.fuelle(T.ANWEISUNG_EROEFFNUNG).format(fragen=fragen),
        arbeitszeile=T.TEXT_ARBEIT_EROEFFNUNG, arbeitsart="eroeffnung",
    )


def _speichere_eroeffnung(conn, tg, chat_id: int, wert: str, e=None, klm=None) -> str:
    """Zerlegt den Block ``VORSCHLAG EROEFFNUNG:`` in Eroeffnung und
    Abschluss und legt beides ab. Unveraendert seit dem 06.09.2026."""
    import re

    eroeffnung: list[str] = []
    abschluss: list[str] = []
    ziel = eroeffnung
    for zeile in (wert or "").splitlines():
        roh = zeile.strip()
        if not roh:
            continue
        ohne = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", roh)
        kopf, sep, rest = ohne.partition(":")
        if sep and kopf.strip().lower().startswith(("abschluss", "closing")):
            ziel = abschluss
            if rest.strip():
                ziel.append(rest.strip())
            continue
        if sep and kopf.strip().lower().startswith(("eroeffnung", "opening")):
            ziel = eroeffnung
            if rest.strip():
                ziel.append(rest.strip())
            continue
        ziel.append(ohne)
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung", "\n".join(eroeffnung).strip() or None
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", "\n".join(abschluss).strip() or None
    )
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_EROEFFNUNG_FESTGELEGT,
        quelle="knopf",
    )
    leitfaden.sende_einmal(conn, tg, chat_id, e=e)
    from interview_theater.knoepfe.stationen import (
        biete_phase_proaktiv, uebergang_nach_speichern,
    )

    if not uebergang_nach_speichern(conn, tg, klm, e, chat_id):
        biete_phase_proaktiv(conn, tg, chat_id)
    return T._TEXT_EROEFFNUNG_QUITTUNG


def _leitfaden_knopf(conn, chat_id: int) -> tuple[str, str] | None:
    """"Leitfaden zeigen", sobald es einen gibt -- sonst None."""
    if not leitfaden.steht(conn, chat_id):
        return None
    return (
        T._TEXT_LEITFADEN_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_LEITFADEN, None)),
    )

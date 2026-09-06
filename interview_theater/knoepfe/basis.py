"""Die Grundleiste und ihre Bausteine -- die Schicht, auf der alles steht.

Hier liegen die vier Dinge, die jede Knopfgruppe braucht: die Umrechnung
zwischen Knopf-id und ``callback_data`` (``_daten`` / ``_id_aus_daten``, an
der Zusage 1 haengt), die **Grundleiste** unter jeder Vorschlagsnachricht
("Eigene Idee" · "Passt, aber anders" · "Gefaellt uns, weiter"), der
Speicherweg dahinter (``_speichere``, ``offene_art``, ``_ist_bestaetigung``)
und der Weg vom Knopf zu einem Modellaufruf, der nicht im Handler stattfindet
(``_starte_auftrag``, Zusage 2).

Aufrufe **nach oben** -- in die Fragen, die Figuren, die Szenen -- gibt es
genau vier, und sie stehen als lokaler Import in der jeweiligen Funktion:
sonst waere die Schicht keine.
"""

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ART_ANDERS, ART_EIGENE, ART_KERNTHEMA, ART_PHASE, ART_SPEICHERN,
    MAX_AUSWAHL, MAX_VORSCHLAEGE, PRAEFIX, TEXT_ANDERS_KNOPF,
    TEXT_EIGENE_IDEE_KNOPF, TEXT_WEITER_KNOPF, TRENNER, _AUSWAHLMARKER,
    _ERSTER_ALS_WERT, _FELD_FUER, _NOTIERT, _TEXT_ANDERS_KNOPF,
    _TEXT_EIGENE_KNOPF, _TEXT_FRAGEN_WAHL, _TEXT_KERNTHEMA_FRAGE,
    _TEXT_KERNTHEMA_KEINE, _TEXT_NACH_SPEICHERN_FRAGE, _TEXT_SCHON_GESETZT,
    _TEXT_SPEICHERN_KNOPF, _TEXT_UNBEKANNT, log,
)


def _daten(knopf_id: int) -> str:
    """Die ``callback_data`` zu einer Knopf-id."""
    return f"{PRAEFIX}{knopf_id}"


def _id_aus_daten(daten: str) -> int | None:
    """Liest die Knopf-id aus ``callback_data``; None bei allem anderen.

    Tolerant gegenueber Fremdem: in einer Gruppe kann ein anderer Bot
    Knoepfe stehen haben, und ein Knopfdruck aus einer alten Fassung dieses
    Bots (anderes Format) darf die Schleife nicht zum Absturz bringen."""
    if not daten.startswith(PRAEFIX):
        return None
    rest = daten[len(PRAEFIX):]
    return int(rest) if rest.isdigit() else None


def _entferne_tastatur(tg, chat_id, message_id) -> None:
    """Nimmt die Knoepfe unter der Angebotsnachricht weg -- nachdem die
    Wirkung eingetreten ist, nie davor.

    Fehlschlaege werden geschluckt: die Wirkung steht schon in der Datenbank,
    und die Gruppe soll wegen einer misslungenen Kosmetik keine Fehlermeldung
    sehen (global-constraints.md 'Fehlerhaltung')."""
    if message_id is None:
        return
    try:
        tg.entferne_knoepfe(chat_id, message_id)
    except Exception:
        log.warning("Knoepfe entfernen fehlgeschlagen, chat_id=%s", chat_id)


def kernthema_vorschlaege(conn, chat_id: int) -> list[str]:
    """Bis zu ``MAX_VORSCHLAEGE`` Kernthema-Vorschlaege, rein aus der
    Datenbank -- die Kurzformen der Verdichtungsthemen
    (``verdichtung_thema.kurz``, hoechstens acht Woerter).

    Kein Modellaufruf: die Themen sind schon beim Verdichten eines Interviews
    entstanden und bezahlt, sie hier ein zweites Mal zu erfragen waere ein
    zweiter Aufruf fuer dasselbe Ergebnis. Doppelte fallen raus (zwei
    Interviews koennen dasselbe Thema tragen), die Reihenfolge bleibt die der
    Entstehung -- die aelteste Verdichtung zuerst."""
    gesehen: list[str] = []
    for verdichtung in repo.verdichtungen(conn, chat_id):
        for thema in repo.themen_zu(conn, verdichtung["id"]):
            text = (thema["kurz"] or thema["thema"] or "").strip()
            if text and text not in gesehen:
                gesehen.append(text)
    return gesehen[:MAX_VORSCHLAEGE]


def biete_kernthema(conn, tg, chat_id: int, vorschlaege: list[str] | None = None) -> bool:
    """Bietet die Kernthema-Vorschlaege als Knoepfe an. Liefert False, wenn
    es nichts anzubieten gab -- dann hat der Aufrufer bereits die Zeile
    bekommen, die das erklaert.

    Der Volltext steht in der Beschriftung UND in der Tabelle ``knopf``, nie
    in ``callback_data`` (Zusage 1 im Moduldocstring)."""
    if vorschlaege is None:
        vorschlaege = kernthema_vorschlaege(conn, chat_id)
    vorschlaege = [v for v in vorschlaege if v.strip()][:MAX_VORSCHLAEGE]
    if not vorschlaege:
        tg.sende(chat_id, _TEXT_KERNTHEMA_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_KERNTHEMA, wert)))
        for wert in vorschlaege
    ]
    tg.sende_mit_knoepfen(chat_id, _TEXT_KERNTHEMA_FRAGE, knoepfe)
    return True


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = f"Weiter zu {phasen.knopfbezeichnung(nummer)}"
    tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def _phasenknopf(conn, chat_id: int) -> tuple[str, str] | None:
    """Der Knopf "Weiter zu Phase N", wenn die Materiallage eine hoehere
    Stufe hergibt -- sonst None (``phasen.naechste_moegliche``, reine
    Leseabfrage).

    Die Sperre fuer Phase 4 steckt in ``phasen.voraussetzungen``, nicht
    hier: solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    ``naechste_moegliche`` die 4 gar nicht erst her -- an allen drei Stellen
    zugleich (diese Funktion, ``biete_nach_aufnahme``,
    ``kontext._baue_phasenhinweis``)."""
    nummer = phasen.naechste_moegliche(conn, chat_id)
    if nummer is None:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    return (f"Weiter zu {phasen.knopfbezeichnung(nummer)}", _daten(knopf_id))


def _nimm_alte_leiste_ab(conn, tg, chat_id: int, art: str) -> None:
    """Nimmt die Tastatur einer aelteren, ungedrueckten Speicher-Leiste
    derselben Art ab, bevor eine neue kommt.

    Warum: der Wert steckt im Knopf, nicht im Text. Nach drei Vorschlaegen
    staenden sonst drei Leisten im Chat, und ein Druck auf die von vor zwei
    Nachrichten speicherte den ueberholten Vorschlag -- genau die Sorte
    stiller Fehler, gegen die die Knoepfe angetreten sind. Die alten
    Knopfzeilen werden zusaetzlich als benutzt gestempelt
    (``repo.verfallen_lassen``), damit sie auch dann nicht mehr wirken, wenn
    die App die Tastatur noch einen Moment zeigt."""
    alte = repo.offene_knoepfe(conn, chat_id, art)
    if not alte:
        return
    repo.verfallen_lassen(conn, [k["id"] for k in alte])
    for message_id in dict.fromkeys(k["message_id"] for k in alte):
        _entferne_tastatur(tg, chat_id, message_id)


def speicherleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die **Grundleiste** unter einem Vorschlag: "Eigene Idee" · "Passt,
    aber anders" · "Gefaellt uns, weiter" (05.09.2026 abends, Birk).

    ``wert`` ist der Text aus dem Vorschlagsblock (``vorschlag.lies``) --
    exakt der, der beim Druck gespeichert wird. Nichts wird hier
    umformuliert, gekuerzt oder ergaenzt: was die Gruppe im Chat liest, ist
    was in der Datenbank landet.

    **Beide rechten Knoepfe speichern.** "Passt, aber anders" schreibt
    denselben Wert wie "Gefaellt uns, weiter" und fragt danach nach der
    Aenderung -- der Unterschied ist, was DANACH passiert, nicht ob etwas in
    der Datenbank steht. Der Anlass ist gemessen: ein "nochmal anders" ohne
    Speichern liess die Gruppe drei Runden lang mit einem leeren
    Arbeitsstand weiterarbeiten, und beim Abbruch war nichts da.

    Der Volltext steht in der Tabelle ``knopf``, nie in ``callback_data``
    (Zusage 1 im Moduldocstring) -- eine Begriffsliste sprengt die 64 Bytes
    muehelos."""
    eigene = repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)
    anders = repo.lege_knopf_an(
        conn, chat_id, ART_ANDERS, f"{art}{TRENNER}{wert}"
    )
    speichern = repo.lege_knopf_an(
        conn, chat_id, ART_SPEICHERN, f"{art}{TRENNER}{wert}"
    )
    return [
        (_TEXT_EIGENE_KNOPF, _daten(eigene)),
        (_TEXT_ANDERS_KNOPF, _daten(anders)),
        (_TEXT_SPEICHERN_KNOPF, _daten(speichern)),
    ]


def _feld_ist_frei(conn, chat_id: int, feld: str) -> bool:
    """Darf die Grundleiste einen Auswahl-Vorschlag fuer dieses Feld tragen?

    Ja, solange das Feld leer ist -- oder die Gruppe ausdruecklich um eine
    Aenderung gebeten hat (``arbeitsstand.aenderung_offen``). Steht der Wert
    und ist nichts offen, traegt die Leiste ihn nicht: das war der Live-Fall
    vom 05.09.2026, 21:50 (siehe ``sende_mit_speicherleiste``)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return True
    if (stand["aenderung_offen"] or "").strip() == feld:
        return True
    if feld not in stand.keys():
        return True
    return not (stand[feld] or "").strip()


def _auswahlleiste(conn, chat_id: int, marker: str, wert: str) -> list[tuple[str, str]]:
    """Ein Knopf je Zeile eines Auswahl-Blocks (``VORSCHLAG RICHTUNGEN:`` und
    Verwandte) -- die Zeile ist zugleich Beschriftung und gespeicherter Wert.

    Der Volltext steht wie ueberall in der Tabelle ``knopf``; in
    ``callback_data`` steht nur die id (Zusage 1)."""
    from interview_theater import vorschlag

    art = _AUSWAHLMARKER[marker]
    return [
        (zeile, _daten(repo.lege_knopf_an(conn, chat_id, art, zeile)))
        for zeile in vorschlag.zeilen(wert)[:MAX_AUSWAHL]
    ]


def sende_mit_speicherleiste(conn, tg, chat_id: int, text: str) -> tuple[int, bool]:
    """Schickt eine Bot-Antwort und haengt die Knoepfe darunter
    (05.09.2026). Liefert ``(message_id, leiste?)``.

    Zwei Sorten Knopf, in dieser Reihenfolge:

    1. **Optionsknoepfe oben** -- einer je Zeile eines Auswahl-Blocks
       (``VORSCHLAG RICHTUNGEN:``, ``KERNTHEMA:``, ``NAMEN:``, ``DUKTUS:``,
       ``RAHMEN:``). Sie tragen die Auswahl selbst.
    2. **Die Grundleiste unten** -- "Eigene Idee" · "Passt, aber anders" ·
       "Gefaellt uns, weiter", unter JEDER Vorschlagsnachricht.

    Die Grundleiste braucht einen speicherbaren Wert. Er kommt entweder aus
    dem Block der gerade offenen Art (``offene_art``: Begriffe in Phase 1,
    Fragen in 2, Kernthema/Figuren in 4) oder -- bei einer Auswahlliste --
    aus deren ERSTEM Vorschlag (``_ERSTER_ALS_WERT``). Gibt es weder das eine
    noch das andere, steht die Nachricht ohne Knoepfe da: **kein Raten**,
    lieber keine Knoepfe als welche, die den falschen Text speichern.

    Die Markerzeilen selbst gehen nie in den Chat (``vorschlag.ohne_marker``);
    sie sind Technik zwischen Prompt und Code, kein Inhalt fuer die Gruppe.

    Der Text ist auch ohne Leiste immer derselbe -- das ist wichtig: die
    Gruppe soll nicht daran, ob Knoepfe darunter stehen, ablesen muessen, ob
    das Modell die Form eingehalten hat."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(text) or text
    bloecke = vorschlag.alle(text)

    # Die Fragenauswahl der Phase 2 (06.09.2026) ist keine Leiste, sondern
    # eine eigene Mehrfachauswahl: zehn Knoepfe zum Antippen und drei
    # Handlungsknoepfe darunter. Sie kommt VOR allem anderen, weil sie den
    # Text mitbringt und nichts speichert.
    if "fragenauswahl" in bloecke:
        # ``ohne_block`` statt ``ohne_marker``: die zehn Fragen stehen gleich
        # auf den Knoepfen, und zweimal dieselbe Liste ist auf dem Telefon
        # eine halbe Bildschirmseite Doppelung.
        from interview_theater.knoepfe.fragen import biete_fragenauswahl

        return biete_fragenauswahl(
            conn, tg, chat_id, bloecke["fragenauswahl"],
            vorschlag.ohne_block(text, "fragenauswahl") or _TEXT_FRAGEN_WAHL,
        ), True

    # Oben: die Auswahlknoepfe. Kommen mehrere Auswahl-Bloecke in einer
    # Nachricht (das Modell soll das nicht, tut es aber gelegentlich),
    # gewinnt der erste aus _AUSWAHLMARKER -- eine feste Ordnung statt einer
    # zufaelligen aus dem Text.
    marker = next((m for m in _AUSWAHLMARKER if m in bloecke), None)
    art, wert = _leistenwert(conn, chat_id, bloecke, marker)

    if marker is None and (not art or not wert):
        return tg.sende(chat_id, sauber), False

    oben = _auswahlleiste(conn, chat_id, marker, bloecke[marker]) if marker else []
    if not art or not wert:
        return _sende_nur_auswahl(conn, tg, chat_id, sauber, marker, oben)

    if art == "figuren" and not oben:
        # Figuren sind zweistufig (05.09.2026 abends): Ebene 1 ist die Liste
        # mit "Anzahl aendern" und "Namen aendern" -- ein eigener Weg, kein
        # Sonderfall der Grundleiste.
        from interview_theater.knoepfe.figuren import biete_figurenliste

        return biete_figurenliste(conn, tg, chat_id, wert, sauber), True

    if art == "geschichte" and not oben:
        # Die Geschichte traegt Bogen, Ende UND die Szenenfolge; sie geht
        # deshalb ueber ihren eigenen Speicherweg (``_speichere_geschichte``)
        # und nicht ueber den Arbeitsstand-Setter -- sonst staende der
        # Vorschlagstext als ein Feld da und keine Szene in der Tabelle.
        from interview_theater.knoepfe.szenen import sende_geschichte

        return sende_geschichte(conn, tg, chat_id, text), True

    return _sende_mit_grundleiste(conn, tg, chat_id, sauber, art, wert, oben)


def _leistenwert(
    conn, chat_id: int, bloecke: dict, marker: str | None,
) -> tuple[str | None, str | None]:
    """Welchen ``(art, wert)`` traegt die Grundleiste unter dieser Nachricht?

    Entweder den Block der gerade offenen Art (``offene_art``) oder -- bei
    einer Auswahlliste -- deren ERSTEN Vorschlag. Findet sich keins von
    beidem, kommt ``(None, None)`` zurueck: **kein Raten**."""
    from interview_theater import vorschlag

    art = offene_art(conn, chat_id)
    wert = bloecke.get(art) if art else None
    if art == "fragen_weich" and wert is None and "einleitungen" in bloecke:
        # Der alte Weg bleibt begehbar (06.09.2026, 10:18): liefert ein
        # Modell noch ``VORSCHLAG EINLEITUNGEN:`` -- weil der Prompt-Umbau
        # den laufenden Zug einer Gruppe nicht ruecklaeufig aendert --,
        # traegt die Leiste diesen Block. Sonst staende die Antwort ohne
        # Knoepfe da, und die Stufe waere nicht abzunehmen.
        art, wert = "einleitungen", bloecke["einleitungen"]
    if marker in _ERSTER_ALS_WERT and _feld_ist_frei(
        conn, chat_id, _ERSTER_ALS_WERT[marker]
    ):
        # Eine Auswahlliste: die Grundleiste traegt den ERSTEN Vorschlag,
        # nie die ganze Liste -- "Passt, aber anders" soll einen Rahmen
        # speichern, nicht drei untereinander.
        #
        # **Nur, solange das Zielfeld frei ist** (06.09.2026, Birk,
        # Testgruppe 21:50): der Bot bot in Phase 6 drei Szenenbilder als
        # ``VORSCHLAG RAHMEN:`` an, die Gruppe druckte "Gefaellt uns,
        # weiter" -- und die Leiste ueberschrieb den Rahmen von 21:37 ("Vier
        # Freundinnen im Nordkiez ...") still mit "Leyla checkt ihr Handy auf
        # dem Schulhof". Steht das Feld schon und hat niemand um eine
        # Aenderung gebeten, traegt die Leiste diesen Wert gar nicht erst.
        erste = vorschlag.zeilen(bloecke[marker])
        if erste:
            art, wert = _ERSTER_ALS_WERT[marker], erste[0]
    return art, wert


def _sende_nur_auswahl(
    conn, tg, chat_id: int, sauber: str, marker: str | None, oben: list,
) -> tuple[int, bool]:
    """Auswahlknoepfe ohne speicherbaren Wert (Richtungen, Namen, Duktus): die
    Grundleiste faellt weg, die Optionen bleiben. "Eigene Idee" kommt trotzdem
    mit -- ohne sie gaebe es keinen Weg an der Liste vorbei."""
    if not oben:
        return tg.sende(chat_id, sauber), False
    oben.append(
        (
            _TEXT_EIGENE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, marker)),
        )
    )
    message_id = tg.sende_mit_knoepfen(chat_id, sauber, oben)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in oben], message_id
    )
    return message_id, True


def _sende_mit_grundleiste(
    conn, tg, chat_id: int, sauber: str, art: str, wert: str, oben: list,
) -> tuple[int, bool]:
    """Der Regelfall: Auswahlknoepfe oben, Grundleiste unten -- und die alten
    Leisten kommen vorher ab, damit im Chat nur eine bedienbar ist."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_EIGENE)
    leiste = oben + speicherleiste(conn, chat_id, art, wert)
    message_id = tg.sende_mit_knoepfen(chat_id, sauber, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


def offene_art(conn, chat_id: int) -> str | None:
    """Welche Art gerade noch fehlt und deshalb eine Speicher-Leiste
    verdient -- oder None.

    Die Reihenfolge ist die der Arbeit, nicht die des Alphabets, und sie
    haengt an der **Phase**, damit in Phase 1 nicht ploetzlich nach Figuren
    gefragt wird:

    * Phase 1 -- ``begriffe``, solange das Feld leer ist.
    * Phase 2 -- ``fragen``, solange das Feld leer ist.
    * Phase 4 -- ``rahmen`` (das **Setting**: Ort, Zeit, Anlass), solange das
      Feld leer ist; danach ``figuren``, solange die Liste nicht fixiert ist
      (``figuren_fixiert_am`` -- dieselbe Bedingung wie
      ``phasen.voraussetzungen[5]``). Kernthema und Kernfrage stehen hier
      seit dem Umbau vom 05.09.2026 nachts **nicht** mehr: es wird erfunden,
      nicht aus dem Material geschaelt.
    * Phase 5 -- ``geschichte``, solange das Feld leer ist.

    Steht der Wert, gibt es keine Leiste mehr -- **das** ist der Mechanismus
    hinter "die Leiste kommt nach jeder Aenderung wieder": speichert weder
    Knopf noch Erkenner, bleibt das Feld leer, und die naechste Bot-Antwort
    mit einem Vorschlagsblock traegt sie erneut."""
    phase = phasen.aktuelle(conn, chat_id)
    stand = repo.hole_arbeitsstand(conn, chat_id)

    def leer(feld: str) -> bool:
        return not (stand and (stand[feld] or "").strip())

    # "Passt, aber anders" hat gespeichert UND um eine Aenderung gebeten --
    # dann gehoert die Leiste wieder unter die naechste Antwort, obwohl das
    # Feld gefuellt ist. Ohne diese Ausnahme gaebe es keinen Weg, den
    # ueberarbeiteten Vorschlag abzunehmen (05.09.2026 abends).
    offen = (stand["aenderung_offen"] if stand else "") or ""
    if offen:
        return offen

    if phase == 1:
        return "begriffe" if leer("begriffe") else None
    if phase == 2:
        # Die Verfeinerungsebene (06.09.2026): erst die Fragen, dann die
        # Einleitungen zu den heiklen darunter, dann Eroeffnung und
        # Abschluss. Jede Stufe wird erst offen, wenn die davor steht --
        # sonst haenge die Leiste einer spaeteren Stufe unter dem Vorschlag
        # einer frueheren und speicherte den falschen Text.
        if leer("fragen"):
            return "fragen"
        # **Seit dem 06.09.2026, 10:18 ist die zweite Stufe die weiche
        # Fassung** und nicht mehr die Einleitung: die sensible Frage wird
        # umformuliert, nicht mit einem Vorsatz versehen. ``frage_einleitungen``
        # bleibt daneben stehen -- eine Gruppe, die den alten Weg schon
        # durchlaufen hat, soll ihn nicht ein zweites Mal gehen.
        if leer("fragen_weich") and leer("frage_einleitungen"):
            return "fragen_weich"
        if leer("interview_eroeffnung"):
            return "eroeffnung"
        return None
    if phase == 4:
        if leer("rahmen"):
            return "rahmen"
        if leer("figuren_fixiert_am"):
            return "figuren"
        # Seit dem 06.09.2026 gehoert die Geschichte in dieselbe Station:
        # steht die Figurenliste, ist sie die naechste offene Ebene -- ohne
        # Phasenwechsel dazwischen.
        if leer("geschichte"):
            return "geschichte"
    return None


def sende_notiert_mit_leiste(conn, tg, chat_id: int, text: str, art: str,
                             wert: str) -> tuple[int, bool]:
    """Die \"Notiert:\"-Meldung des Erkenners MIT der Grundleiste darunter.

    Der Anlass (Birk, Live-Befund Testgruppe 05.09.2026, 23:37): der
    Erkenner-Nachlauf laeuft NACH der Gespraechsantwort. Speichert er in
    Phase 4 oder 5 eine Ping-Pong-Art, stand die Grundleiste unter der
    Antwort davor -- also unter einem Text, der den Wert noch gar nicht
    kannte, waehrend die Nachricht mit dem Wert nackt dastand. Jetzt haengt
    sie dort, wo der Wert steht: \"Passt, aber anders\" schaerft nach,
    \"Gefaellt uns, weiter\" fixiert, \"Eigene Idee\" macht den Weg frei.

    Die alte Leiste wird abgenommen (``_nimm_alte_leiste_ab``), damit nicht
    zwei im Chat stehen und die aeltere den ueberholten Wert speichert."""
    for alte in (ART_SPEICHERN, ART_ANDERS, ART_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, alte)
    leiste = speicherleiste(conn, chat_id, art, wert)
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


# --- Phase 6 · Szenen: Angebote -------------------------------------------


def grundleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die drei Knoepfe, die unter JEDEM Vorschlag in Phase 6 stehen:
    "Eigene Idee" · "Passt, aber anders" · "Gefaellt uns, weiter".

    ``art`` ist die Knopf-Art, unter der gespeichert wird
    (``ART_SZENENFOLGE_SPEICHERN``, ``ART_SZENENFELDER_SPEICHERN``), ``wert``
    der Text, der beim Druck wirkt -- exakt der, der im Chat steht. Nichts
    wird hier umformuliert (dieselbe Zusage wie in ``speicherleiste``).

    "Gefaellt uns, weiter" und "Passt, aber anders" speichern BEIDE. Der
    Unterschied steht im Praefix des Wertes und wirkt danach: "anders" nimmt
    den Vorschlag an und fragt zugleich, was noch geaendert werden soll -- die
    Gruppe soll einen brauchbaren Vorschlag nicht wegwerfen muessen, nur weil
    ein Detail nicht stimmt (Birk, 05.09.2026)."""
    return [
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)),
        ),
        (
            TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"anders{TRENNER}{wert}")),
        ),
        (
            TEXT_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"weiter{TRENNER}{wert}")),
        ),
    ]


def _mit_leiste(conn, tg, chat_id: int, text: str, leiste: list[tuple[str, str]]) -> int:
    """Schickt ``text`` mit ``leiste`` und merkt sich die Nachricht je Knopf --
    damit eine spaetere Leiste die alte abnehmen kann
    (``_nimm_alte_leiste_ab``)."""
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def _ist_bestaetigung(conn, chat_id: int, art: str, wert: str) -> bool:
    """Ist dieser Speicherdruck nur ein Ja zu dem, was schon dasteht?

    Die Bedingung (06.09.2026, Birk): das Feld ist gesetzt, der Druck traegt
    einen ANDEREN Wert, und es ist keine Aenderung offen
    (``arbeitsstand.aenderung_offen``). Dann hat niemand um eine Aenderung
    gebeten -- und ein stilles Ueberschreiben ist genau der Fall vom
    Testabend: "Gefaellt uns, weiter" unter einem Szenenbild-Vorschlag
    ersetzte den Rahmen von 21:37 durch "Leyla checkt ihr Handy auf dem
    Schulhof", ohne dass irgendwo stand, dass etwas verloren geht.

    Ueberschrieben wird weiterhin nach "Passt, aber anders" (setzt
    ``aenderung_offen``) und durch den Erkenner, wenn die Gruppe den neuen
    Wert wirklich sagt -- beides sind ausgesprochene Absichten, kein
    Nebeneffekt eines Knopfdrucks."""
    if art not in _NOTIERT:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return False
    feld = _FELD_FUER.get(art, art)
    alt = (stand[feld] or "").strip() if feld in stand.keys() else ""
    if not alt or alt == wert.strip():
        return False
    return not (stand["aenderung_offen"] or "").strip()


def _speichere(conn, tg, chat_id: int, roh: str, weiterfrage: bool = True,
               nur_bestaetigen: bool = False) -> str:
    """Schreibt den Wert einer Speicher-Leiste in den Arbeitsstand -- ueber
    **dieselben** ``repo``-Funktionen wie ``erkenner.wende_an``.

    Das ist die ganze Uebung: kein zweiter Schreibweg, kein zweites Feld,
    keine zweite Notiert-Zeile. Der Erkenner-Pfad bleibt daneben bestehen;
    schreibt er zuerst, ist das Feld gesetzt und die Leiste erscheint gar
    nicht mehr (``offene_art``).

    ``roh`` ist ``"<art>|<wert>"`` (siehe ``ART_SPEICHERN``). Getrennt wird
    am ERSTEN '|', damit ein Wert mit '|' darin (eine Frageliste zum
    Beispiel) die Art nicht zerlegt."""
    art, _, wert = roh.partition(TRENNER)
    art = art.strip()
    wert = wert.strip()
    if not art or not wert:
        log.error("Speicher-Knopf ohne Wert, chat_id=%s, roh=%r", chat_id, roh)
        return _TEXT_UNBEKANNT

    if art == "figuren":
        from interview_theater.knoepfe.figuren import _uebernimm_figurenliste

        return _uebernimm_figurenliste(conn, tg, chat_id, wert)

    if art not in _NOTIERT:
        log.error("Speicher-Knopf mit unbekannter art %r, chat_id=%s", art, chat_id)
        return _TEXT_UNBEKANNT

    if nur_bestaetigen and _ist_bestaetigung(conn, chat_id, art, wert):
        # Das Feld steht, niemand hat um eine Aenderung gebeten: der Druck
        # ist ein Ja zum Bestehenden. Keine Schreiboperation, keine
        # Notiert-Zeile, kein Journal-Eintrag -- und vor allem kein stiller
        # Verlust (06.09.2026, Testgruppe 21:50).
        log.info(
            "Speicher-Knopf bestaetigt nur, art=%s, chat_id=%s", art, chat_id,
        )
        repo.merke_vorfall(
            conn, chat_id, None, "ueberschreiben_verhindert",
            f"'{art}' steht bereits und wurde durch einen Speicher-Knopf nicht ersetzt",
        )
        tg.sende(chat_id, _TEXT_SCHON_GESETZT)
        return _TEXT_SCHON_GESETZT

    repo.setze_arbeitsstand(conn, chat_id, _FELD_FUER.get(art, art), wert)
    if weiterfrage:
        # Abgenommen: die offene Aenderungsbitte ist erledigt, die Leiste
        # verschwindet wieder (``offene_art``).
        repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"{_NOTIERT[art]}: {wert}", quelle="knopf",
    )
    tg.sende(
        chat_id,
        f"Notiert:\n{_NOTIERT[art]}: {wert}",
    )
    # Danach die eine Frage, die den Zwischenraum offenhaelt -- und darunter,
    # wenn die Materiallage es hergibt, der Weg weiter
    # (``phasen.voraussetzungen``): der Knopf sagt, was jetzt dran ist,
    # statt dass jemand raten muss.
    if weiterfrage:
        phasenknopf = _phasenknopf(conn, chat_id)
        if phasenknopf is not None:
            tg.sende_mit_knoepfen(chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
        else:
            tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
    return f"{_NOTIERT[art]} uebernommen"


def _starte_auftrag(conn, tg, klm, e, chat_id: int, anweisung: str,
                    arbeitszeile: str | None = None) -> bool:
    """Gibt einen Gespraechszug mit Anweisung an einen eigenen Thread ab --
    der Weg, auf dem ein Knopf zu einem Modellaufruf kommt, ohne selbst
    einen zu machen (Zusage 2).

    ``arbeitszeile`` macht die Wartezeit sichtbar (06.09.2026, 10:10)."""
    from interview_theater import ablauf

    return ablauf.starte_auftrag(
        conn, tg, klm, e, chat_id, anweisung, arbeitszeile,
    ) is not None


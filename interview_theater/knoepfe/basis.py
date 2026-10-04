"""Die Grundleiste und ihre Bausteine -- die Schicht, auf der alles steht.

Hier liegen die vier Dinge, die jede Knopfgruppe braucht: die Umrechnung
zwischen Knopf-id und ``callback_data`` (``_daten`` / ``_id_aus_daten``, an
der Zusage 1 haengt), die **Grundleiste** unter jeder Vorschlagsnachricht
("Eigene Idee" - "Passt, aber anders" - "Gefaellt uns, weiter") samt Menue
und Rueckspiegelung, der Speicherweg dahinter (``_speichere``,
``offene_art``, ``_ist_bestaetigung``) und der Weg vom Knopf zu einem
Modellaufruf, der nicht im Handler stattfindet (``_starte_auftrag``,
Zusage 2).

Aufrufe **nach oben** -- in die Fragen, die Figuren, die Szenen -- gibt es
genau vier, und sie stehen als lokaler Import in der jeweiligen Funktion:
sonst waere die Schicht keine.
"""

from interview_theater import erkenner, phasen, repo

from interview_theater.knoepfe.texte import (
    ART_ANDERS, ART_BOARD_UEBERNEHMEN, ART_EIGENE, ART_KERNTHEMA, ART_PHASE,
    ART_SPEICHERN, ART_UNDO,
    MAX_AUSWAHL, MAX_VORSCHLAEGE, MENUE_KNOPF_LAENGE, PRAEFIX, TRENNER,
    _AUSWAHLMARKER, _FELD_FUER, T, log,
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


# --- Angebote -------------------------------------------------------------


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
        tg.sende(chat_id, T._TEXT_KERNTHEMA_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_KERNTHEMA, wert)))
        for wert in vorschlaege
    ]
    _sende_knoepfe(conn, tg, chat_id, T._TEXT_KERNTHEMA_FRAGE, knoepfe)
    return True


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = T._TEXT_WEITER_ZU_KNOPF.format(phase=phasen.bezeichnung(nummer))
    _sende_knoepfe(conn, tg, chat_id, text, [(beschriftung, _daten(knopf_id))])


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
    beschriftung = T._TEXT_WEITER_ZU_KNOPF.format(phase=phasen.bezeichnung(nummer))
    return (beschriftung, _daten(knopf_id))


def _merke_botnachricht(conn, chat_id: int, message_id: int, text: str) -> None:
    """Schreibt eine Knopfnachricht in ``nachricht`` (``ist_bot = 1``) --
    genau wie ``tg.sende`` es ueber ``ablauf.antworte`` tut (06.09.2026,
    Birk 12:05).

    Der Anlass: **alle Vorschlagsmenues fehlten im Gespraechsfenster.** Der
    Bot legte drei Richtungen hin, die Gruppe antwortete darauf -- und im
    naechsten Zug wusste er nichts davon, weil nur ``sende`` mitschrieb und
    ``sende_mit_knoepfen`` nicht. Ein Fehlschlag ist unkritisch und wird nur
    geloggt: die Nachricht steht im Chat, das ist der Betriebspfad."""
    if not message_id or not (text or "").strip():
        return
    try:
        repo.merke_nachricht(
            conn, chat_id, message_id, None, 1, "text", text, repo._jetzt(),
        )
    except Exception:
        log.exception("Knopfnachricht nicht mitgeschrieben, chat_id=%s", chat_id)


def _sende_knoepfe(conn, tg, chat_id: int, text: str, leiste, **kw) -> int:
    """``tg.sende_mit_knoepfen`` plus Mitschrift in ``nachricht``.

    **Der eine Sendeweg fuer Knopfnachrichten** (06.09.2026, Birk 12:05):
    vorher schrieb nur ``tg.sende`` mit, und deshalb fehlten saemtliche
    Vorschlagsmenues im Gespraechsfenster des naechsten Zuges. Wer hier eine
    neue Leiste baut, nimmt diese Funktion und nicht ``tg`` direkt."""
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste, **kw)
    _merke_botnachricht(conn, chat_id, message_id, kw.get("klartext") or text)
    return message_id


def biete_begriffsvorschlag(conn, tg, chat_id: int, begriffe: list[str]) -> int:
    """Der Top-5-Vorschlag nach "Discussion done" (Karte t_4517d4ad, D6):
    die Begriffe als nummerierte Liste und EIN Knopf "Take these". Eine
    Abkuerzung, nie ein Zwang -- der Text sagt, dass die Gruppe ihre fuenf
    auch selbst schicken kann. Der Wert steht in der Tabelle ``knopf``
    (Zusage 1), gespeichert wird beim Druck ueber ``_speichere`` (Zusage 2:
    kein Modellaufruf)."""
    liste = "\n".join(f"{nr}. {begriff}" for nr, begriff in enumerate(begriffe, 1))
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_BOARD_UEBERNEHMEN, ", ".join(begriffe))
    message_id = _sende_knoepfe(
        conn, tg, chat_id, T._TEXT_BOARD_VORSCHLAG.format(liste=liste),
        [(T._TEXT_BOARD_UEBERNEHMEN_KNOPF, _daten(knopf_id))],
    )
    repo.merke_knopf_nachricht(conn, [knopf_id], message_id)
    return message_id


def _reduziere_auf_undo(tg, chat_id, message_id, undo) -> None:
    """Laesst von einer ueberholten Leisten-Nachricht **nur den Undo-Knopf**
    stehen (Karte U), statt die Tastatur ganz abzunehmen.

    Der Grund: der Undo-Knopf dieser Nachricht ist der einzige Weg, ihren Wert
    zurueckzunehmen -- er darf nicht verschwinden, nur weil eine neue Leiste
    kommt. Die Speicher-Knoepfe daneben muessen weg (der Wert steckt im Knopf,
    und ein Druck auf die alte Leiste speicherte den ueberholten Vorschlag).

    Fehlschlaege werden geschluckt wie in ``_entferne_tastatur``: die Knoepfe
    sind in der Datenbank schon verfallen, die Tastatur zeigt es nur an."""
    try:
        tg.aktualisiere_knoepfe(
            chat_id, message_id,
            [(T._TEXT_UNDO_KNOPF, _daten(k["id"])) for k in undo],
        )
    except Exception:
        log.warning("Leiste auf Undo reduzieren fehlgeschlagen, chat_id=%s", chat_id)


def _nimm_alte_leiste_ab(conn, tg, chat_id: int, art: str) -> None:
    """Nimmt die Tastatur einer aelteren, ungedrueckten Speicher-Leiste
    derselben Art ab, bevor eine neue kommt.

    Warum: der Wert steckt im Knopf, nicht im Text. Nach drei Vorschlaegen
    staenden sonst drei Leisten im Chat, und ein Druck auf die von vor zwei
    Nachrichten speicherte den ueberholten Vorschlag -- genau die Sorte
    stiller Fehler, gegen die die Knoepfe angetreten sind. Die alten
    Knopfzeilen werden zusaetzlich als benutzt gestempelt
    (``repo.verfallen_lassen``), damit sie auch dann nicht mehr wirken, wenn
    die App die Tastatur noch einen Moment zeigt.

    **Traegt die Nachricht einen unbenutzten Undo-Knopf** (Karte U), wird ihre
    Tastatur auf ihn allein reduziert statt ganz abgenommen: er ist der einzige
    Weg, den Wert dieser Meldung zurueckzunehmen.

    Verfallen gelassen werden dabei **alle** Nicht-Undo-Knoepfe dieser
    Nachrichten, nicht nur die der uebergebenen ``art``. Zwei Gruende: eine
    ueberholte Leisten-Nachricht soll keinen einzigen lebenden Speicher-Knopf
    behalten, und ``sende_notiert_mit_leiste`` ruft diese Funktion dreimal
    hintereinander -- ohne das liefe der zweite und dritte Aufruf in ein
    ``editMessageReplyMarkup`` mit unveraenderter Tastatur, und Telegram
    antwortet darauf mit 400."""
    _nimm_leisten_ab(conn, tg, chat_id, repo.offene_knoepfe(conn, chat_id, art))


def _nimm_leisten_ab(conn, tg, chat_id: int, alte) -> None:
    """Der Rumpf von ``_nimm_alte_leiste_ab`` fuer eine schon gelesene Liste
    offener Knoepfe (``repo.offene_knoepfe``) -- herausgezogen (Padua Phasen
    TEIL 2, Abschlussreview): eine Abnahme aus dem Chat
    (``ueberarbeitung.nimm_ab``) liest die Leiste VOR der Wirkung und nimmt
    nach der Wirkung genau diese Nachrichten ab, nicht die gerade neu
    gekommene. Dieselbe Regel wie oben: alle Nicht-Undo-Knoepfe dieser
    Nachrichten verfallen, ein Undo-Knopf bleibt allein stehen."""
    if not alte:
        return
    nachrichten = list(dict.fromkeys(k["message_id"] for k in alte))
    offen = [
        k for message_id in nachrichten
        for k in repo.offene_knoepfe_der_nachricht(conn, chat_id, message_id)
    ]
    repo.verfallen_lassen(conn, [k["id"] for k in offen if k["art"] != ART_UNDO])
    for message_id in nachrichten:
        undo = [
            k for k in offen
            if k["message_id"] == message_id and k["art"] == ART_UNDO
        ]
        if undo:
            _reduziere_auf_undo(tg, chat_id, message_id, undo)
        else:
            _entferne_tastatur(tg, chat_id, message_id)


def speicherleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die **Rueckspiegelung EINES Wertes**: "Ja, speichern" · "Nein,
    nochmal aendern" (06.09.2026, Birk 11:00 -- vorher die dreiteilige
    Grundleiste "Eigene Idee · Passt, aber anders · Gefaellt uns, weiter").

    ``wert`` ist der Text aus dem Vorschlagsblock (``vorschlag.lies``) --
    exakt der, der beim Druck gespeichert wird. Nichts wird hier
    umformuliert, gekuerzt oder ergaenzt: was die Gruppe im Chat liest, ist
    was in der Datenbank landet.

    **Genau zwei Knoepfe, und nur EINER speichert.** Die Leiste steht unter
    einer Rueckspiegelung ("ihr habt Mira, Selin und Nour genannt --
    speichern?"), also unter genau einem fixen Wert: dann ist Ja/Nein die
    ehrliche Frage. "Nein, nochmal aendern" schreibt nichts und macht den
    Weg frei (``ART_EIGENE``); der naechste Beitrag der Gruppe ist die neue
    Fassung.

    Der Volltext steht in der Tabelle ``knopf``, nie in ``callback_data``
    (Zusage 1 im Moduldocstring) -- eine Begriffsliste sprengt die 64 Bytes
    muehelos."""
    speichern = repo.lege_knopf_an(
        conn, chat_id, ART_SPEICHERN, f"{art}{TRENNER}{wert}"
    )
    # "Nein, nochmal aendern" speichert seit dem 02.10.2026 VORLAEUFIG (Birk,
    # Padua): ``ART_ANDERS`` mit demselben Wert wie "Ja". Ausnahme Figuren:
    # die Liste legt Figurenzeilen an, ein zweiter Entwurf liesse die
    # verworfenen Namen als Dubletten stehen -- dort bleibt "Nein" ohne
    # Schreiben (``ART_EIGENE``).
    if art == "figuren":
        nochmal = repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)
    else:
        nochmal = repo.lege_knopf_an(conn, chat_id, ART_ANDERS, f"{art}{TRENNER}{wert}")
    return [
        (T._TEXT_SPEICHERN_KNOPF, _daten(speichern)),
        (T._TEXT_ANDERS_KNOPF, _daten(nochmal)),
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
    """Ein Knopf je Option eines Menue-Blocks (``VORSCHLAG RICHTUNGEN:`` und
    Verwandte).

    Beschriftung seit dem 06.09.2026 (Birk, 11:05): ``"1 · <Titel>"``,
    hoechstens ``MENUE_KNOPF_LAENGE`` Zeichen -- die Nummer verbindet Knopf
    und Text, der Titel macht ihn lesbar. **Gespeichert wird weiterhin die
    ganze Zeile** (Titel und Beschreibung): die Beschriftung ist Anzeige,
    der ``wert`` in der Tabelle ``knopf`` ist der Inhalt.

    Der Volltext steht wie ueberall in der Tabelle ``knopf``; in
    ``callback_data`` steht nur die id (Zusage 1)."""
    from interview_theater import vorschlag

    art = _AUSWAHLMARKER[marker]
    leiste: list[tuple[str, str]] = []
    zeilen = vorschlag.zeilen(wert)[:MAX_AUSWAHL]
    titel = [t for t, _ in vorschlag.optionen(wert)][:MAX_AUSWAHL]
    for nummer, zeile in enumerate(zeilen, start=1):
        kopf = titel[nummer - 1] if nummer - 1 < len(titel) else zeile
        beschriftung = f"{nummer} · {kopf}"[:MENUE_KNOPF_LAENGE]
        leiste.append(
            (beschriftung, _daten(repo.lege_knopf_an(conn, chat_id, art, zeile)))
        )
    return leiste


def _erster_block(text: str, bloecke: dict[str, str]) -> str:
    """Welche Vorschlagsart im TEXT zuerst steht -- deterministisch.

    ``vorschlag.alle`` liefert ein dict; dessen Reihenfolge ist zwar seit
    Python 3.7 die Einfuegereihenfolge, aber hier soll das nicht implizit
    sein, sondern gemessen: gesucht wird die Position der Markerzeile."""
    from interview_theater import vorschlag

    def position(art: str) -> int:
        stelle = (text or "").upper().find(vorschlag.marker(art).upper())
        return stelle if stelle >= 0 else 10**9

    return min(bloecke, key=position)


def _sende_menue(conn, tg, chat_id: int, text: str, marker: str,
                 wert: str) -> tuple[int, bool]:
    """Fall 1 der Knopfregel: ein **Optionen-Menue** (06.09.2026, Birk).

    Im Text nummerierte Optionen mit fettem Titel und Beschreibung darunter
    (``vorschlag.menuetext``, HTML mit Escaping und Rueckfall auf Klartext),
    als Knoepfe ``"1 · Titel"`` ... und darunter ``"Anders"``. **Kein
    Sammelknopf**: bei mehreren Optionen gibt es nichts, das \"alle\"
    speichern koennte -- genau daran nahm die alte Grundleiste still den
    ersten Vorschlag."""
    from interview_theater import vorschlag

    oben = _auswahlleiste(conn, chat_id, marker, wert)
    if not oben:
        return tg.sende(chat_id, vorschlag.ohne_marker(text) or text), False
    oben.append(
        (
            T._TEXT_MENUE_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, marker)),
        )
    )
    vorspann = vorschlag.ohne_block(text, marker)
    html, klar = vorschlag.menuetext(vorspann, wert)
    message_id = _sende_knoepfe(conn, tg, chat_id, html, oben, parse_mode="HTML", klartext=klar
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in oben], message_id)
    return message_id, True


def _sende_rueckspiegelung(conn, tg, chat_id: int, sauber: str, marker: str,
                           wert: str) -> tuple[int, bool]:
    """Fall 2 der Knopfregel, Menue-Variante: **ein** Vorschlag statt zwei
    bis vier -- dann ist es kein Menue, sondern eine Rueckspiegelung.

    "Ja, speichern" traegt dieselbe Knopf-Art wie eine Option des Menues
    (``_AUSWAHLMARKER``) und wirkt deshalb genauso; "Nein, nochmal aendern"
    speichert nichts.

    Steht hinter dem Marker ein Arbeitsstand-Feld (``_NOTIERT`` -- Rahmen,
    Kernthema), laeuft der Druck ueber ``ART_SPEICHERN``: nur dieser Weg
    traegt die Kette danach weiter (``_kette_weiter``: Setting -> Anzahl der
    Figuren, Kernthema -> Kernfrage)."""
    if marker in T._NOTIERT:
        leiste = speicherleiste(conn, chat_id, marker, wert)
        message_id = _sende_knoepfe(conn, tg, chat_id, sauber, leiste)
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        return message_id, True
    art = _AUSWAHLMARKER[marker]
    leiste = [
        (
            T._TEXT_SPEICHERN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, wert)),
        ),
        (
            T._TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, marker)),
        ),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, sauber, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id, True


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
    das Modell die Form eingehalten hat.

    Zwei Bloecke verschiedener Arten in einer Nachricht raeumt
    ``_ein_feld_je_nachricht`` vorher auf, den Wert der Grundleiste sucht
    ``_leistenwert``."""
    from interview_theater import vorschlag

    text, bloecke = _ein_feld_je_nachricht(conn, chat_id, text)
    sauber = vorschlag.ohne_marker(text) or text

    # Der Fragenvorschlag der Phase 2 (02.10.2026) ist keine Leiste, sondern
    # ein eigener Ueberblick mit Richtungsfrage -- er kommt VOR allem
    # anderen, weil er den Text mitbringt und nichts direkt speichert. Die
    # weiche Fassung (``VORSCHLAG FRAGEN WEICH:``) reist, falls vorhanden,
    # aus DEMSELBEN Modellzug mit (``_ein_feld_je_nachricht`` laesst dieses
    # eine Paar durch).
    if "fragenauswahl" in bloecke:
        from interview_theater.knoepfe.fragen import biete_fragenauswahl

        rest = vorschlag.ohne_block(text, "fragenauswahl", "fragen_weich")
        return biete_fragenauswahl(
            conn, tg, chat_id, bloecke["fragenauswahl"],
            bloecke.get("fragen_weich"), rest or T._TEXT_FRAGEN_RICHTUNG_FRAGE,
        ), True

    # Die Antwort auf eine Schaerfung (02.10.2026): ``VORSCHLAG FRAGE:``
    # ersetzt genau die eine gerade offene Frage -- kein Vorspann-Text, keine
    # Grundleiste, die Frage wird deterministisch neu gezeigt.
    if "frage" in bloecke:
        from interview_theater.knoepfe.fragen import uebernimm_schaerfung

        return uebernimm_schaerfung(
            conn, tg, chat_id, bloecke["frage"], bloecke.get("fragen_weich"),
        ), True

    # Die eigenen Fragen der Gruppe (Padua Phase 1+2 Karte, Aufgabe 13,
    # 03.10.2026, KORREKTUR-PHASE2-KEIN-KNOPF.md): ``VORSCHLAG EIGENE
    # FRAGEN:`` ist kein Angebot, sondern die laufende, vollstaendige
    # Zusammenfassung dessen, was die Gruppe selbst schon gesagt hat --
    # jede Zeile "Begriff: Frage". Kein Vorspann-Text, keine Grundleiste:
    # der Code prueft nach jedem Speichern, ob jeder Begriff genug eigene
    # Fragen hat, und meldet entweder den Stand oder startet automatisch die
    # Gegenueberstellung mit den KI-Fragen.
    if "eigene_fragen" in bloecke:
        from interview_theater.knoepfe.fragen import uebernimm_eigene

        rest = vorschlag.ohne_block(text, "eigene_fragen")
        return uebernimm_eigene(
            conn, tg, chat_id, bloecke["eigene_fragen"], rest,
        ), True

    # Oben: die Auswahlknoepfe. Kommen mehrere Auswahl-Bloecke in einer
    # Nachricht (das Modell soll das nicht, tut es aber gelegentlich),
    # gewinnt der erste aus _AUSWAHLMARKER -- eine feste Ordnung statt einer
    # zufaelligen aus dem Text.
    marker = next((m for m in _AUSWAHLMARKER if m in bloecke), None)

    art, wert = _leistenwert(conn, chat_id, bloecke)

    if marker is None and (not art or not wert):
        return tg.sende(chat_id, sauber), False

    if marker is not None:
        # Fall 1 der Knopfregel: ein Optionen-Menue. Nummerierte Optionen mit
        # fettem Titel im Text, "1 · Titel" ... als Knoepfe, "Anders"
        # darunter -- und KEIN Sammelknopf, der etwas speichert.
        if len(vorschlag.zeilen(bloecke[marker])) == 1:
            # Ein einziger Vorschlag ist kein Menue, sondern eine
            # Rueckspiegelung: dann Ja/Nein (Birk, 06.09.2026 11:00 --
            # "ein Wert → Ja/Nein; 2-4 Werte → Menue").
            return _sende_rueckspiegelung(
                conn, tg, chat_id, sauber, marker,
                vorschlag.zeilen(bloecke[marker])[0],
            )
        return _sende_menue(conn, tg, chat_id, text, marker, bloecke[marker])

    if art == "figuren":
        # Figuren sind zweistufig (05.09.2026 abends): Ebene 1 ist die Liste
        # mit "Anzahl aendern" und "Namen aendern" -- ein eigener Weg, kein
        # Sonderfall der Grundleiste.
        from interview_theater.knoepfe.figuren import biete_figurenliste

        return biete_figurenliste(conn, tg, chat_id, wert, sauber), True

    if art == "geschichte":
        # Die Geschichte traegt Bogen, Ende UND die Szenenfolge; sie geht
        # deshalb ueber ihren eigenen Speicherweg (``_speichere_geschichte``)
        # und nicht ueber den Arbeitsstand-Setter -- sonst staende der
        # Vorschlagstext als ein Feld da und keine Szene in der Tabelle.
        from interview_theater.knoepfe.szenen import sende_geschichte

        return sende_geschichte(conn, tg, chat_id, text), True

    return _sende_mit_grundleiste(conn, tg, chat_id, sauber, art, wert)


def _sende_mit_grundleiste(
    conn, tg, chat_id: int, sauber: str, art: str, wert: str,
) -> tuple[int, bool]:
    """Fall 2 der Knopfregel: die Rueckspiegelung EINES Wertes. Begriffe,
    Fragen, Einleitungen sind mehrzeilig, aber EIN Wert -- deshalb Ja/Nein und
    kein Menue.

    Die alten Leisten kommen vorher ab, damit im Chat nur eine bedienbar
    ist."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_EIGENE)
    leiste = speicherleiste(conn, chat_id, art, wert)
    message_id = _sende_knoepfe(conn, tg, chat_id, sauber, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


#: Blockpaare, die zusammen EINE Entscheidung tragen (02.10.2026,
#: Phase-2-Umbau "Fragen einzeln"): der Fragenvorschlag samt seinen weichen
#: Fassungen aus demselben Modellzug, und eine geschaerfte Einzelfrage
#: ebenso. ``_ein_feld_je_nachricht`` wirft die weiche Fassung sonst als
#: "zweites Thema in derselben Nachricht" weg.
_ERLAUBTE_BLOCKPAARE = (
    frozenset({"fragenauswahl", "fragen_weich"}),
    frozenset({"frage", "fragen_weich"}),
)


def _ein_feld_je_nachricht(conn, chat_id: int, text: str) -> tuple[str, dict]:
    """**Ein Feld je Nachricht** (06.09.2026, Birk 11:00): enthaelt eine
    Antwort zwei Vorschlagsbloecke VERSCHIEDENER Arten, geht nur der erste
    raus, der zweite wird verworfen (Vorfall ``vorschlag_mehrere_arten``).
    Zwei Themen in einer Nachricht heissen: die Gruppe beantwortet eines und
    das andere verfaellt.

    Liefert den (gegebenenfalls gekuerzten) Text und seine Bloecke."""
    from interview_theater import vorschlag

    bloecke = vorschlag.alle(text)
    if len(bloecke) <= 1 or frozenset(bloecke) in _ERLAUBTE_BLOCKPAARE:
        return text, bloecke
    # Deterministisch: die Reihenfolge im TEXT entscheidet, nicht die
    # eines dicts -- der erste Block im Text ist der, den das Modell
    # gemeint hat, alles danach gehoert in eine eigene Nachricht.
    erster = _erster_block(text, bloecke)
    verworfen = [a for a in bloecke if a != erster]
    repo.merke_vorfall(
        conn, chat_id, None, "vorschlag_mehrere_arten",
        "Zwei Vorschlagsbloecke in einer Nachricht: "
        f"'{erster}' gesendet, {verworfen} verworfen",
    )
    for art_weg in verworfen:
        text = vorschlag.ohne_block(text, art_weg)
    return text, {erster: bloecke[erster]}


def _leistenwert(conn, chat_id: int, bloecke: dict) -> tuple[str | None, str | None]:
    """Welchen ``(art, wert)`` traegt die Grundleiste unter dieser Nachricht?

    Den Block der gerade offenen Art (``offene_art``). Findet sich keiner,
    kommt ``(art, None)`` oder ``(None, None)`` zurueck: **kein Raten**.

    ``_ERSTER_ALS_WERT`` ist am 06.09.2026 leergeraeumt worden (Birk): bei
    mehreren Optionen wird NIE still die erste genommen."""
    art = offene_art(conn, chat_id)
    wert = bloecke.get(art) if art else None
    if art == "fragen_weich" and wert is None and "einleitungen" in bloecke:
        # Der alte Weg bleibt begehbar (06.09.2026, 10:18): liefert ein
        # Modell noch ``VORSCHLAG EINLEITUNGEN:`` -- weil der Prompt-Umbau
        # den laufenden Zug einer Gruppe nicht ruecklaeufig aendert --,
        # traegt die Leiste diesen Block. Sonst staende die Antwort ohne
        # Knoepfe da, und die Stufe waere nicht abzunehmen.
        art, wert = "einleitungen", bloecke["einleitungen"]
    return art, wert


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
        # Seit dem Umbau auf "Fragen einzeln" (02.10.2026) laeuft der
        # Fragenvorschlag und seine Sensibilitaetspruefung ueber einen
        # eigenen Ueberblick samt Frage-fuer-Frage-Stufe
        # (``knoepfe.fragen``), nicht mehr ueber die Grundleiste -- die
        # einzige verbleibende Stufe hier ist Eroeffnung und Abschluss, und
        # nur, sobald die Frageliste wirklich steht (eine Gruppe, die noch
        # mitten im Vorschlag ist, hat ``fragen`` noch leer).
        if not leer("fragen") and leer("interview_eroeffnung"):
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
                             wert: str, zusatz=()) -> tuple[int, bool]:
    """Die \"Notiert:\"-Meldung des Erkenners MIT der Grundleiste darunter.

    Der Anlass (Birk, Live-Befund Testgruppe 05.09.2026, 23:37): der
    Erkenner-Nachlauf laeuft NACH der Gespraechsantwort. Speichert er in
    Phase 4 oder 5 eine Ping-Pong-Art, stand die Grundleiste unter der
    Antwort davor -- also unter einem Text, der den Wert noch gar nicht
    kannte, waehrend die Nachricht mit dem Wert nackt dastand. Jetzt haengt
    sie dort, wo der Wert steht: \"Passt, aber anders\" schaerft nach,
    \"Gefaellt uns, weiter\" fixiert, \"Eigene Idee\" macht den Weg frei.

    Die alte Leiste wird abgenommen (``_nimm_alte_leiste_ab``), damit nicht
    zwei im Chat stehen und die aeltere den ueberholten Wert speichert.

    ``zusatz`` haengt weitere Knopfzeilen UNTER die Grundleiste -- gebraucht
    fuer den Undo-Knopf (Karte U), der als ruhiger Nebenknopf zuletzt steht.
    Vorgabe leer, damit jeder bestehende Aufruf unveraendert gueltig bleibt."""
    for alte in (ART_SPEICHERN, ART_ANDERS, ART_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, alte)
    leiste = speicherleiste(conn, chat_id, art, wert) + list(zusatz)
    # UX-Knoepfe-Karte, Abschnitt 3: "Notiert: ..." ist eine Quittung, keine
    # Aeusserung des Bots -- auch mit einer Grundleiste darunter.
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste, system=True)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


def undo_leiste(conn, chat_id: int, lauf_id: int | None) -> list[tuple[str, str]]:
    """Der EINE ruhige Undo-Knopf zu einem Erkennerlauf -- oder eine leere
    Leiste, wenn es keinen Lauf gibt (Karte U, 01.10.2026).

    Eine Meldung, eine Ruecknahme: der Knopf traegt die ``erkenner_lauf.id``
    im ``wert`` der Knopfzeile, nie in ``callback_data`` (Zusage 1). Eine
    Einzelauswahl ("nur das Kernthema, nicht die Figur") gibt es bewusst
    nicht -- sie waere eine Liste dort, wo die Gruppe einen Fehler wegtippen
    will."""
    if lauf_id is None:
        return []
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_UNDO, str(lauf_id))
    return [(T._TEXT_UNDO_KNOPF, _daten(knopf_id))]


def sende_notiert_nur_undo(conn, tg, chat_id: int, text: str, lauf_id: int,
                           leiste=None) -> int:
    """Die "Notiert:"-Meldung mit dem Undo-Knopf als einziger Zeile -- der Weg
    fuer alle Phasen, in denen keine Grundleiste darunter gehoert.

    Aus ``tg.sende`` wird damit ``_sende_knoepfe``: dieselbe Mitschrift in
    ``nachricht`` wie bei jeder anderen Knopfnachricht (06.09.2026, Birk
    12:05), und ``merke_knopf_nachricht`` haelt fest, unter welcher Nachricht
    der Knopf haengt.

    ``leiste`` reicht eine schon gebaute ``undo_leiste`` durch (Review-Fix
    Aufgabe 7): hat der Aufrufer die Knopfzeile bereits angelegt, entstuende
    hier sonst eine zweite, nie gezeigte -- eine verwaiste, offene Undo-Zeile
    je Meldung."""
    if leiste is None:
        leiste = undo_leiste(conn, chat_id, lauf_id)
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste, system=True)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


# --- Phase 6 · Szenen: Angebote -------------------------------------------


def grundleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die **Rueckspiegelung EINES Wertes** in den spaeten Phasen:
    "Ja, speichern" · "Nein, nochmal aendern" (06.09.2026, Birk 11:00 --
    vorher drei Knoepfe).

    ``art`` ist die Knopf-Art, unter der gespeichert wird
    (``ART_SZENENFOLGE_SPEICHERN``, ``ART_SZENENFELDER_SPEICHERN``), ``wert``
    der Text, der beim Druck wirkt -- exakt der, der im Chat steht. Nichts
    wird hier umformuliert (dieselbe Zusage wie in ``speicherleiste``).

    Nur **einer** speichert: "Ja". "Nein, nochmal aendern" schreibt nichts
    und macht den Weg frei -- der naechste Beitrag der Gruppe ist die neue
    Fassung."""
    return [
        (
            T.TEXT_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"weiter{TRENNER}{wert}")),
        ),
        # Seit 02.10.2026 (Birk, Padua) speichert auch "Nein" -- vorlaeufig,
        # ueber dieselbe Art mit Modus "anders".
        (
            T.TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"anders{TRENNER}{wert}")),
        ),
    ]


def _mit_leiste(conn, tg, chat_id: int, text: str, leiste: list[tuple[str, str]]) -> int:
    """Schickt ``text`` mit ``leiste`` und merkt sich die Nachricht je Knopf --
    damit eine spaetere Leiste die alte abnehmen kann
    (``_nimm_alte_leiste_ab``)."""
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
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
    if art not in T._NOTIERT:
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
               nur_bestaetigen: bool = False, uebergang: bool = False,
               klm=None, e=None) -> str:
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
        return T._TEXT_UNBEKANNT

    if art == "figuren":
        from interview_theater.knoepfe.figuren import _uebernimm_figurenliste

        return _uebernimm_figurenliste(conn, tg, chat_id, wert)

    if art not in T._NOTIERT:
        log.error("Speicher-Knopf mit unbekannter art %r, chat_id=%s", art, chat_id)
        return T._TEXT_UNBEKANNT

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
        tg.sende(chat_id, T._TEXT_SCHON_GESETZT, system=True)
        return T._TEXT_SCHON_GESETZT

    def _schreibe():
        feld = _FELD_FUER.get(art, art)
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)
        if feld == "begriffe":
            # Karte t_4517d4ad (D7) -- innerhalb von ``lauf_fuer_knopf``, damit
            # die Ruecknahme das Detail mit zuruecknimmt.
            from interview_theater import begriffsboard

            begriffsboard.schreibe_detail(conn, chat_id, wert)
        if weiterfrage:
            # Abgenommen: die offene Aenderungsbitte ist erledigt, die Leiste
            # verschwindet wieder (``offene_art``).
            repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)

    text = T._TEXT_NOTIERT_ZEILE.format(feld=T._NOTIERT[art], wert=wert)
    # Derselbe Undo-Knopf wie unter jeder automatischen Erkenner-Meldung
    # (Karte U) -- UX-Knoepfe-Karte, Abschnitt 2: "Ja, speichern" schreibt
    # ueber dieselben repo-Funktionen wie der Erkenner, bekommt also auch
    # dieselbe Ruecknahme, keine zweite Maschine.
    lauf_id = erkenner.lauf_fuer_knopf(conn, e, chat_id, text, _schreibe)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"{T._NOTIERT[art]}: {wert}", quelle="knopf",
    )
    if lauf_id is None:
        tg.sende(chat_id, text, system=True)
    else:
        sende_notiert_nur_undo(conn, tg, chat_id, text, lauf_id)
    # Danach die eine Frage, die den Zwischenraum offenhaelt -- und darunter,
    # wenn die Materiallage es hergibt, der Weg weiter
    # (``phasen.voraussetzungen``): der Knopf sagt, was jetzt dran ist,
    # statt dass jemand raten muss.
    #
    # ``uebergang`` (02.10.2026, Birk, Padua; KORREKTUR 18:20, Kommentar 807):
    # "Ja, speichern" fixiert UND geht DIREKT AUTOMATISCH in die naechste
    # Phase weiter, sobald die Materiallage sie hergibt -- keine zweite
    # Auswahl, kein "Weiter zu ..."-Angebot an dieser Stelle (das waere die
    # Hotfix-Variante aus B5, die hier NICHT gilt -- B5 bleibt allein am
    # Erkenner-Pfad, ``erkenner._sende_meldung``, wo die Gruppe noch nicht
    # geklickt hat). Ausgenommen sind die Fragen: an ihnen haengt die Kette
    # Sensibilitaet -> Einleitungen -> Eroeffnung, und erst deren Ja
    # schliesst Phase 2 ab.
    if weiterfrage and uebergang and art != "fragen":
        from interview_theater.knoepfe.stationen import uebergang_nach_speichern

        if uebergang_nach_speichern(conn, tg, klm, e, chat_id):
            return T._TEXT_FELD_UEBERNOMMEN.format(feld=T._NOTIERT[art])
    if weiterfrage:
        phasenknopf = _phasenknopf(conn, chat_id)
        if phasenknopf is not None:
            _sende_knoepfe(conn, tg, chat_id, T._TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
        else:
            tg.sende(chat_id, T._TEXT_NACH_SPEICHERN_FRAGE)
    return T._TEXT_FELD_UEBERNOMMEN.format(feld=T._NOTIERT[art])


def _starte_auftrag(conn, tg, klm, e, chat_id: int, anweisung: str,
                    arbeitszeile: str | None = None,
                    arbeitsart: str | None = None) -> bool:
    """Gibt einen Gespraechszug mit Anweisung an einen eigenen Thread ab --
    der Weg, auf dem ein Knopf zu einem Modellaufruf kommt, ohne selbst
    einen zu machen (Zusage 2).

    ``arbeitszeile`` macht die Wartezeit sichtbar (06.09.2026, 10:10)."""
    from interview_theater import ablauf

    return ablauf.starte_auftrag(
        conn, tg, klm, e, chat_id, anweisung, arbeitszeile, arbeitsart,
    ) is not None

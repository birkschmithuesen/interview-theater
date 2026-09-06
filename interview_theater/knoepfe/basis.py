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

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ART_ANDERS, ART_EIGENE, ART_KERNTHEMA, ART_PHASE, ART_SPEICHERN,
    MAX_AUSWAHL, MAX_VORSCHLAEGE, MENUE_KNOPF_LAENGE, PRAEFIX,
    TEXT_ANDERS_KNOPF, TEXT_WEITER_KNOPF, TRENNER, _AUSWAHLMARKER, _FELD_FUER,
    _NOTIERT, _TEXT_ANDERS_KNOPF, _TEXT_FRAGEN_WAHL, _TEXT_KERNTHEMA_FRAGE,
    _TEXT_KERNTHEMA_KEINE, _TEXT_MENUE_ANDERS_KNOPF,
    _TEXT_NACH_SPEICHERN_FRAGE, _TEXT_SCHON_GESETZT, _TEXT_SPEICHERN_KNOPF,
    _TEXT_UNBEKANNT, log,
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
        tg.sende(chat_id, _TEXT_KERNTHEMA_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_KERNTHEMA, wert)))
        for wert in vorschlaege
    ]
    _sende_knoepfe(conn, tg, chat_id, _TEXT_KERNTHEMA_FRAGE, knoepfe)
    return True


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = f"Weiter zu {phasen.knopfbezeichnung(nummer)}"
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
    return (f"Weiter zu {phasen.knopfbezeichnung(nummer)}", _daten(knopf_id))


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
    nochmal = repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)
    return [
        (_TEXT_SPEICHERN_KNOPF, _daten(speichern)),
        (_TEXT_ANDERS_KNOPF, _daten(nochmal)),
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
            _TEXT_MENUE_ANDERS_KNOPF,
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
    if marker in _NOTIERT:
        leiste = speicherleiste(conn, chat_id, marker, wert)
        message_id = _sende_knoepfe(conn, tg, chat_id, sauber, leiste)
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        return message_id, True
    art = _AUSWAHLMARKER[marker]
    leiste = [
        (
            _TEXT_SPEICHERN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, wert)),
        ),
        (
            _TEXT_ANDERS_KNOPF,
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


def _ein_feld_je_nachricht(conn, chat_id: int, text: str) -> tuple[str, dict]:
    """**Ein Feld je Nachricht** (06.09.2026, Birk 11:00): enthaelt eine
    Antwort zwei Vorschlagsbloecke VERSCHIEDENER Arten, geht nur der erste
    raus, der zweite wird verworfen (Vorfall ``vorschlag_mehrere_arten``).
    Zwei Themen in einer Nachricht heissen: die Gruppe beantwortet eines und
    das andere verfaellt.

    Liefert den (gegebenenfalls gekuerzten) Text und seine Bloecke."""
    from interview_theater import vorschlag

    bloecke = vorschlag.alle(text)
    if len(bloecke) <= 1:
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
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


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
            TEXT_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"weiter{TRENNER}{wert}")),
        ),
        (
            TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)),
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
            _sende_knoepfe(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
        else:
            tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
    return f"{_NOTIERT[art]} uebernommen"


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

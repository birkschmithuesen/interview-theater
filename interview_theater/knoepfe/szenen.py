"""Phasen 5 bis 8: Geschichte, Schaerfung, Szenentexte, Durchlauf.

Die laengste Kette im Paket, und sie folgt ueberall derselben Form: ein
Vorschlag steht als Text im Chat, darunter haengen Knoepfe, und der Knopf
traegt die Entscheidung selbst -- Szenenfolge (``sende_szenenfolge``),
Geschichte (``sende_geschichte``, ``biete_kurzgeschichte``), Schaerfung am
Material (``biete_schaerfung``), die Szene mit ihrer Form, ihrem Stil und
ihren Feldern (``biete_szene``, ``biete_szenenform``, ``biete_szenenstil``),
die Stueckpruefung (``zeige_stueckpruefung``) und der Durchlauf mit dem
Textbuch und dem Link auf die Probenansicht (``biete_durchlauf``,
``probenansicht_zeile``).

Kein Modellaufruf steht hier: was eines braucht, geht ueber
``szenenfolge.py``, ``schaerfung.py``, ``stueckpruefung.py``,
``kurzgeschichte.py`` oder ``szene.py`` in einen eigenen Thread.
"""

from interview_theater import repo

from interview_theater.knoepfe.texte import (
    ART_DRAMATURGIE, ART_DRAMATURGIE_LASSEN, ART_DRAMATURGIE_SZENE,
    ART_DURCHLAUF_SZENE, ART_EIGENE, ART_FASSUNGEN, ART_GESCHICHTE_ANDERS,
    ART_GESCHICHTE_NEU,
    ART_GESCHICHTE_PASST, ART_GESCHICHTE_SCHREIBEN, ART_GESCHICHTE_SPEICHERN,
    ART_PRUEFUNG_LASSEN, ART_PRUEFUNG_RUNDE, ART_PRUEFUNG_SZENE,
    ART_SCHAERFUNG_FIGUR, ART_SCHAERFUNG_KEINE, ART_SCHAERFUNG_RUNDE,
    ART_SCHAERFUNG_STELLE, ART_SCHAERFUNG_SZENE, ART_SZENENFELDER_SPEICHERN,
    ART_SZENENFOLGE_ANZAHL, ART_SZENENFOLGE_REIHENFOLGE,
    ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM, ART_SZENENSTIL,
    ART_SZENE_ANDERS, ART_SZENE_FORM, ART_SZENE_NAECHSTE, ART_SZENE_NEU,
    ART_SZENE_PASST, ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN,
    ART_SZENE_SO_LASSEN, ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA,
    ART_SPRECHANTEILE, ART_TEXTBUCH,
    MAX_AUSWAHL, MENUE_KNOPF_LAENGE, TEXT_ANDERS_KNOPF, TEXT_ANZAHL_KNOPF,
    TEXT_DRAMATURGIE_KNOPF,
    TEXT_DURCHLAUF_SZENE_KNOPF, TEXT_EIGENE_IDEE_KNOPF, TEXT_FASSUNGEN_KNOPF,
    TEXT_FORM_VORSCHLAG_ZUSATZ, TEXT_GESCHICHTE_SCHREIBEN_KNOPF,
    TEXT_NAECHSTE_KNOPF, TEXT_NEU_KNOPF, TEXT_PASST_KNOPF,
    TEXT_REIHENFOLGE_KNOPF, TEXT_SCHAERFUNG_RUNDE_KNOPF, TEXT_SPRECHANTEILE_KNOPF,
    TEXT_SZENE_FORM_KNOPF,
    TEXT_SZENE_PLANEN_KNOPF, TEXT_SZENE_SCHREIBEN_KNOPF,
    TEXT_SZENE_SO_LASSEN_KNOPF, TEXT_SZENE_UEBERSPRINGEN_KNOPF,
    TEXT_TEXTBUCH_KNOPF, TRENNER, _TEXT_ANDERS, _TEXT_EIGENE_IDEE,
    _TEXT_DRAMATURGIE_LAEUFT, _TEXT_DRAMATURGIE_LASSEN_KNOPF,
    _TEXT_FASSUNGEN_KOPF, _TEXT_FASSUNG_KOPF,
    _TEXT_FOLGE_GESPEICHERT, _TEXT_FOLGE_LEER, _TEXT_GESCHICHTE_ANDERS_KNOPF,
    _TEXT_GESCHICHTE_GESPEICHERT, _TEXT_GESCHICHTE_LEER,
    _TEXT_GESCHICHTE_NEU_KNOPF, _TEXT_GESCHICHTE_PASST_KNOPF,
    _TEXT_KEINE_FASSUNGEN, _TEXT_NUR_FORMWAHL,
    _TEXT_KEINE_NAECHSTE, _TEXT_MENUE_ANDERS_KNOPF, _TEXT_NACH_SPEICHERN_FRAGE,
    _TEXT_PROBENANSICHT, _TEXT_PRUEFUNG_LAEUFT, _TEXT_PRUEFUNG_LASSEN_KNOPF,
    _TEXT_PRUEFUNG_RUNDE_KNOPF, _TEXT_PRUEFUNG_SZENE_KNOPF,
    _TEXT_RICHTUNG_GESPEICHERT, _TEXT_SCHAERFUNG_ALLE_KNOPF,
    _TEXT_SCHAERFUNG_DURCH, _TEXT_SCHAERFUNG_KEINE_KNOPF,
    _TEXT_SCHAERFUNG_LAEUFT, _TEXT_SPAETERE_GEPRUEFT, _TEXT_SZENENFORM_FRAGE,
    _TEXT_SZENE_OHNE_TEXT, _TEXT_SZENE_UNBEKANNT, _TEXT_UNBEKANNT,
    _TEXT_USA_FRAGE_KNOEPFE, _TEXT_USA_JA_KNOPF, _TEXT_USA_NEIN_KNOPF, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _mit_leiste, _nimm_alte_leiste_ab, _phasenknopf,
    _sende_knoepfe, grundleiste,
)


def biete_szenenform(conn, tg, chat_id: int, nummer: int, text: str | None = None,
                     zeile=None) -> int:
    """Bietet die sechs Formen fuer EINE Szene als Knoepfe an (05.09.2026).

    Warum hier ein Knopf: 553e3aa stellt die Form je Szene in phasen/6.md als
    nummerierte Auswahl. Dieselbe Schwaeche wie beim Format -- "nimm das
    dritte" ist fuer den Erkenner nicht aufloesbar, und eine falsch geratene
    Form fuehrt zu einem Szenentext nach den falschen Dramaturgieregeln
    (``prompts/formen/<name>.md``).

    Die Szenennummer MUSS mitwandern, sonst wuesste der Knopfdruck nicht,
    welche Szene gemeint ist. Sie steht dafuer im ``wert`` der Knopfzeile
    ("3:dialog"), nicht in ``callback_data`` -- dort steht wie ueberall nur
    die Knopf-id. Damit bleibt die 64-Byte-Grenze unabhaengig von Nummer und
    Formnamen eingehalten.

    Die Liste kommt aus ``szene.FORMEN`` und wird hier NICHT zweitgepflegt:
    kommt dort eine Form dazu, gibt es den Knopf automatisch.

    Gibt es einen Formvorschlag aus der Szenenfolge (``form_vorschlag``,
    06.09.2026), steht er ZUERST und traegt "(Vorschlag)" -- darueber eine
    Zeile Begruendung (``form_vorschlag_grund``). Er ist damit sichtbar ein
    Vorschlag und keine Vorentscheidung: gesetzt wird die Form durch den
    Druck, und nur durch ihn."""
    from interview_theater import szene

    reihenfolge = list(szene.FORMEN)
    vorschlag_form = ""
    zusatz = ""
    if zeile is not None:
        vorschlag_form = (zeile["form_vorschlag"] or "").strip().lower()
        if vorschlag_form in reihenfolge:
            reihenfolge.remove(vorschlag_form)
            reihenfolge.insert(0, vorschlag_form)
        grund = (zeile["form_vorschlag_grund"] or "").strip()
        if grund:
            zusatz = "\n\n" + grund

    knoepfe = [
        (
            form.capitalize() + (TEXT_FORM_VORSCHLAG_ZUSATZ if form == vorschlag_form
                                 else ""),
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFORM, f"{nummer}:{form}")),
        )
        for form in reihenfolge
    ]
    frage = text or _TEXT_SZENENFORM_FRAGE.format(nummer=nummer)
    return _mit_leiste(conn, tg, chat_id, frage + zusatz, knoepfe)


def biete_szenenstil(conn, tg, chat_id: int, nummer: int) -> int:
    """Die Stil-Auswahl fuer EINE Szene -- **eine** Nachricht, alle Stile,
    jeder mit Titel, einem Satz und der Herkunft (06.09.2026, Birk 12:50).

    Birk im Wortlaut: *"alle Gruppen sollen auf alle Stile zugreifen koennen,
    als Auswahl, mit Nennung des Originalmaterials."* Bis dahin hing ein Stil
    am Bot (eine Overlay-Datei je Gruppe) und war damit nicht waehlbar.

    Gebaut als Optionen-Menue nach der Regel vom 06.09.2026, 11:05: der Text
    traegt die nummerierten Optionen, die Knoepfe tragen ``"N · Titel"``,
    hoechstens ``MENUE_KNOPF_LAENGE`` Zeichen -- Knopf N und Punkt N meinen
    dasselbe, weil beide aus ``stile.reihenfolge_mit_vorschlag`` kommen.

    Steht sie nach der Form (``ART_SZENENFORM``), gibt es einen **Vorschlag**
    passend zur Form samt Begruendung. Er ist ein Vorschlag: gesetzt wird der
    Stil allein durch den Druck -- dieselbe Regel wie beim Formvorschlag."""
    from interview_theater import stile

    zeile = repo.hole_szene(conn, repo.stelle_szene_sicher(conn, chat_id, nummer))
    form = (zeile["form"] or "").strip().lower() if zeile is not None else ""
    vorschlag, grund = stile.vorschlag_fuer(form)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENENSTIL)
    leiste = [
        (
            f"{n} · {eintrag['titel']}"[:MENUE_KNOPF_LAENGE],
            _daten(
                repo.lege_knopf_an(
                    conn, chat_id, ART_SZENENSTIL, f"{nummer}:{eintrag['slug']}"
                )
            ),
        )
        for n, eintrag in enumerate(
            stile.reihenfolge_mit_vorschlag(vorschlag), start=1
        )
    ]
    leiste.append(
        (
            stile.TEXT_OHNE,
            _daten(
                repo.lege_knopf_an(
                    conn, chat_id, ART_SZENENSTIL, f"{nummer}:{stile.OHNE}"
                )
            ),
        )
    )
    return _mit_leiste(conn, tg, chat_id, stile.menuetext(vorschlag, grund), leiste)


def biete_szene_usa(conn, tg, chat_id: int, text: str | None = None) -> None:
    """Haengt die beiden Einwilligungsknoepfe unter das USA-Angebot
    (``szene._TEXT_ANGEBOT_USA``).

    Der Anlass ist der teuerste gemessene Fehler des 05.09.2026: der Bot
    fragte nach dem US-Modell, die Gruppe antwortete siebenmal sinngemaess
    "ja" -- der Erkenner las es jedes Mal als Zustimmung zu den FIGUREN, und
    der Bot wiederholte dieselbe Erinnerung, bis der Notausgang
    (``szene.USA_ERINNERUNGEN_MAX``) griff und in der Schweiz schrieb. Eine
    Einwilligung ist genau der Fall, der nicht erraten werden darf: hier
    entscheidet die Gruppe ueber eine Datenuebermittlung.

    Zwei Knoepfe und nicht einer: anders als beim Aufnahme-Umschalter sind
    Ja und Nein zwei verschiedene Entscheidungen mit verschiedenen Folgen,
    und ein Nein muss genauso ein Druck sein wie ein Ja -- sonst waere
    Schweigen die einzige Form der Ablehnung."""
    knoepfe = [
        (_TEXT_USA_JA_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "ja"))),
        (_TEXT_USA_NEIN_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "nein"))),
    ]
    _sende_knoepfe(conn, tg, chat_id, text or _TEXT_USA_FRAGE_KNOEPFE, knoepfe)


def sende_szenenfolge(conn, tg, chat_id: int, antwort: str) -> int:
    """Der Szenenfolge-Vorschlag im Chat: der Text ohne Markerzeilen, darunter
    "Anzahl aendern" · "Reihenfolge aendern" und die Grundleiste.

    Ohne Marker (``vorschlag.lies``) gibt es KEINE Leiste -- kein Raten:
    lieber ein Vorschlag ohne Knoepfe als Knoepfe, die den falschen Text
    speichern (dieselbe Regel wie in ``sende_mit_speicherleiste``). Die Gruppe
    kann dann immer noch frei antworten; das wirkt ohnehin immer."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "szenenfolge")
    if not wert:
        log.error("Szenenfolge-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENENFOLGE_SPEICHERN)
    leiste = [
        (
            TEXT_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_ANZAHL, None)),
        ),
        (
            TEXT_REIHENFOLGE_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_REIHENFOLGE, None)
            ),
        ),
    ] + grundleiste(conn, chat_id, ART_SZENENFOLGE_SPEICHERN, wert)
    return _mit_leiste(conn, tg, chat_id, sauber, leiste)


def sende_geschichte(conn, tg, chat_id: int, antwort: str) -> int:
    """Die **drei Richtungen** der Geschichte als Optionen-Menue (Phase 4,
    06.09.2026, Birk 11:42).

    Bis dahin trug ein ``VORSCHLAG GESCHICHTE:``-Block Bogen, Ende UND die
    ganze Szenenfolge -- eine Entscheidung ueber alles auf einmal, mit einer
    Grundleiste, die still den ersten Vorschlag nahm. Jetzt sind es drei
    Richtungen, je fetter Titel und zwei bis drei Saetze, als Menue mit
    Knoepfen "1 · Titel" … und "Anders". Die Szenenfolge kommt erst NACH der
    Wahl, als eigener Vorschlag mit Ja/Nein
    (``szenenfolge.starte_geschichte_szenen``).

    Ohne Marker keine Leiste, kein Raten -- dieselbe Regel wie ueberall.
    Enthaelt der Block nur EINE Zeile (das Modell hat sich nicht an die drei
    gehalten), ist es eine Rueckspiegelung: Ja/Nein statt Menue."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "geschichte")
    if not wert:
        log.error("Geschichte-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_GESCHICHTE_SPEICHERN)
    from interview_theater import szenenfolge

    # Woran der alte Block erkennbar ist: seine ZWEITE Zeile beginnt mit
    # "Ende:" (Bogen, Ende, dann je Szene eine Zeile). Drei Richtungen haben
    # keine solche Zeile -- und genau daran haengt die Unterscheidung, nicht
    # an der Zeilenzahl: drei Szenen und drei Richtungen saehen sonst gleich
    # aus.
    zeilen_roh = vorschlag.zeilen(wert)
    alter_block = len(zeilen_roh) > 1 and szenenfolge._ENDE_PRAEFIX.match(zeilen_roh[1])
    _, szenenzeilen = szenenfolge.zerlege_geschichte(wert)
    if alter_block and szenenzeilen:
        # Der alte Weg bleibt begehbar: liefert ein Modell noch Bogen, Ende
        # UND Szenenfolge in einem Block (ein laufender Zug sieht den neuen
        # Prompt nicht rueckwirkend), bleibt es bei einer Entscheidung mit
        # Anzahl, Reihenfolge und Ja/Nein.
        leiste = [
            (
                TEXT_ANZAHL_KNOPF,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_ANZAHL, None)),
            ),
            (
                TEXT_REIHENFOLGE_KNOPF,
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_SZENENFOLGE_REIHENFOLGE, None
                    )
                ),
            ),
        ] + grundleiste(conn, chat_id, ART_GESCHICHTE_SPEICHERN, wert)
        return _mit_leiste(conn, tg, chat_id, sauber, leiste)
    richtungen = vorschlag.zeilen(wert)[:MAX_AUSWAHL]
    titel = [t for t, _ in vorschlag.optionen(wert)][:MAX_AUSWAHL]
    if len(richtungen) == 1:
        leiste = grundleiste(conn, chat_id, ART_GESCHICHTE_SPEICHERN, richtungen[0])
        return _mit_leiste(conn, tg, chat_id, sauber, leiste)
    leiste = []
    for nummer, zeile in enumerate(richtungen, start=1):
        kopf = titel[nummer - 1] if nummer - 1 < len(titel) else zeile
        leiste.append(
            (
                f"{nummer} · {kopf}"[:MENUE_KNOPF_LAENGE],
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_GESCHICHTE_SPEICHERN,
                        f"weiter{TRENNER}{zeile}",
                    )
                ),
            )
        )
    leiste.append(
        (
            _TEXT_MENUE_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, "geschichte")),
        )
    )
    html, klar = vorschlag.menuetext(
        vorschlag.ohne_block(antwort, "geschichte"), wert
    )
    message_id = _sende_knoepfe(conn, tg, chat_id, html, leiste, parse_mode="HTML", klartext=klar
    )
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id
    )
    return message_id


# --- Phase 6 · Schaerfung am Material -------------------------------------


def biete_schaerfung(conn, tg, chat_id: int) -> bool:
    """Stellt die naechste offene Schaerfung als **Menue** vor -- erst Szene
    fuer Szene, dann Figur fuer Figur. Liefert True, solange noch eine kam.

    Bis zum 06.09.2026 war das hier der einzige Auswahl-Moment, der NICHT
    ueber ``vorschlag.menuetext`` lief: ein Fliessblock mit vollstaendigen
    Zitaten und **zwei** Knoepfen fuer alles (Analyse Abschnitt 2, gemessene
    Bloecke von 712 und 1280 Zeichen). Jetzt dieselbe Bauweise wie ueberall
    sonst: Ueberschrift, hoechstens ``schaerfung.MAX_STELLEN`` nummerierte
    Kurzoptionen, **ein Knopf je Stelle** (Knopf N und Punkt N meinen
    dasselbe, siehe ``stile.reihenfolge_mit_vorschlag``), darunter "Diese
    uebernehmen" und "Keine davon".

    Deterministisch aus der Datenbank -- kein Modellaufruf im Handler
    (Zusage 2). Die ``callback_data`` traegt nur ``k:<id>`` (Zusage 1); was
    gemeint ist, steht im ``wert`` der Knopfzeile.

    Ist nichts mehr offen, steht die Frage nach einer weiteren Runde da und,
    wenn die Materiallage sie hergibt, der Weg zu den Szentexten."""
    from interview_theater import schaerfung as schaerfung_modul

    for szene in repo.hole_szenen(conn, chat_id):
        stellen = schaerfung_modul.offene_stellen(
            conn, chat_id, szene_id=szene["id"]
        )
        if not stellen:
            continue
        _sende_schaerfungsmenue(
            conn, tg, chat_id,
            schaerfung_modul.szenenueberschrift(conn, chat_id, szene),
            stellen, ART_SCHAERFUNG_SZENE, str(szene["nummer"]),
        )
        return True
    for figur in repo.figuren(conn, chat_id):
        stellen = schaerfung_modul.offene_stellen(
            conn, chat_id, figur_id=figur["id"]
        )
        if not stellen:
            continue
        _sende_schaerfungsmenue(
            conn, tg, chat_id,
            schaerfung_modul.figurueberschrift(figur),
            stellen, ART_SCHAERFUNG_FIGUR, figur["name"],
        )
        return True
    leiste = [
        (
            TEXT_SCHAERFUNG_RUNDE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHAERFUNG_RUNDE, None)),
        )
    ]
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        leiste.append(phasenknopf)
    _mit_leiste(conn, tg, chat_id, _TEXT_SCHAERFUNG_DURCH, leiste)
    return False


def _sende_schaerfungsmenue(
    conn, tg, chat_id: int, ueberschrift: str, stellen: list,
    sammelart: str, sammelwert: str,
) -> int:
    """Ein Schaerfungs-Menue: je Stelle ein Knopf, darunter die zwei
    Sammelknoepfe.

    Die Reihenfolge der Knoepfe ist die Reihenfolge der Punkte -- ``stellen``
    wird genau einmal durchlaufen und speist beides."""
    from interview_theater import schaerfung as schaerfung_modul, vorschlag

    zeilen: list[str] = []
    leiste: list[tuple[str, str]] = []
    for nummer, eintrag in enumerate(stellen, start=1):
        titel, beschreibung = schaerfung_modul.option(conn, chat_id, eintrag)
        zeilen.append(f"{titel} — {beschreibung}".strip(" —"))
        leiste.append(
            (
                f"{nummer} · {titel}"[:MENUE_KNOPF_LAENGE],
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_SCHAERFUNG_STELLE, str(eintrag["id"])
                    )
                ),
            )
        )
    leiste.append(
        (
            _TEXT_SCHAERFUNG_ALLE_KNOPF,
            _daten(
                repo.lege_knopf_an(
                    conn, chat_id, sammelart, f"weiter{TRENNER}{sammelwert}"
                )
            ),
        )
    )
    leiste.append(
        (
            _TEXT_SCHAERFUNG_KEINE_KNOPF,
            _daten(
                repo.lege_knopf_an(
                    conn, chat_id, ART_SCHAERFUNG_KEINE,
                    TRENNER.join(str(z["id"]) for z in stellen),
                )
            ),
        )
    )
    html, klar = vorschlag.menuetext(ueberschrift, "\n".join(zeilen))
    message_id = _sende_knoepfe(
        conn, tg, chat_id, html, leiste, parse_mode="HTML", klartext=klar
    )
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id
    )
    return message_id


def starte_schaerfung(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst das Mapping an (im Thread) und stellt danach die erste
    Schaerfung vor -- der automatische Eintritt in Phase 6.

    Kein Modellaufruf hier: ``schaerfung.starte`` gibt sofort ab (Zusage 2).
    Ohne Sprachmodell (Tests) bleibt der Weg trotzdem offen -- dann wird
    gezeigt, was schon zugeordnet ist.

    **``_TEXT_SCHAERFUNG_LAEUFT`` nur, wenn die Sperre wirklich frei war**
    (30.09.2026, widerspruechliche Meldungen): haelt ein anderer
    Vorschlagslauf die gemeinsame Sperre, schickt ``schaerfung.starte``
    selbst ``TEXT_GEMERKT`` -- ein vorab gesendetes \"gleich\" waere dann eine
    zweite, sich widersprechende Zeile im selben Chatfenster. Kein
    Modellaufruf: ``vorschlagssperre.laeuft`` ist eine reine Abfrage."""
    from interview_theater import schaerfung as schaerfung_modul
    from interview_theater import vorschlagssperre

    def _danach() -> None:
        biete_schaerfung(conn, tg, chat_id)

    frei = not vorschlagssperre.laeuft(chat_id)
    if frei:
        tg.sende(chat_id, _TEXT_SCHAERFUNG_LAEUFT)
    if schaerfung_modul.starte(conn, tg, klm, e, chat_id, nachbereitung=_danach) is None:
        biete_schaerfung(conn, tg, chat_id)


def starte_stueckpruefung(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst die Pruefung des ganzen Stuecks an (im Thread) -- der
    automatische EINE Lauf beim Eintritt in Phase 7.

    Kein Modellaufruf hier: ``stueckpruefung.starte`` gibt sofort ab
    (Zusage 2). Ohne Sprachmodell (Tests) bleibt der Weg still offen; dann
    zeigt ``zeige_stueckpruefung`` das, was schon dasteht."""
    from interview_theater import stueckpruefung as pruefung_modul

    tg.sende(chat_id, _TEXT_PRUEFUNG_LAEUFT)
    pruefung_modul.starte(conn, tg, klm, e, chat_id)


def probenansicht_zeile(conn, e, chat_id: int) -> str:
    """Die Zeile mit dem Link auf ``/g/<token>/textbuch``, oder "".

    Ohne ``IT_WEB_URL`` (``e.web_url``) gibt es keine Weboberflaeche und
    also auch keinen Link -- das ist kein Fehlerfall, sondern der Zustand
    eines Bots ohne Webserver daneben. Der Weg zum Token ist derselbe wie in
    der Begruessung und in ``/stand`` (``repo.gruppenseite_url``), damit es
    nicht zwei Arten gibt, dieselbe URL zu bauen."""
    basis = getattr(e, "web_url", "") if e is not None else ""
    if not basis:
        return ""
    url = repo.gruppenseite_url(conn, chat_id, basis)
    return _TEXT_PROBENANSICHT.format(url=f"{url}/textbuch") if url else ""


def zeige_stueckpruefung(
    conn, tg, chat_id: int, runde: int | None = None, e=None
) -> int:
    """Die Befunde EINER Runde: je Frage eine Nachricht mit "Szene N
    ueberarbeiten" und "Lassen", darunter die Abschlussleiste mit "Noch eine
    Pruefrunde", "Textbuch als Datei" und einem Knopf je Szene.

    Deterministisch aus der Datenbank, kein Modellaufruf (Zusage 2) -- der
    Lauf ist gelaufen, hier wird nur vorgestellt. Liefert die Zahl der
    verschickten Befund-Nachrichten."""
    from interview_theater import stueckpruefung as pruefung_modul

    if runde is None:
        runde = repo.letzte_pruefrunde(conn, chat_id)
    if not runde:
        return 0
    zeilen = repo.stueckpruefungen(conn, chat_id, runde=runde)
    if not zeilen:
        return 0
    tg.sende(chat_id, pruefung_modul.MELDUNG_KOPF.format(runde=runde))
    verschickt = 0
    for zeile in zeilen:
        leiste = []
        if zeile["szene_nummer"] is not None and (zeile["vorschlag"] or "").strip():
            leiste.append(
                (
                    _TEXT_PRUEFUNG_SZENE_KNOPF.format(nummer=zeile["szene_nummer"]),
                    _daten(
                        repo.lege_knopf_an(
                            conn, chat_id, ART_PRUEFUNG_SZENE, str(zeile["id"])
                        )
                    ),
                )
            )
        leiste.append(
            (
                _TEXT_PRUEFUNG_LASSEN_KNOPF,
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_PRUEFUNG_LASSEN, str(zeile["id"])
                    )
                ),
            )
        )
        message_id = _sende_knoepfe(conn, tg, chat_id, pruefung_modul.befundtext(zeile), leiste
        )
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        verschickt += 1
    biete_nach_pruefung(conn, tg, chat_id, runde, e)
    return verschickt


def biete_nach_pruefung(conn, tg, chat_id: int, runde: int, e=None) -> int:
    """Die Abschlussleiste unter den Befunden: "Noch eine Pruefrunde",
    "Textbuch als Datei" und ein Knopf je Szene ("Szene N ansehen").

    Mit ``e`` steht darueber die Zeile mit dem Link zur Probenansicht
    (06.09.2026) -- neben dem Datei-Knopf, nicht an seiner Stelle."""
    from interview_theater import szenenfolge

    leiste = [
        (
            _TEXT_PRUEFUNG_RUNDE_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_PRUEFUNG_RUNDE, str(runde))
            ),
        ),
        (
            TEXT_TEXTBUCH_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEXTBUCH, None)),
        ),
        # Die feinkoernige Ebene daneben (06.09.2026): der Stueck-Judge sagt
        # "Spannungsbogen 3/5", die Dramaturgie-Pruefung sagt "Szene 4 endet,
        # wie sie anfaengt" -- mit Zitat und Szenennummer. Zwei Fragen, zwei
        # Knoepfe; angeboten wird beides, gedrueckt wird, was die Gruppe will.
        (
            TEXT_DRAMATURGIE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_DRAMATURGIE, None)),
        ),
    ]
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None:
            continue
        leiste.append(
            (
                TEXT_DURCHLAUF_SZENE_KNOPF.format(nummer=s["nummer"]),
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_DURCHLAUF_SZENE, str(s["nummer"])
                    )
                ),
            )
        )
    text = szenenfolge.uebersicht(conn, chat_id) + probenansicht_zeile(conn, e, chat_id)
    return _mit_leiste(conn, tg, chat_id, text, leiste)


def _pruefbefund(conn, chat_id: int, befund_id: int):
    """Der Befund mit dieser id, oder None -- ueber ``repo``, damit das
    weiche Loeschen an einer Stelle bleibt."""
    return next(
        (z for z in repo.stueckpruefungen(conn, chat_id) if z["id"] == befund_id),
        None,
    )



# --- Phase 7 - Dramaturgie-Pruefung (06.09.2026) --------------------------


def starte_dramaturgie(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst die Dramaturgie-Pruefung an (im Thread).

    Kein Modellaufruf hier: ``dramaturgie.fanout.starte`` gibt sofort ab
    (Zusage 2)."""
    from interview_theater.dramaturgie import fanout

    tg.sende(chat_id, _TEXT_DRAMATURGIE_LAEUFT)
    fanout.starte(conn, tg, klm, e, chat_id)


def zeige_dramaturgie(conn, tg, chat_id: int, runde: int | None = None) -> int:
    """Die Befunde EINER Dramaturgie-Runde: je Befund eine Zeile mit
    Szenennummer, und je Ueberarbeitungsauftrag ein Knopf "Szene N so
    ueberarbeiten".

    **Der Bot schlaegt vor, er handelt nicht.** Kein automatisches
    Neuschreiben; erst der Knopfdruck loest einen Szenenlauf aus -- dieselbe
    Haltung wie ueberall im Repo: Datenstand ist nicht Absicht.

    **Ohne Belegzitat im Chat.** Das Zitat ist der Nachweis fuer den Code;
    dass es geprueft wurde, ist die Zusage, nicht seine Anzeige.

    Deterministisch aus der Datenbank, kein Modellaufruf (Zusage 2). Liefert
    die Zahl der verschickten Befund-Nachrichten."""
    from interview_theater.dramaturgie import fanout

    if runde is None:
        runde = repo.letzte_dramaturgie_runde(conn, chat_id)
    if not runde:
        return 0
    zeilen = repo.dramaturgie_befunde(conn, chat_id, runde=runde)
    if not zeilen:
        tg.sende(chat_id, fanout.MELDUNG_OHNE_BEFUND)
        return 0
    figuren = [f["name"] for f in repo.figuren(conn, chat_id)]
    auftraege = {a["befund_id"]: a for a in fanout.auftraege(zeilen, figuren)}

    tg.sende(chat_id, fanout.MELDUNG_KOPF.format(runde=runde))
    verschickt = 0
    for zeile in zeilen:
        text = fanout.befundzeile(zeile)
        if zeile["id"] not in auftraege:
            tg.sende(chat_id, text)
            verschickt += 1
            continue
        leiste = [
            (
                fanout.TEXT_AUFTRAG_KNOPF.format(nummer=zeile["szene"]),
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_DRAMATURGIE_SZENE, str(zeile["id"])
                    )
                ),
            ),
            (
                _TEXT_DRAMATURGIE_LASSEN_KNOPF,
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_DRAMATURGIE_LASSEN, str(zeile["id"])
                    )
                ),
            ),
        ]
        message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        verschickt += 1
    return verschickt


def sende_szenenfelder(conn, tg, chat_id: int, nummer: int, antwort: str) -> int:
    """Der Feldvorschlag fuer EINE Szene, mit der Grundleiste darunter.

    Der ``wert`` traegt die Szenennummer mit (\"3|form: Lied\\nort: ...\"):
    zwischen Vorschlag und Druck kann die Gruppe laengst ueber eine andere
    Szene reden, und ein Feldvorschlag, der in der falschen Szene landet, ist
    schlimmer als keiner."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "szene")
    if not wert:
        log.error("Feldvorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENENFELDER_SPEICHERN)
    leiste = grundleiste(
        conn, chat_id, ART_SZENENFELDER_SPEICHERN, f"{nummer}{TRENNER}{wert}"
    )
    return _mit_leiste(conn, tg, chat_id, sauber, leiste)


def biete_szene(conn, tg, chat_id: int, zeile) -> int:
    """Stellt EINE Szene vor und haengt ihr Menue darunter: "Passt,
    schreiben" · "Anders planen" · "Form aendern" · "Ueberspringen" ·
    "Eigene Idee".

    Deterministisch aus der Datenbank (``szenenfolge.vorstellung``) -- kein
    Modellaufruf. Das Menue kommt nach jeder Aenderung neu: jeder der Knoepfe,
    der etwas an der Szene aendert, ruft am Ende wieder hierher zurueck.

    Steht ein Pruef-Vermerk an dieser Szene (an einer frueheren Szene wurde
    etwas geaendert, ``szenenfolge.zu_pruefen``), sind es zwei andere
    Knoepfe: "Neu schreiben" und "So lassen". Das ist die Frage, die dann
    ansteht -- "Ueberspringen" und "Form aendern" waeren daneben Rauschen.

    **Ist die Form noch nicht bestaetigt, kommt zuerst die Formfrage**
    (Birk, 06.09.2026 00:30: "Die Form Monolog habe ich niemals eingegeben
    und aktiv bestaetigt. Die Form muss mit mehr Bedacht gewaehlt werden und
    vom User bestaetigt werden."). Der Vorschlag des Bots steht dabei als
    erster Knopf mit "(Vorschlag)"; die Schreibfrage kommt erst nach dem
    Druck. Ohne bestaetigte Form wird nicht geschrieben
    (``szene.PFLICHTFELDER``)."""
    from interview_theater import szene as szene_modul, szenenfolge

    nummer = zeile["nummer"]
    # **In Phase 6 entfaellt die Formfrage** (06.09.2026, 10:30, Birk): dort
    # entsteht die Szene als Geschichte, und was daraus wird -- Dialog,
    # Monolog, Rap, Lied --, entscheidet die Gruppe erst im Feinschliff
    # (Phase 7). ``form`` bleibt solange NULL, ``form_vorschlag`` ist eine
    # Notiz fuer dann.
    if not (zeile["form"] or "").strip() and not szene_modul.schreibt_prosa(
        conn, chat_id
    ):
        return biete_szenenform(conn, tg, chat_id, nummer, zeile=zeile)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENE_SCHREIBEN)
    if szenenfolge.zu_pruefen(conn, chat_id, nummer):
        leiste = [
            (
                TEXT_NEU_KNOPF,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NEU, str(nummer))),
            ),
            (
                TEXT_SZENE_SO_LASSEN_KNOPF,
                _daten(
                    repo.lege_knopf_an(conn, chat_id, ART_SZENE_SO_LASSEN, str(nummer))
                ),
            ),
        ]
        return _mit_leiste(
            conn, tg, chat_id, szenenfolge.vorstellung(conn, zeile, chat_id), leiste
        )
    leiste = [
        (
            TEXT_SZENE_SCHREIBEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_SCHREIBEN, str(nummer))),
        ),
        (
            TEXT_SZENE_PLANEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_PLANEN, str(nummer))),
        ),
        (
            TEXT_SZENE_FORM_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_FORM, str(nummer))),
        ),
        (
            TEXT_SZENE_UEBERSPRINGEN_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_SZENE_UEBERSPRINGEN, str(nummer))
            ),
        ),
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_EIGENE, ART_SZENE_SCHREIBEN)
            ),
        ),
    ]
    return _mit_leiste(conn, tg, chat_id, szenenfolge.vorstellung(conn, zeile), leiste)


def biete_nach_szenentext(conn, tg, chat_id: int, nummer: int, text: str) -> int:
    """Die vier Knoepfe unter einem frisch geschriebenen Szenentext: "Passt" ·
    "Passt, aber anders" · "Neu schreiben" · "Naechste Szene".

    Der Anlass (Birk, 05.09.2026): der Szenentext stand im Chat, und danach
    passierte nichts -- die Gruppe wusste nicht, ob sie zustimmen, aendern
    oder weitergehen soll, und der Bot wusste nicht, ob die Szene gilt.
    Deshalb traegt "Passt" seit heute einen eigenen Stempel in der Datenbank
    (``repo.setze_szene_fertig``) und nicht bloss das Vorhandensein eines
    Textes.

    Ist es die letzte Szene und sind alle fertig, steht statt "Naechste
    Szene" der Weg weiter: "Weiter zu Durchlauf" -- ohne Nummer, wie jeder
    Phasenknopf hier."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENE_PASST)
    leiste = [
        (
            TEXT_PASST_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_PASST, str(nummer))),
        ),
        (
            TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_ANDERS, str(nummer))),
        ),
        (
            TEXT_NEU_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NEU, str(nummer))),
        ),
        (
            TEXT_NAECHSTE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NAECHSTE, str(nummer))),
        ),
    ]
    return _mit_leiste(conn, tg, chat_id, text, leiste)


def biete_durchlauf(conn, tg, chat_id: int, e=None) -> int:
    """Der Eintritt in Phase 7 (Schaerfung des Stuecks): die Szenenfolge mit Status als Text, darunter
    ein Knopf je Szene, "Textbuch als Datei" und "Eigene Idee".

    Alles deterministisch aus der Datenbank. Der Durchlauf ist eine Ansicht
    auf das, was die Gruppe gebaut hat -- kein Anlass, ein Modell zu fragen.

    Mit ``e`` steht unter der Uebersicht die Zeile mit dem Link zur
    Probenansicht (06.09.2026): die Datei nimmt man mit, die Seite liest man
    in der Probe. Beides, nicht eines statt des anderen."""
    from interview_theater import szenenfolge

    leiste = []
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None:
            continue
        leiste.append(
            (
                TEXT_DURCHLAUF_SZENE_KNOPF.format(nummer=s["nummer"]),
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_DURCHLAUF_SZENE, str(s["nummer"])
                    )
                ),
            )
        )
    leiste.append(
        (
            TEXT_TEXTBUCH_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEXTBUCH, None)),
        )
    )
    # "Wer spricht wie viel" (06.09.2026): der Durchlauf ist die Stelle, an
    # der die Gruppe das Stueck als Ganzes ansieht -- und die einzige, an der
    # die Frage nach den Sprechanteilen im Chat einen Ort hat. Reine
    # Zaehlung, kein Modellaufruf.
    leiste.append(
        (
            TEXT_SPRECHANTEILE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SPRECHANTEILE, None)),
        )
    )
    leiste.append(
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, ART_TEXTBUCH)),
        )
    )
    text = szenenfolge.uebersicht(conn, chat_id) + probenansicht_zeile(conn, e, chat_id)
    return _mit_leiste(conn, tg, chat_id, text, leiste)


# --- Phase 6 · Szenentexte: Wirkungen ------------------------------------------


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    """Die (nicht entfernte) Szene mit dieser Nummer, oder None."""
    return next(
        (s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == nummer), None
    )


def zeige_szenentext(conn, tg, chat_id: int, nummer: int) -> str:
    """Der Volltext EINER Szene, deterministisch aus der Datenbank -- der
    Weg hinter dem Knopf "Szene N ansehen" (Phase 8).

    Seit dem 06.09.2026 (Nacht-Simulation Punkt 7) eine eigene Funktion und
    nicht mehr nur ein Zweig im Knopf-Handler: derselbe Weg wird jetzt auch
    ohne Knopfdruck gegangen, wenn die Gruppe im Chat nach dem Text fragt
    (``ablauf.szenentext_gewuenscht``). Der Grund ist der gemessene: der
    Gespraechs-Bot hat den Volltext gar nicht im Kontext und hat ihn deshalb
    zusammengefasst statt gezeigt. Ein Ort fuer den Text, zwei Ausloeser.

    Liefert die Zeile fuer die Knopfquittung."""
    ziel = _szene_mit_nummer(conn, chat_id, nummer)
    if ziel is None:
        tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    volltext = (ziel["volltext"] or "").strip()
    if not volltext:
        tg.sende(chat_id, _TEXT_SZENE_OHNE_TEXT.format(nummer=nummer))
        return _TEXT_SZENE_OHNE_TEXT.format(nummer=nummer)
    # Der Volltext geht ungekuerzt raus -- lange Texte teilt der
    # Telegram-Wrapper selbst (``telegram.teile_text``).
    kopf = f"Szene {nummer}"
    if ziel["titel"]:
        kopf += f": {ziel['titel']}"
    text = f"{kopf}\n\n{volltext}"
    # Gibt es frueher geschriebene Fassungen, haengt darunter EIN Knopf
    # (06.09.2026). Kein neuer automatischer Text: die Liste kommt erst auf
    # Druck, deterministisch aus der Datenbank. Ohne fruehere Fassung bleibt
    # es bei der Nachricht, die es vorher auch gab.
    if len(repo.szenenfassungen(conn, ziel["id"])) > 1:
        leiste = [(
            TEXT_FASSUNGEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FASSUNGEN, str(nummer))),
        )]
        _mit_leiste(conn, tg, chat_id, text, leiste)
        return f"Szene {nummer}"
    tg.sende(chat_id, text)
    return f"Szene {nummer}"


def _zeige_fassungen(conn, tg, chat_id: int, nummer: int) -> str:
    """Die frueher geschriebenen Fassungen einer Szene, aelteste zuerst.

    Deterministisch aus ``szenenfassung``, kein Modellaufruf (Zusage 2). Die
    aktuelle Fassung bleibt weg -- sie steht in der Nachricht darueber.

    **Zurueckgesetzt wird nichts.** Eine frueherer Fassung wieder zur
    aktuellen zu machen ist eine Entscheidung mit Datenwirkung; hier gibt es
    sie nur zum Lesen, damit die Gruppe in der Probe zwei Fassungen
    nebeneinander halten kann."""
    ziel = _szene_mit_nummer(conn, chat_id, nummer)
    if ziel is None:
        tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    fassungen = repo.szenenfassungen(conn, ziel["id"])[:-1]
    if not fassungen:
        text = _TEXT_KEINE_FASSUNGEN.format(nummer=nummer)
        tg.sende(chat_id, text)
        return text
    teile = [_TEXT_FASSUNGEN_KOPF.format(nummer=nummer)]
    for f in fassungen:
        anders = (f["anders_gemacht"] or "").strip()
        teile.append(
            _TEXT_FASSUNG_KOPF.format(
                nummer=f["nummer"],
                zeit=(f["erstellt_am"] or "")[:16].replace("T", " "),
                anders=f" {anders}" if anders else "",
            )
        )
        teile.append(f["volltext"] or "")
    # Lange Texte teilt der Telegram-Wrapper selbst (``telegram.teile_text``).
    tg.sende(chat_id, "\n\n".join(teile))
    return TEXT_FASSUNGEN_KNOPF


def _naechste_offene(conn, chat_id: int, nach: int):
    """Die naechste Szene nach ``nach``, die noch nicht abgenommen ist -- oder
    None, wenn keine mehr kommt.

    Nicht einfach "die naechste": eine Gruppe, die Szene 2 ueberspringt und
    spaeter zurueckkommt, soll nicht an ihr vorbeigeschickt werden."""
    from interview_theater import szenenfolge

    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is not None and s["nummer"] > nach and not szenenfolge.ist_fertig(s):
            return s
    return None


def _speichere_szenenfolge(conn, tg, klm, e, chat_id: int, roh: str) -> str:
    """Legt aus dem Vorschlag die Szenen an und stellt die erste vor.

    ``roh`` ist ``"<weiter|anders>|<Vorschlagstext>"``. Beide Wege speichern;
    "anders" haengt danach die Frage an, was noch geaendert werden soll -- die
    naechste freie Nachricht wirkt dann ganz normal ueber den Erkenner."""
    from interview_theater import szenenfolge

    modus, _, wert = roh.partition(TRENNER)
    zeilen = szenenfolge.zerlege(wert)
    if not zeilen:
        log.error("Szenenfolge-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_FOLGE_LEER)
        return _TEXT_FOLGE_LEER
    nummern = szenenfolge.lege_an(conn, chat_id, zeilen)
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        "Szenenfolge: " + "; ".join(f"{n}. {z[0]}" for n, z in zip(nummern, zeilen)),
        quelle="knopf",
    )
    tg.sende(chat_id, _TEXT_FOLGE_GESPEICHERT.format(anzahl=len(nummern)))
    if modus.strip() == "anders":
        tg.sende(chat_id, _TEXT_EIGENE_IDEE)
    erste = _szene_mit_nummer(conn, chat_id, nummern[0])
    if erste is not None:
        biete_szene(conn, tg, chat_id, erste)
    return f"{len(nummern)} Szenen uebernommen"


def _uebernimm_formwahl(conn, tg, chat_id: int, wert: str, formen: dict) -> str:
    """Die angetippte Zeile war eine Formwahl je Szene -- **die Wahl wird
    uebernommen, die Geschichte bleibt leer** (06.09.2026, B2).

    Sie abzuweisen und sonst nichts zu tun waere ein zweiter Verlust: die
    Formentscheidung der Gruppe stand am 06.09. nur als Fliesstext in einem
    Feld, das ihr nicht gehoerte, und ``szene.form`` war in **allen 15**
    Zeilen NULL.

    Zwei Ablagen, weil es zwei Lagen gibt: **gibt es die Szene schon**, geht
    die Form in ``szene.form``; **gibt es sie noch nicht** -- und das war der
    Live-Fall, die Formwahl kam vor der Szenenfolge --, geht sie als
    Festlegung in die Auffangtabelle und ist damit im Prompt, bis die Szenen
    entstehen.

    ``szene.form`` und nicht ``form_vorschlag``: die Gruppe hat den Knopf
    **gedrueckt**. Die Regel aus AGENTS.md ("die Form ist ein Vorschlag,
    keine Vorentscheidung") haelt den Vorschlag eines Modells aus dem Feld
    heraus, nicht die Wahl der Gruppe -- gesetzt wird sie durch einen Druck,
    und der ist hier passiert."""
    vorhandene = {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, chat_id)}
    geschrieben = []
    offen = []
    for nummer in sorted(formen):
        szene_id = vorhandene.get(nummer)
        if szene_id is None:
            offen.append(f"Szene {nummer}: {formen[nummer]}")
            continue
        repo.setze_szenenfeld(conn, szene_id, "form", formen[nummer])
        geschrieben.append(f"Szene {nummer}: {formen[nummer]}")
    if offen:
        repo.schreibe_festlegung(
            conn, chat_id, "form", "Form je Szene — " + ", ".join(offen),
            quelle="knopf",
        )
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        "Form je Szene: " + ", ".join(geschrieben + offen), quelle="knopf",
    )
    repo.merke_vorfall(
        conn, chat_id, None, "geschichte_war_formwahl",
        "Eine Formwahl sollte als Geschichte gespeichert werden",
    )
    log.info("Geschichte-Knopf trug eine Formwahl, chat_id=%s: %r", chat_id, wert[:80])
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", "geschichte")
    tg.sende(chat_id, _TEXT_NUR_FORMWAHL)
    return "Formwahl uebernommen, Geschichte fehlt noch"



def _speichere_geschichte(conn, tg, klm, e, chat_id: int, roh: str) -> str:
    """Speichert die GEWAEHLTE RICHTUNG (``arbeitsstand.geschichte``) und
    bietet danach die Szenenfolge an (06.09.2026, Birk 11:42).

    Bis dahin legte dieser Weg in einem Zug auch die Szenen an -- eine
    Entscheidung ueber alles auf einmal. Jetzt ist die Richtung die
    Entscheidung; die Szenenfolge ist der naechste, eigene Schritt
    (``szenenfolge.starte_geschichte_szenen``, eigener Thread -- kein
    Modellaufruf im Knopf-Handler, Zusage 2).

    Der alte Weg bleibt begehbar: liefert ein Modell noch einen Block MIT
    Szenenzeilen (der Prompt-Umbau aendert einen laufenden Zug nicht
    rueckwirkend), werden sie wie bisher angelegt."""
    from interview_theater import szenenfolge

    modus, _, wert = roh.partition(TRENNER)
    zeilen_roh = [z for z in (wert or "").splitlines() if z.strip()]
    alter_block = (
        len(zeilen_roh) > 1 and szenenfolge._ENDE_PRAEFIX.match(zeilen_roh[1].strip())
    )
    geschichte, zeilen = szenenfolge.zerlege_geschichte(wert)
    if not alter_block:
        zeilen = []
    if not geschichte:
        log.error("Geschichte-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_GESCHICHTE_LEER)
        return _TEXT_GESCHICHTE_LEER
    # **Eine Menuezeile ist keine Geschichte** (06.09.2026, B1/B2 der
    # Phase-4-Analyse). Der Kommentar unten benennt die Absicht richtig --
    # sie traegt aber nur, wenn die Menuezeile eine HANDLUNGSrichtung
    # beschreibt. Am 06.09. beschrieb sie eine Formabfolge ueber drei
    # Szenen, und die ganze Zeile landete in ``arbeitsstand.geschichte``:
    # 113 Zeichen Formwahl statt der 665 Zeichen langen, vierteiligen
    # Handlung. Spiegelbildlich zu ``erkenner._ist_geschichte``, das
    # denselben Fehler in der anderen Richtung abfaengt.
    if not zeilen:
        formen = szenenfolge.formabfolge(wert)
        if formen:
            return _uebernimm_formwahl(conn, tg, chat_id, wert, formen)
    # Eine Richtung ist eine Zeile "Titel — Bogen, Ende, Konflikt": sie ist
    # die Geschichte, nicht ihr erster Satz.
    geschichte = wert.strip() if not zeilen else geschichte
    repo.setze_arbeitsstand(conn, chat_id, "geschichte", geschichte)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Geschichte: {geschichte}", quelle="knopf",
    )
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    if zeilen:
        nummern = szenenfolge.lege_an(conn, chat_id, zeilen)
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            "Szenenfolge: "
            + "; ".join(f"{n}. {z[0]}" for n, z in zip(nummern, zeilen)),
            quelle="knopf",
        )
        tg.sende(
            chat_id,
            _TEXT_GESCHICHTE_GESPEICHERT.format(anzahl=len(nummern))
            + "\n" + geschichte,
        )
        if modus.strip() == "anders":
            repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", "geschichte")
            tg.sende(chat_id, _TEXT_ANDERS)
            return "Gespeichert, was soll anders sein?"
        phasenknopf = _phasenknopf(conn, chat_id)
        if phasenknopf is not None:
            _mit_leiste(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
        else:
            tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
        return f"Geschichte mit {len(nummern)} Szenen uebernommen"
    tg.sende(chat_id, _TEXT_RICHTUNG_GESPEICHERT + "\n" + geschichte)
    szenenfolge.starte_geschichte_szenen(conn, tg, klm, e, chat_id)
    return "Richtung uebernommen"


def _speichere_szenenfelder(conn, tg, chat_id: int, roh: str) -> str:
    """Schreibt die vorgeschlagenen Felder in die Szene und stellt sie neu vor.

    ``roh`` ist ``"<nummer>|<Vorschlagstext>"``; der Vorschlagstext ist
    ``feld: Wert`` je Zeile. Gelesen wird ueber ``szene.feldname`` --
    dieselben Aliase wie beim Befehl und beim Erkenner, kein zweites
    Vokabular. Was der Code nicht kennt, wird uebergangen und geloggt: ein
    unbekanntes Feld ist kein Grund, die uebrigen wegzuwerfen."""
    from interview_theater import szene as szene_modul

    roh_nummer, _, wert = roh.partition(TRENNER)
    try:
        nummer = int(roh_nummer)
    except ValueError:
        log.error("Feldvorschlag ohne Nummer, chat_id=%s, roh=%r", chat_id, roh)
        return _TEXT_UNBEKANNT
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    gesetzt = []
    for zeile in wert.splitlines():
        kopf, trenner, rest = zeile.partition(":")
        feld = szene_modul.feldname(kopf)
        if not trenner or not feld or not rest.strip():
            continue
        if feld == "figuren":
            nach_name = {
                f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)
            }
            ids = [
                nach_name[n.strip().lower()]
                for n in rest.split(",")
                if n.strip().lower() in nach_name
            ]
            if ids:
                repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
                gesetzt.append(feld)
            continue
        repo.setze_szenenfeld(conn, szene_id, feld, rest.strip())
        gesetzt.append(feld)
    if not gesetzt:
        log.error("Feldvorschlag ohne verwertbares Feld, chat_id=%s", chat_id)
        return _TEXT_UNBEKANNT
    biete_szene(conn, tg, chat_id, repo.hole_szene(conn, szene_id))
    return f"Szene {nummer}: {', '.join(gesetzt)}"


def _schreibe_szene(conn, tg, klm, e, chat_id: int, nummer: int,
                    notiz: str | None = None) -> str:
    """"Passt, schreiben" -- mit den drei Ausgaengen, die es hier gibt:

    1. Es fehlen Pflichtfelder der Szene -> **kein** Sperrtext, sondern ein
       Vorschlag der fehlenden Felder aus dem Material
       (``szenenfolge.starte_feldvorschlag``), mit Grundleiste darunter. Der
       Sperrtext bleibt der richtige Weg beim direkten Schreibauftrag
       (``/szene``), aber wer eine Szene vor Augen hat und "schreiben" tippt,
       soll nicht eine Liste von Luecken bekommen.
    2. Die USA-Einwilligung steht noch aus -> ``szene.starte`` stellt die
       Frage samt Knoepfen und merkt sich den Auftrag; nach der Antwort
       laeuft er automatisch weiter (``erkenner._starte_szene``). Genau das
       Verhalten von heute, nur eingebettet.
    3. Sonst laeuft der Szenenlauf im eigenen Thread -- kein Modellaufruf in
       diesem Handler (Zusage 2)."""
    from interview_theater import szene as szene_modul, szenenfolge

    ziel = _szene_mit_nummer(conn, chat_id, nummer)
    if ziel is None:
        tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    fehlende, _ = szene_modul.fehlendes(conn, ziel)
    eigene = [
        f for f in fehlende if f not in szene_modul.ARBEITSSTAND_PFLICHTFELDER
    ]
    if eigene:
        if szenenfolge.starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel) is not None:
            return "Ich schlage die fehlenden Angaben vor"
    auftrag = f"Schreib Szene {nummer}."
    if notiz and notiz.strip():
        auftrag += f" {notiz.strip()}"
    szene_modul.starte(conn, tg, klm, e, chat_id, auftrag)
    return f"Szene {nummer} laeuft"
#: Wartet diese Gruppe gerade darauf, uns zu sagen, was an der Kurzgeschichte
#: anders werden soll? Im Prozess und nicht in der Datenbank (wie
#: ``szenenfolge._regienotiz_erwartet``): der Merker gilt fuer genau die
#: naechste Nachricht, und ein Neustart dazwischen macht daraus wieder einen
#: normalen Gespraechsbeitrag -- die harmlose Fehlerrichtung.
_geschichte_notiz_erwartet: set[int] = set()


def erwarte_geschichte_notiz(chat_id: int) -> None:
    """Merkt: die naechste Nachricht dieser Gruppe sagt, was an der
    Kurzgeschichte anders werden soll."""
    _geschichte_notiz_erwartet.add(chat_id)


def nimm_geschichte_notiz(chat_id: int) -> bool:
    """Liefert True, wenn eine Regie-Notiz zur Kurzgeschichte erwartet wird --
    und vergisst es dabei (einmalig, wie ``nimm_figurenanzahl_erwartung``)."""
    if chat_id not in _geschichte_notiz_erwartet:
        return False
    _geschichte_notiz_erwartet.discard(chat_id)
    return True


def biete_kurzgeschichte(conn, tg, chat_id: int, text: str) -> int:
    """Der Knopf, aus dem der Prosa-Lauf startet.

    **Nie aus dem Gespraech** (06.09.2026, Birk 12:25): der Lauf kostet
    Minuten und Geld, und ein Modell, das ihn "ankuendigt", hat ihn nicht
    gestartet. Er haengt an diesem einen Knopf."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_GESCHICHTE_SCHREIBEN)
    leiste = [
        (
            TEXT_GESCHICHTE_SCHREIBEN_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_SCHREIBEN, None)
            ),
        ),
    ]
    return _mit_leiste(conn, tg, chat_id, text, leiste)


def zeige_kurzgeschichte(conn, tg, chat_id: int) -> None:
    """Spielt die fertige Kurzgeschichte abschnittsweise aus und haengt die
    drei Wege darunter: passt / anders / ganz neu.

    Abschnittsweise, weil eine Kurzgeschichte ueber
    ``telegram.NACHRICHT_GRENZE`` liegt und Telegram sie sonst abschneidet --
    und weil die Gruppe sie so liest, wie sie spaeter gearbeitet wird: ein
    Abschnitt ist eine Szene.

    **Davor steht der Vorspann** (07.09.2026, ``vorspann.py``): Setting,
    Worum-es-geht, Form, die Szenen und die Besetzung. Er ist nicht Teil der
    Geschichte, sondern die Antwort auf die Frage, die eine Gruppe mit
    dreizehn Figuren beim ersten Absatz hat -- wer ist wer. Deterministisch,
    ohne Modellaufruf, als eigene Nachricht: er soll ueber der Geschichte
    stehen bleiben, wenn die weiterscrollt."""
    from interview_theater import telegram as telegram_modul, vorspann

    kopfzeilen = vorspann.als_chattext(vorspann.aus_datenbank(conn, chat_id))
    if kopfzeilen:
        for stueck in telegram_modul.teile_text(kopfzeilen):
            tg.sende(chat_id, stueck)

    for szene in repo.hole_szenen(conn, chat_id):
        prosa = (szene["prosa"] or "").strip()
        if not prosa:
            continue
        kopf = f"{szene['nummer']}. {szene['titel'] or ''}".strip()
        for stueck in telegram_modul.teile_text(f"{kopf}\n\n{prosa}"):
            tg.sende(chat_id, stueck)
    leiste = [
        (_TEXT_GESCHICHTE_PASST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_PASST, None))),
        (_TEXT_GESCHICHTE_ANDERS_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_ANDERS, None))),
        (_TEXT_GESCHICHTE_NEU_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_GESCHICHTE_NEU, None))),
    ]
    _mit_leiste(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE, leiste)


def _melde_spaetere(conn, tg, chat_id: int, nummer: int) -> list[int]:
    """Markiert nach einer Aenderung an Szene ``nummer`` alle spaeteren
    geschriebenen Szenen zur Pruefung und sagt der Gruppe in EINER Zeile,
    welche das sind (``szenenfolge.markiere_spaetere``).

    Kein automatisches Neuschreiben und keine Rueckfrage: die Szenen tragen
    danach ihren Vermerk, und wenn sie das naechste Mal vorgestellt werden,
    stehen "Neu schreiben" und "So lassen" darunter. Ein Fehlschlag beim
    Senden darf den laufenden Knopf nicht mitreissen."""
    from interview_theater import szenenfolge

    betroffen = szenenfolge.markiere_spaetere(conn, chat_id, nummer)
    if not betroffen:
        return []
    namen = ", ".join(f"Szene {n}" for n in betroffen)
    try:
        tg.sende(
            chat_id,
            _TEXT_SPAETERE_GEPRUEFT.format(nummer=nummer, spaetere=namen),
        )
    except Exception:
        log.exception("Hinweis auf spaetere Szenen fehlgeschlagen, chat_id=%s", chat_id)
    return betroffen


def _biete_weiter_nach_szene(conn, tg, chat_id: int, nummer: int) -> None:
    """Nach einer abgenommenen Szene: entweder die naechste offene, oder --
    wenn keine mehr kommt -- "Weiter zu Durchlauf".

    Der Phasenknopf entsteht ueber ``_phasenknopf``, also nur, wenn die
    Materiallage Phase 7 ueberhaupt hergibt (``phasen.voraussetzungen``:
    mindestens eine geschriebene Szene). Er heisst "Weiter zu 7 · Durchlauf"
    wie jeder Phasenknopf -- eine zweite Schreibweise waere eine zweite Sache
    zu lernen."""
    naechste = _naechste_offene(conn, chat_id, nummer)
    if naechste is not None:
        biete_szene(conn, tg, chat_id, naechste)
        return
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        _mit_leiste(conn, tg, chat_id, _TEXT_KEINE_NAECHSTE, [phasenknopf])
    else:
        tg.sende(chat_id, _TEXT_KEINE_NAECHSTE)

"""Phasen 5 bis 8: Geschichte, Schaerfung, Szenentexte, Durchlauf.

Die laengste Kette im Paket, und sie folgt ueberall derselben Form: ein
Vorschlag steht als Text im Chat, darunter haengen Knoepfe, und der Knopf
traegt die Entscheidung selbst -- Szenenfolge (``sende_szenenfolge``),
Geschichte (``sende_geschichte``), Schaerfung am Material
(``biete_schaerfung``), die Szene mit ihrer Form und ihren Feldern
(``biete_szene``, ``biete_szenenform``), die Stueckpruefung
(``zeige_stueckpruefung``) und der Durchlauf mit dem Textbuch
(``biete_durchlauf``).

Kein Modellaufruf steht hier: was eines braucht, geht ueber
``szenenfolge.py``, ``schaerfung.py``, ``stueckpruefung.py`` oder ``szene.py``
in einen eigenen Thread.
"""

from interview_theater import repo

from interview_theater.knoepfe.texte import (
    ART_DURCHLAUF_SZENE, ART_EIGENE, ART_GESCHICHTE_SPEICHERN,
    ART_PRUEFUNG_LASSEN, ART_PRUEFUNG_RUNDE, ART_PRUEFUNG_SZENE,
    ART_SCHAERFUNG_FIGUR, ART_SCHAERFUNG_RUNDE, ART_SCHAERFUNG_SZENE,
    ART_SZENENFELDER_SPEICHERN, ART_SZENENFOLGE_ANZAHL,
    ART_SZENENFOLGE_REIHENFOLGE, ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM,
    ART_SZENE_ANDERS, ART_SZENE_FORM, ART_SZENE_NAECHSTE, ART_SZENE_NEU,
    ART_SZENE_PASST, ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN,
    ART_SZENE_SO_LASSEN, ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA, ART_TEXTBUCH,
    TEXT_ANDERS_KNOPF, TEXT_ANZAHL_KNOPF, TEXT_DURCHLAUF_SZENE_KNOPF,
    TEXT_EIGENE_IDEE_KNOPF, TEXT_FORM_VORSCHLAG_ZUSATZ, TEXT_NAECHSTE_KNOPF,
    TEXT_NEU_KNOPF, TEXT_PASST_KNOPF, TEXT_REIHENFOLGE_KNOPF,
    TEXT_SCHAERFUNG_RUNDE_KNOPF, TEXT_SZENE_FORM_KNOPF,
    TEXT_SZENE_PLANEN_KNOPF, TEXT_SZENE_SCHREIBEN_KNOPF,
    TEXT_SZENE_SO_LASSEN_KNOPF, TEXT_SZENE_UEBERSPRINGEN_KNOPF,
    TEXT_TEXTBUCH_KNOPF, TRENNER, _TEXT_ANDERS, _TEXT_EIGENE_IDEE,
    _TEXT_FOLGE_GESPEICHERT, _TEXT_FOLGE_LEER, _TEXT_GESCHICHTE_GESPEICHERT,
    _TEXT_GESCHICHTE_LEER, _TEXT_KEINE_NAECHSTE, _TEXT_NACH_SPEICHERN_FRAGE,
    _TEXT_PRUEFUNG_LAEUFT, _TEXT_PRUEFUNG_LASSEN_KNOPF,
    _TEXT_PRUEFUNG_RUNDE_KNOPF, _TEXT_PRUEFUNG_SZENE_KNOPF,
    _TEXT_SCHAERFUNG_DURCH, _TEXT_SCHAERFUNG_LAEUFT, _TEXT_SPAETERE_GEPRUEFT,
    _TEXT_SZENENFORM_FRAGE, _TEXT_SZENE_OHNE_TEXT, _TEXT_SZENE_UNBEKANNT,
    _TEXT_UNBEKANNT, _TEXT_USA_FRAGE_KNOEPFE, _TEXT_USA_JA_KNOPF,
    _TEXT_USA_NEIN_KNOPF, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _mit_leiste, _nimm_alte_leiste_ab, _phasenknopf,
    grundleiste,
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
    tg.sende_mit_knoepfen(chat_id, text or _TEXT_USA_FRAGE_KNOEPFE, knoepfe)


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
    """Der Geschichte-Vorschlag im Chat (Phase 5): Bogen, Ende und
    Szenenfolge, darunter \"Anzahl aendern\" · \"Reihenfolge aendern\" und die
    Grundleiste.

    Derselbe Weg wie ``sende_szenenfolge`` -- ohne Marker keine Leiste, kein
    Raten. Der ``wert`` traegt den ganzen Block: die Geschichte und ihre
    Szenen sind EINE Entscheidung."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "geschichte")
    if not wert:
        log.error("Geschichte-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_GESCHICHTE_SPEICHERN)
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


def biete_schaerfung(conn, tg, chat_id: int) -> bool:
    """Stellt die naechste offene Schaerfung vor -- erst Szene fuer Szene,
    dann Figur fuer Figur. Liefert True, solange noch eine kam.

    Deterministisch aus der Datenbank (``schaerfung.szenenvorschlag`` /
    ``figurvorschlag``): das Mapping ist schon gelaufen, hier wird nur
    vorgestellt -- kein Modellaufruf im Handler (Zusage 2).

    Ist nichts mehr offen, steht die Frage nach einer weiteren Runde da und,
    wenn die Materiallage sie hergibt, der Weg zu den Szenentexten."""
    from interview_theater import schaerfung as schaerfung_modul

    for szene in repo.hole_szenen(conn, chat_id):
        text = schaerfung_modul.szenenvorschlag(conn, chat_id, szene)
        if text is None:
            continue
        leiste = grundleiste(
            conn, chat_id, ART_SCHAERFUNG_SZENE, str(szene["nummer"])
        )
        _mit_leiste(conn, tg, chat_id, text, leiste)
        return True
    for figur in repo.figuren(conn, chat_id):
        text = schaerfung_modul.figurvorschlag(conn, chat_id, figur)
        if text is None:
            continue
        leiste = grundleiste(conn, chat_id, ART_SCHAERFUNG_FIGUR, figur["name"])
        _mit_leiste(conn, tg, chat_id, text, leiste)
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


def starte_schaerfung(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst das Mapping an (im Thread) und stellt danach die erste
    Schaerfung vor -- der automatische Eintritt in Phase 6.

    Kein Modellaufruf hier: ``schaerfung.starte`` gibt sofort ab (Zusage 2).
    Ohne Sprachmodell (Tests) bleibt der Weg trotzdem offen -- dann wird
    gezeigt, was schon zugeordnet ist."""
    from interview_theater import schaerfung as schaerfung_modul

    def _danach() -> None:
        biete_schaerfung(conn, tg, chat_id)

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


def zeige_stueckpruefung(conn, tg, chat_id: int, runde: int | None = None) -> int:
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
        message_id = tg.sende_mit_knoepfen(
            chat_id, pruefung_modul.befundtext(zeile), leiste
        )
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        verschickt += 1
    biete_nach_pruefung(conn, tg, chat_id, runde)
    return verschickt


def biete_nach_pruefung(conn, tg, chat_id: int, runde: int) -> int:
    """Die Abschlussleiste unter den Befunden: "Noch eine Pruefrunde",
    "Textbuch als Datei" und ein Knopf je Szene ("Szene N ansehen")."""
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
    return _mit_leiste(conn, tg, chat_id, szenenfolge.uebersicht(conn, chat_id), leiste)


def _pruefbefund(conn, chat_id: int, befund_id: int):
    """Der Befund mit dieser id, oder None -- ueber ``repo``, damit das
    weiche Loeschen an einer Stelle bleibt."""
    return next(
        (z for z in repo.stueckpruefungen(conn, chat_id) if z["id"] == befund_id),
        None,
    )


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


def biete_durchlauf(conn, tg, chat_id: int) -> int:
    """Der Eintritt in Phase 7 (Schaerfung des Stuecks): die Szenenfolge mit Status als Text, darunter
    ein Knopf je Szene, "Textbuch als Datei" und "Eigene Idee".

    Alles deterministisch aus der Datenbank. Der Durchlauf ist eine Ansicht
    auf das, was die Gruppe gebaut hat -- kein Anlass, ein Modell zu fragen."""
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
    leiste.append(
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, ART_TEXTBUCH)),
        )
    )
    return _mit_leiste(conn, tg, chat_id, szenenfolge.uebersicht(conn, chat_id), leiste)


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
    tg.sende(chat_id, f"{kopf}\n\n{volltext}")
    return f"Szene {nummer}"


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


def _speichere_geschichte(conn, tg, chat_id: int, roh: str) -> str:
    """Speichert Bogen und Ende (``arbeitsstand.geschichte``) UND legt die
    Szenenfolge an -- Phase 5, ein Vorschlag, eine Entscheidung.

    Die Szenen entstehen ueber denselben ``szenenfolge.lege_an`` wie bisher:
    es gibt einen Weg, eine Szenenfolge anzulegen, nicht zwei. Danach kommt
    **keine** Szenenvorstellung -- die naechste Station ist die Schaerfung,
    und die Gruppe bekommt dafuer den Phasenknopf."""
    from interview_theater import szenenfolge

    modus, _, wert = roh.partition(TRENNER)
    geschichte, zeilen = szenenfolge.zerlege_geschichte(wert)
    if not geschichte or not zeilen:
        log.error("Geschichte-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_GESCHICHTE_LEER)
        return _TEXT_GESCHICHTE_LEER
    repo.setze_arbeitsstand(conn, chat_id, "geschichte", geschichte)
    nummern = szenenfolge.lege_an(conn, chat_id, zeilen)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Geschichte: {geschichte}", quelle="knopf",
    )
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        "Szenenfolge: " + "; ".join(f"{n}. {z[0]}" for n, z in zip(nummern, zeilen)),
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
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        _mit_leiste(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
    else:
        tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
    return f"Geschichte mit {len(nummern)} Szenen uebernommen"


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


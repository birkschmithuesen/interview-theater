"""Was ein gedrueckter Knopf tut -- die Dispatch-Tabelle und ihre Handler.

Je Knopfart eine benannte Funktion der Form ``(conn, d) -> str``, wobei ``d``
ein ``Druck`` ist (tg, klm, e, knopf, chat_id). Die Zuordnung steht in
``_WIRKUNGEN``; ``_wirke`` schlaegt nach und ruft auf, ``behandle`` ist der
Eingang aus ``bot.schleife``.

Vorher war das eine if/elif-Kaskade ueber 62 Arten in einer Funktion von 464
Zeilen. Eine Tabelle laesst sich auslesen, eine Kaskade nicht -- genau darauf
baut ``tests/test_knoepfe_struktur.py``, das die drei Zusagen des Pakets am
Quelltext prueft statt am Verhalten.
"""

from typing import NamedTuple

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ANWEISUNGEN, ANWEISUNG_DUKTUS, ANWEISUNG_FRAGEN_ANDERE,
    ANWEISUNG_KERNTHEMA, ANWEISUNG_NAMEN, ART_ANDERS, ART_AUFNAHME,
    ART_AUSWERTEN, ART_AUSWERTEN_ALLE, ART_DURCHLAUF_SZENE, ART_EIGENE,
    ART_FIGUREN_ANZAHL, ART_FIGUREN_ANZAHL_FREI, ART_FIGUREN_ANZAHL_MENU,
    ART_FIGUREN_NAMEN_MENU, ART_FIGUR_DUKTUS, ART_FIGUR_DUKTUS_MENU,
    ART_FIGUR_ENTFERNEN, ART_FIGUR_INTERVIEW, ART_FIGUR_INTERVIEW_MENU,
    ART_FIGUR_NAME, ART_FIGUR_NAME_MENU, ART_FIGUR_PASST, ART_FRAGEN_ANDERE,
    ART_FRAGEN_EIGENE, ART_FRAGEN_UEBERNEHMEN, ART_FRAGE_WAHL,
    ART_GESCHICHTE_SPEICHERN, ART_HILFE, ART_KERNTHEMA, ART_LEITFADEN,
    ART_NOCH_NICHT, ART_PHASE, ART_PRUEFUNG_LASSEN, ART_PRUEFUNG_RUNDE,
    ART_PRUEFUNG_SZENE, ART_RAHMEN, ART_RICHTUNG, ART_SCHAERFUNG_FIGUR,
    ART_SCHAERFUNG_RUNDE, ART_SCHAERFUNG_SZENE, ART_SCHLAG_VOR, ART_SPEICHERN,
    ART_STAND, ART_SZENENFELDER_SPEICHERN, ART_SZENENFOLGE_ANZAHL,
    ART_SZENENFOLGE_ANZAHL_WERT, ART_SZENENFOLGE_REIHENFOLGE,
    ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM, ART_SZENE_ANDERS,
    ART_SZENE_FORM, ART_SZENE_NAECHSTE, ART_SZENE_NEU, ART_SZENE_PASST,
    ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN, ART_SZENE_SO_LASSEN,
    ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA, ART_SZENE_ZEIGEN, ART_TEIL_FERTIG,
    ART_TEIL_WEITER, ART_TEXTBUCH, ART_TRANSKRIPT, ART_WIR_ZUERST,
    ART_ZUSAMMENFASSUNG, PHASE_SETTING, PHASE_SZENEN, TRENNER,
    _ANWEISUNG_ALLGEMEIN, _KETTE, _NOTIERT, _TEXT_ANDERS, _TEXT_ANZAHL_FRAGE,
    _TEXT_AUSWERTEN_UNBEKANNT, _TEXT_AUSWERTEN_UNMOEGLICH, _TEXT_EIGENE,
    _TEXT_EIGENE_IDEE, _TEXT_FIGUREN_ANZAHL_FRAGE,
    _TEXT_FIGUREN_ANZAHL_FREI_FRAGE, _TEXT_FIGUREN_NAMEN_FRAGE,
    _TEXT_FRAGEN_EIGENE, _TEXT_FRAGEN_WAHL, _TEXT_KEIN_TRANSKRIPT,
    _TEXT_NOCH_NICHT, _TEXT_PASST, _TEXT_PRUEFUNG_LASSEN,
    _TEXT_PRUEFUNG_UEBERHOLT, _TEXT_PRUEFUNG_UNBEKANNT,
    _TEXT_REIHENFOLGE_FRAGE, _TEXT_SCHAERFUNG_NICHTS,
    _TEXT_SCHAERFUNG_UEBERNOMMEN, _TEXT_SCHON_BENUTZT, _TEXT_SCHON_GESETZT,
    _TEXT_SZENE_ANDERS_FRAGE, _TEXT_SZENE_PLANEN_FRAGE,
    _TEXT_SZENE_SO_GELASSEN, _TEXT_SZENE_UEBERSPRUNGEN, _TEXT_SZENE_UNBEKANNT,
    _TEXT_TEIL_SCHON_AUS, _TEXT_TEIL_WEITER, _TEXT_TEXTBUCH_BESCHREIBUNG,
    _TEXT_TEXTBUCH_FEHLER, _TEXT_UNBEKANNT, _TEXT_USA_JA, _TEXT_USA_NEIN,
    _TEXT_WIR_ZUERST, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _entferne_tastatur, _id_aus_daten, _mit_leiste, _speichere,
    _starte_auftrag, offene_art,
)
from interview_theater.knoepfe.fragen import (
    _auswahlfragen, _speichere_eroeffnung, starte_eroeffnung,
    starte_sensibilitaetspruefung,
)
from interview_theater.knoepfe.figuren import (
    _biete_interviews, _entwurfszeilen, _ersetze_namen, _kette_weiter,
    _zahl_aus, biete_figurenanzahl, erwarte_figurenanzahl, stelle_figur_vor,
    uebernimm_figurenanzahl,
)
from interview_theater.knoepfe.szenen import (
    _biete_weiter_nach_szene, _melde_spaetere, _naechste_offene, _pruefbefund,
    _schreibe_szene, _speichere_geschichte, _speichere_szenenfelder,
    _speichere_szenenfolge, _szene_mit_nummer, biete_schaerfung, biete_szene,
    biete_szenenform, starte_schaerfung, starte_stueckpruefung,
    zeige_szenentext,
)
from interview_theater.knoepfe.interviews import (
    _werte_alle_aus,
)
from interview_theater.knoepfe.stationen import (
    eintritt_in_phase,
)


class Druck(NamedTuple):
    """Alles, was ein Knopf-Handler ausser ``conn`` braucht (06.09.2026).

    Ein Handler hat damit ueberall dieselbe Form ``(conn, d) -> str`` und
    passt in die Tabelle ``_WIRKUNGEN``. ``knopf`` ist die Zeile aus der
    Tabelle ``knopf``, ``chat_id`` kommt aus ihr und nicht aus dem Druck --
    ``behandle`` hat beides vorher gegeneinander geprueft."""

    tg: object
    klm: object
    e: object
    knopf: object
    chat_id: int

    @property
    def wert(self) -> str:
        """Der ``wert`` der Knopfzeile als String, nie None."""
        return str(self.knopf["wert"] or "")


def _wirkung_szenenfolge_speichern(conn, d: Druck) -> str:
    return _speichere_szenenfolge(conn, d.tg, d.klm, d.e, d.chat_id, d.wert)


def _wirkung_geschichte_speichern(conn, d: Druck) -> str:
    return _speichere_geschichte(conn, d.tg, d.chat_id, d.wert)


def _wirkung_schaerfung_szene(conn, d: Druck) -> str:
    """Die Uebernahme ist deterministisch (Felder ergaenzen), der naechste
    Vorschlag kommt aus der Datenbank -- kein Modellaufruf (Zusage 2)."""
    from interview_theater import schaerfung as schaerfung_modul

    modus, _, nummer_roh = d.wert.partition(TRENNER)
    ziel = _szene_mit_nummer(conn, d.chat_id, int(nummer_roh or d.wert))
    if ziel is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    anzahl = schaerfung_modul.uebernimm_szene(conn, d.chat_id, ziel)
    if not anzahl:
        d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_NICHTS)
    else:
        d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_UEBERNOMMEN.format(anzahl=anzahl))
    if modus.strip() == "anders":
        d.tg.sende(d.chat_id, _TEXT_EIGENE_IDEE)
    biete_schaerfung(conn, d.tg, d.chat_id)
    return f"Szene {ziel['nummer']} geschaerft"


def _wirkung_schaerfung_figur(conn, d: Druck) -> str:
    from interview_theater import schaerfung as schaerfung_modul

    modus, _, name = d.wert.partition(TRENNER)
    figur = repo.hole_figur(conn, d.chat_id, name or d.wert)
    if figur is None:
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    anzahl = schaerfung_modul.uebernimm_figur(conn, d.chat_id, figur)
    if not anzahl:
        d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_NICHTS)
    else:
        d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_UEBERNOMMEN.format(anzahl=anzahl))
    if modus.strip() == "anders":
        d.tg.sende(d.chat_id, _TEXT_EIGENE_IDEE)
    biete_schaerfung(conn, d.tg, d.chat_id)
    return f"{figur['name']} geschaerft"


def _wirkung_schaerfung_runde(conn, d: Druck) -> str:
    """Eine weitere Runde mit dem inzwischen geschaerften Stand -- der Lauf
    haengt im Thread, hier wird nur angestossen."""
    starte_schaerfung(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Noch eine Runde"


def _wirkung_szenenfolge_anzahl(conn, d: Druck) -> str:
    """Nur die Zahlenknoepfe oeffnen -- der Vorschlag entsteht erst beim Druck
    auf eine Zahl, und der laeuft im Thread."""
    from interview_theater import szenenfolge

    leiste = [
        (
            str(zahl),
            _daten(
                repo.lege_knopf_an(
                    conn, d.chat_id, ART_SZENENFOLGE_ANZAHL_WERT, str(zahl)
                )
            ),
        )
        for zahl in szenenfolge.ANZAHL_MOEGLICH
    ]
    _mit_leiste(conn, d.tg, d.chat_id, _TEXT_ANZAHL_FRAGE, leiste)
    return "Wie viele?"


def _wirkung_szenenfolge_anzahl_wert(conn, d: Druck) -> str:
    """In Phase 4 ist die Anzahl eine Angabe zur GESCHICHTE, nicht zu einer
    blanken Szenenfolge -- derselbe Knopf, der Weg richtet sich nach der
    Station."""
    from interview_theater import szenenfolge

    if phasen.aktuelle(conn, d.chat_id) <= PHASE_SETTING:
        szenenfolge.starte_geschichte(
            conn, d.tg, d.klm, d.e, d.chat_id, anzahl=int(d.wert)
        )
    else:
        szenenfolge.starte(conn, d.tg, d.klm, d.e, d.chat_id, anzahl=int(d.wert))
    return f"{d.wert} Szenen"


def _wirkung_szenenfolge_reihenfolge(conn, d: Druck) -> str:
    """Der Bot fragt; die naechste Nachricht wirkt ueber den normalen
    Gespraechszug, der den Vorschlag neu baut. Kein Modellaufruf hier."""
    d.tg.sende(d.chat_id, _TEXT_REIHENFOLGE_FRAGE)
    return "Sagt mir die Reihenfolge"


def _wirkung_szene_zeigen(conn, d: Druck) -> str:
    ziel = _szene_mit_nummer(conn, d.chat_id, int(d.wert))
    if ziel is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    biete_szene(conn, d.tg, d.chat_id, ziel)
    return f"Szene {d.wert}"


def _wirkung_szene_schreiben(conn, d: Druck) -> str:
    return _schreibe_szene(conn, d.tg, d.klm, d.e, d.chat_id, int(d.wert))


def _wirkung_szene_planen(conn, d: Druck) -> str:
    """Wie "Nochmal anders": ein Satz, kein Modellaufruf. Was die Gruppe danach
    sagt, laeuft ueber den Erkenner (art szene_planen) oder den Gespraechszug
    -- beide Wege setzen die Felder und stellen die Szene neu vor."""
    d.tg.sende(d.chat_id, _TEXT_SZENE_PLANEN_FRAGE)
    return "Was soll anders sein?"


def _wirkung_szene_form(conn, d: Druck) -> str:
    biete_szenenform(conn, d.tg, d.chat_id, int(d.wert))
    return "Welche Form?"


def _wirkung_szene_ueberspringen(conn, d: Druck) -> str:
    nummer = int(d.wert)
    # Weich (N3): die Szene ist raus, aber nichts ist weg -- eine Gruppe,
    # die es sich anders ueberlegt, hat sie noch.
    entfernt = repo.entferne_szene(conn, d.chat_id, nummer)
    if entfernt is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    d.tg.sende(d.chat_id, _TEXT_SZENE_UEBERSPRUNGEN.format(nummer=nummer))
    naechste = _naechste_offene(conn, d.chat_id, nummer)
    if naechste is not None:
        biete_szene(conn, d.tg, d.chat_id, naechste)
    return f"Szene {nummer} raus"


def _wirkung_szenenfelder_speichern(conn, d: Druck) -> str:
    modus, _, rest = d.wert.partition(TRENNER)
    meldung = _speichere_szenenfelder(conn, d.tg, d.chat_id, rest)
    if modus.strip() == "anders":
        d.tg.sende(d.chat_id, _TEXT_EIGENE_IDEE)
    return meldung


def _wirkung_szene_passt(conn, d: Druck) -> str:
    nummer = int(d.wert)
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    repo.setze_szene_fertig(conn, ziel["id"], True)
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        f"Szene {nummer} abgenommen: {ziel['titel'] or ''}".strip(),
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, _TEXT_PASST.format(nummer=nummer))
    _biete_weiter_nach_szene(conn, d.tg, d.chat_id, nummer)
    return f"Szene {nummer} steht"


def _wirkung_szene_anders(conn, d: Druck) -> str:
    """Der Regie-Vermerk kommt als naechste Nachricht; ``ablauf.antworte``
    greift ihn auf (``szenenfolge.nimm_regienotiz``) und schreibt die Szene
    damit neu. Kein Modellaufruf hier."""
    from interview_theater import szenenfolge

    nummer = int(d.wert)
    szenenfolge.erwarte_regienotiz(d.chat_id, nummer)
    d.tg.sende(d.chat_id, _TEXT_SZENE_ANDERS_FRAGE)
    _melde_spaetere(conn, d.tg, d.chat_id, nummer)
    return "Was soll anders werden?"


def _wirkung_szene_neu(conn, d: Druck) -> str:
    from interview_theater import szene as szene_modul, szenenfolge

    nummer = int(d.wert)
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is None:
        d.tg.sende(d.chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    # Die alte Fassung bleibt in der Datenbank (N3-Haltung: nichts wird
    # weggeworfen), der Fertig-Stempel faellt: ein neuer Text ist wieder
    # ein Entwurf.
    repo.hebe_fassung_auf(conn, ziel["id"])
    repo.setze_szene_fertig(conn, ziel["id"], False)
    # Diese Szene wird gerade neu geschrieben -- ihr eigener Pruef-Vermerk
    # ist damit erledigt, und die spaeteren bekommen einen.
    szenenfolge.nimm_pruefvermerk(conn, d.chat_id, nummer)
    _melde_spaetere(conn, d.tg, d.chat_id, nummer)
    # "Neu schreiben" heisst NEU: die alte Fassung geht nicht als Vorlage
    # mit (06.09.2026: zweimal derselbe Text, weil der Volltext unter
    # "soll ueberarbeitet werden" im Prompt stand). Der Marker wird in
    # szene._diese_szene_text erkannt.
    return _schreibe_szene(
        conn, d.tg, d.klm, d.e, d.chat_id, nummer, notiz=szene_modul.NEU_MARKER
    )


def _wirkung_szene_so_lassen(conn, d: Druck) -> str:
    """"So lassen": der Vermerk faellt weg, der Text bleibt. Kein Lauf, kein
    Modellaufruf -- die Gruppe hat entschieden, dass die Aenderung an der
    frueheren Szene diese hier nicht beruehrt."""
    from interview_theater import szenenfolge

    nummer = int(d.wert)
    szenenfolge.nimm_pruefvermerk(conn, d.chat_id, nummer)
    d.tg.sende(d.chat_id, _TEXT_SZENE_SO_GELASSEN.format(nummer=nummer))
    _biete_weiter_nach_szene(conn, d.tg, d.chat_id, nummer)
    return f"Szene {nummer} bleibt"


def _wirkung_szene_naechste(conn, d: Druck) -> str:
    naechste = _naechste_offene(conn, d.chat_id, int(d.wert))
    if naechste is None:
        _biete_weiter_nach_szene(conn, d.tg, d.chat_id, int(d.wert))
        return "Das war die letzte"
    biete_szene(conn, d.tg, d.chat_id, naechste)
    return f"Szene {naechste['nummer']}"


def _wirkung_durchlauf_szene(conn, d: Druck) -> str:
    return zeige_szenentext(conn, d.tg, d.chat_id, int(d.wert))


def _wirkung_pruefung_szene(conn, d: Druck) -> str:
    """"Szene N ueberarbeiten" geht den bestehenden Weg "Passt, aber anders":
    ein Szenenauftrag mit dem Vorschlag als Regie-Notiz. Kein Modellaufruf hier
    -- ``ablauf.starte_auftrag`` gibt an einen eigenen Thread ab (Zusage 2)."""
    befund = _pruefbefund(conn, d.chat_id, int(d.wert))
    if befund is None or befund["szene_nummer"] is None:
        d.tg.sende(d.chat_id, _TEXT_PRUEFUNG_UNBEKANNT)
        return _TEXT_PRUEFUNG_UNBEKANNT
    from interview_theater import ablauf, stueckpruefung as pruefung_modul

    nummer = int(befund["szene_nummer"])
    ablauf.starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        f"Schreib Szene {nummer} neu. {pruefung_modul.regienotiz(befund)}",
    )
    # Nach einer Ueberarbeitung gilt der Stand als ungeprueft -- gesagt,
    # nicht automatisch nachgelaufen (Birk).
    d.tg.sende(d.chat_id, _TEXT_PRUEFUNG_UEBERHOLT)
    return f"Szene {nummer} wird ueberarbeitet"


def _wirkung_pruefung_lassen(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, _TEXT_PRUEFUNG_LASSEN)
    return "Bleibt"


def _wirkung_pruefung_runde(conn, d: Druck) -> str:
    """Noch eine Pruefrunde: derselbe Weg wie beim Eintritt in die Phase, die
    Runde zaehlt in ``repo.letzte_pruefrunde`` von selbst hoch."""
    starte_stueckpruefung(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Ich lese noch einmal"


def _wirkung_textbuch(conn, d: Druck) -> str:
    from interview_theater import szenenfolge

    text = szenenfolge.textbuch(conn, d.chat_id)
    try:
        d.tg.sende_datei(
            d.chat_id, szenenfolge.dateiname(d.chat_id), text,
            _TEXT_TEXTBUCH_BESCHREIBUNG,
        )
    except Exception:
        # Scheitert sendDocument (alte Telegram-Attrappe, Rechte in der
        # Gruppe), soll die Gruppe nicht ratlos dastehen: eine Zeile, und
        # die Szenen sind ueber "Szene N ansehen" weiter erreichbar.
        log.exception("Textbuch-Datei fehlgeschlagen, chat_id=%s", d.chat_id)
        d.tg.sende(d.chat_id, _TEXT_TEXTBUCH_FEHLER)
        return _TEXT_TEXTBUCH_FEHLER
    return "Textbuch"


# --- Die Wirkungen der Grundleiste, der Fragen und der Figuren -------------


def _wirkung_speichern(conn, d: Druck) -> str:
    """"Gefaellt uns, weiter". Vier Wege, je nach der Art im ``wert``: die
    Eroeffnung geht in ZWEI Felder, die Einleitungen tragen die Kette weiter,
    Kernthema/Kernfrage haben ihre eigene Kette, alles andere ist der
    Regelfall."""
    roh = d.wert
    gespeicherte_art = roh.partition(TRENNER)[0].strip()
    if gespeicherte_art == "eroeffnung":
        # Eroeffnung und Abschluss stecken in EINEM Block und gehen in
        # ZWEI Felder -- deshalb ein eigener Speicherweg statt des
        # Arbeitsstand-Setters (wie bei der Geschichte in Phase 5).
        return _speichere_eroeffnung(
            conn, d.tg, d.chat_id, roh.partition(TRENNER)[2]
        )
    if gespeicherte_art in ("einleitungen", "fragen_weich"):
        return _speichere_einleitungen(conn, d, roh)
    if gespeicherte_art in _KETTE:
        return _speichere_kettenglied(conn, d, roh, gespeicherte_art)
    # "Gefaellt uns, weiter" ueberschreibt nie still, was schon steht
    # (06.09.2026): ist das Feld gesetzt und keine Aenderung offen, ist
    # der Druck eine Bestaetigung (``_ist_bestaetigung``).
    meldung = _speichere(conn, d.tg, d.chat_id, roh, nur_bestaetigen=True)
    if gespeicherte_art == "figuren" and meldung not in (
        _TEXT_UNBEKANNT, _TEXT_SCHON_GESETZT,
    ):
        # Ebene 1 ist abgenommen -- ab hier geht es Figur fuer Figur
        # weiter (Ebene 2), ohne dass jemand etwas antippen muss.
        stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    if gespeicherte_art == "fragen" and meldung != _TEXT_UNBEKANNT:
        # Der Rueckfallweg (06.09.2026): die Gruppe hat die Fragen selbst
        # diktiert und ueber die Grundleiste abgenommen, statt sie aus
        # den zehn zu waehlen. Die Sensibilitaetspruefung laeuft
        # trotzdem -- sie haengt an den FRAGEN, nicht daran, wie sie
        # entstanden sind.
        starte_sensibilitaetspruefung(conn, d.tg, d.klm, d.e, d.chat_id)
    return meldung


def _speichere_einleitungen(conn, d: Druck, roh: str) -> str:
    """Die Einleitungen sind abgenommen -- ohne Zwischenfrage weiter zum
    Eroeffnungstext: die Gruppe soll die Verfeinerung als einen Weg erleben,
    nicht als drei Aufgaben.

    Seit dem 06.09.2026, 10:18 laeuft dieselbe Stufe unter ``fragen_weich``
    (die weiche Fassung ersetzt die Einleitung). Beide Arten gehen denselben
    Weg -- eine Gruppe, die den alten Vorschlag noch offen hatte, kann ihn
    trotzdem abnehmen."""
    meldung = _speichere(conn, d.tg, d.chat_id, roh, weiterfrage=False)
    if meldung != _TEXT_UNBEKANNT:
        repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", None)
        starte_eroeffnung(conn, d.tg, d.klm, d.e, d.chat_id)
    return meldung


def _speichere_kettenglied(conn, d: Druck, roh: str, gespeicherte_art: str) -> str:
    """Kernthema und Kernfrage tragen den Weg selbst weiter (Stufe 2 ->
    Stufe 3 -> Filter -> Figurenanzahl). Die allgemeine Weiterfrage ("Wollt ihr
    noch etwas hinzufuegen?") wuerde sich dazwischen stellen, deshalb
    ``weiterfrage=False``."""
    meldung = _speichere(
        conn, d.tg, d.chat_id, roh, weiterfrage=False, nur_bestaetigen=True,
    )
    if meldung not in (_TEXT_UNBEKANNT, _TEXT_SCHON_GESETZT):
        repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", None)
        _kette_weiter(conn, d.tg, d.klm, d.e, d.chat_id, gespeicherte_art)
    return meldung


def _wirkung_anders(conn, d: Druck) -> str:
    """"Passt, aber anders" SPEICHERT ebenfalls (05.09.2026 abends, Birk):
    damit ueberhaupt etwas in der Datenbank steht, auch wenn die Gruppe danach
    abbricht. Erst danach die gezielte Frage -- deterministisch, kein
    Modellaufruf (Zusage 2). Die naechste Bot-Antwort traegt die Leiste wieder,
    und ein "Gefaellt uns, weiter" darauf ueberschreibt den Wert (Journal: eine
    zweite Zeile, nichts wird geaendert)."""
    roh = d.wert
    gespeicherte_art = roh.partition(TRENNER)[0].strip()
    if gespeicherte_art in _NOTIERT or gespeicherte_art == "figuren":
        _speichere(conn, d.tg, d.chat_id, roh, weiterfrage=False)
        repo.setze_arbeitsstand(
            conn, d.chat_id, "aenderung_offen", gespeicherte_art
        )
    d.tg.sende(d.chat_id, _TEXT_ANDERS)
    return "Gespeichert, was soll anders sein?"


def _wirkung_eigene(conn, d: Druck) -> str:
    """Speichert NICHT. Der naechste Gruppenbeitrag ist der Vorschlag, und die
    Antwort darauf traegt die Leiste erneut."""
    repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", d.wert)
    d.tg.sende(d.chat_id, _TEXT_EIGENE)
    return "Erzaehlt"


def _wirkung_frage_wahl(conn, d: Druck) -> str:
    """**Stillgelegt** (06.09.2026, 10:05, Birk): die Toggle-Auswahl
    funktionierte am Telefon nicht. Angeboten werden diese Knoepfe nicht mehr
    (``_fragenleiste``); ein Druck aus einer alten Nachricht laeuft hier ins
    Leere und bekommt den Weg gesagt, statt still nichts zu tun."""
    d.tg.sende(d.chat_id, _TEXT_FRAGEN_WAHL)
    return _TEXT_FRAGEN_WAHL


def _wirkung_fragen_andere(conn, d: Druck) -> str:
    alte = _auswahlfragen(conn, d.chat_id)
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        ANWEISUNG_FRAGEN_ANDERE.format(
            alte="\n".join(f"- {f}" for f in alte)
        ),
    )
    return "Ich schlage andere vor"


def _wirkung_fragen_eigene(conn, d: Druck) -> str:
    """Speichert nichts: die naechste Nachricht der Gruppe sind ihre eigenen
    Fragen, und der naechste Zug baut daraus die Auswahl neu (``offene_art``
    liest den Merkposten)."""
    repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", "fragen")
    d.tg.sende(d.chat_id, _TEXT_FRAGEN_EIGENE)
    return "Erzaehlt"


def _wirkung_leitfaden(conn, d: Druck) -> str:
    from interview_theater import leitfaden

    leitfaden.sende(conn, d.tg, d.chat_id)
    return "Leitfaden"


def _wirkung_richtung(conn, d: Druck) -> str:
    """Stufe 1 der zweistufigen Kernthema-Wahl: die Richtung wird festgehalten,
    ``kernthema`` bleibt LEER -- eine Richtung ist kein Kernthema, und ein halb
    gefuelltes Feld waere schlimmer als ein leeres. Der zweite Schritt ist ein
    Gespraechszug im Thread."""
    richtung = d.wert.strip()
    repo.setze_arbeitsstand(conn, d.chat_id, "kernthema_richtung", richtung)
    repo.schreibe_journal(
        conn, d.chat_id, "vorgeschlagen", f"Richtung: {richtung}", quelle="knopf",
    )
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        ANWEISUNG_KERNTHEMA.format(richtung=richtung),
    )
    return "Richtung uebernommen"


def _wirkung_figuren_anzahl_menu(conn, d: Druck) -> str:
    """"Anzahl aendern" im Listen-Menue und die Erstfrage sind derselbe Weg und
    schreiben dasselbe Feld -- nur der Fragetext ist ein anderer, weil hier
    schon eine Liste dasteht."""
    biete_figurenanzahl(conn, d.tg, d.chat_id, _TEXT_FIGUREN_ANZAHL_FRAGE)
    return "Wie viele?"


def _wirkung_figuren_anzahl(conn, d: Druck) -> str:
    anzahl = _zahl_aus(d.wert.strip())
    if anzahl is None:
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    uebernimm_figurenanzahl(conn, d.tg, d.klm, d.e, d.chat_id, anzahl)
    return f"{d.knopf['wert']} Figuren"


def _wirkung_figuren_anzahl_frei(conn, d: Druck) -> str:
    """Kein Modellaufruf, kein Wert: nur der Merkposten, dass die naechste
    Nachricht der Gruppe die Zahl ist (``ablauf.antworte`` liest ihn)."""
    erwarte_figurenanzahl(d.chat_id)
    d.tg.sende(d.chat_id, _TEXT_FIGUREN_ANZAHL_FREI_FRAGE)
    return "Sagt mir die Zahl"


def _wirkung_figuren_namen_menu(conn, d: Druck) -> str:
    zeilen = _entwurfszeilen(conn, d.chat_id)
    if not zeilen:
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    leiste = []
    for nr, zeile in enumerate(zeilen, start=1):
        name = zeile.split("—")[0].split(" - ")[0].strip()
        leiste.append(
            (
                f"Figur {nr}: {name}",
                _daten(repo.lege_knopf_an(
                    conn, d.chat_id, ART_FIGUR_NAME_MENU, str(nr - 1)
                )),
            )
        )
    message_id = d.tg.sende_mit_knoepfen(
        d.chat_id, _TEXT_FIGUREN_NAMEN_FRAGE, leiste
    )
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return "Welchen Namen?"


def _wirkung_figur_name_menu(conn, d: Druck) -> str:
    zeilen = _entwurfszeilen(conn, d.chat_id)
    index = int(d.knopf["wert"])
    if index >= len(zeilen):
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    # Der Index wandert in den Merkposten, damit der Namensdruck weiss,
    # WELCHE Zeile er ersetzt -- der Knopf traegt nur den Namen.
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", str(index))
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        ANWEISUNG_NAMEN.format(zeile=zeilen[index]),
    )
    return "Namen vorschlagen"


def _wirkung_figur_name(conn, d: Druck) -> str:
    return _ersetze_namen(conn, d.tg, d.chat_id, d.wert.strip())


def _wirkung_figur_passt(conn, d: Druck) -> str:
    figur = repo.hole_figur(conn, d.chat_id, d.wert)
    if figur is not None:
        repo.setze_figur_geprueft(conn, figur["id"], repo._jetzt())
    stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Passt"


def _wirkung_figur_interview_menu(conn, d: Druck) -> str:
    return _biete_interviews(conn, d.tg, d.chat_id, d.wert)


def _wirkung_figur_interview(conn, d: Druck) -> str:
    name, _, roh_id = d.wert.partition(TRENNER)
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None or not roh_id.isdigit():
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    repo.setze_figur_quelle(conn, figur["id"], int(roh_id))
    # Das alte Sprachprofil gehoert zum alten Interview -- es wird neu
    # erzeugt (im Thread), und die Figur ist wieder offen.
    repo.setze_sprachprofil(conn, figur["id"], "", [])
    repo.setze_figur_geprueft(conn, figur["id"], None)
    stelle_figur_vor(
        conn, d.tg, d.klm, d.e, d.chat_id, repo.hole_figur(conn, d.chat_id, name)
    )
    return "Interview gewechselt"


def _wirkung_figur_duktus_menu(conn, d: Druck) -> str:
    name = d.wert
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", name)
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id, ANWEISUNG_DUKTUS.format(name=name)
    )
    return "Duktus-Vorschlaege"


def _wirkung_figur_duktus(conn, d: Druck) -> str:
    stand = repo.hole_arbeitsstand(conn, d.chat_id)
    name = (stand["figur_aktuell"] if stand else "") or ""
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None:
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    # Die Zitate bleiben stehen: sie sind belegt (``zitat.pruefe``) und
    # haengen am Interview, nicht an der Beschreibung.
    zitate = [z for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER) if z]
    repo.setze_sprachprofil(conn, figur["id"], d.wert.strip(), zitate)
    repo.setze_figur_geprueft(conn, figur["id"], None)
    stelle_figur_vor(
        conn, d.tg, d.klm, d.e, d.chat_id, repo.hole_figur(conn, d.chat_id, name)
    )
    return "Duktus uebernommen"


def _wirkung_figur_entfernen(conn, d: Druck) -> str:
    name = repo.entferne_figur(conn, d.chat_id, d.wert)
    if name:
        repo.schreibe_journal(
            conn, d.chat_id, "entschieden", f"Figur entfernt: {name}",
            quelle="knopf",
        )
        d.tg.sende(d.chat_id, f"{name} ist raus.")
    stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Entfernt"


def _wirkung_rahmen(conn, d: Druck) -> str:
    return _speichere(
        conn, d.tg, d.chat_id, f"rahmen{TRENNER}{d.knopf['wert']}"
    )


def _wirkung_wir_zuerst(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, _TEXT_WIR_ZUERST)
    return "Wir hoeren zu"


def _wirkung_schlag_vor(conn, d: Druck) -> str:
    """"Schlag du vor" -- je Phase ein anderer Weg, aber nirgends ein
    Modellaufruf hier: alle drei geben an einen eigenen Thread ab."""
    phase = int(d.knopf["wert"] or 0)
    if phase == PHASE_SETTING and offene_art(conn, d.chat_id) == "geschichte":
        # Innerhalb von Phase 4 hat die GESCHICHTE einen eigenen Weg
        # (``szenenfolge.starte_geschichte``): Bogen + Ende + Szenenfolge
        # mit fester Zeilenform, OHNE Material. Welche Ebene gemeint ist,
        # sagt ``offene_art`` -- steht die Figurenliste, ist es die
        # Geschichte, sonst Setting oder Figuren. Eigener Thread.
        from interview_theater import szenenfolge

        szenenfolge.starte_geschichte(conn, d.tg, d.klm, d.e, d.chat_id)
        return "Ich schlage vor"
    if phase == PHASE_SZENEN:
        # Die Szenentexte-Phase hat einen eigenen Weg
        # (``szenenfolge.starte``): der Vorschlag ist eine Szenenfolge
        # mit fester Zeilenform, kein freier Gespraechszug -- und er
        # traegt danach seine eigenen Knoepfe ("Anzahl aendern",
        # "Reihenfolge aendern"). Auch er laeuft in einem eigenen
        # Thread, kein Modellaufruf hier.
        from interview_theater import szenenfolge

        szenenfolge.starte(conn, d.tg, d.klm, d.e, d.chat_id)
        return "Ich schlage vor"
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        ANWEISUNGEN.get(phase, _ANWEISUNG_ALLGEMEIN),
    )
    return "Ich schlage vor"


def _wirkung_auswerten_alle(conn, d: Druck) -> str:
    return _werte_alle_aus(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_teil_weiter(conn, d: Druck) -> str:
    """Kein Modellaufruf (Zusage 2), keine Schreibwirkung: die Aufnahme laeuft
    ohnehin weiter. Der Knopf ist die Antwort auf eine Frage, die sonst offen
    im Chat stuende -- und die Tastatur ist danach weg (``behandle`` nimmt sie
    ab), was fuer sich schon die Rueckmeldung ist."""
    d.tg.sende(d.chat_id, _TEXT_TEIL_WEITER)
    return "Ich hoere weiter zu"


def _wirkung_teil_fertig(conn, d: Druck) -> str:
    """Wortgleich dasselbe wie "Interview beenden": derselbe Umschalter,
    dieselbe Verdichtung, dieselbe Nach-Interview-Leiste. Kein zweiter Weg fuer
    dieselbe Sache -- deshalb der Umweg ueber /aufnahme statt einer eigenen
    Abfolge hier."""
    from interview_theater import befehle

    if not repo.ist_interviewmodus_an(conn, d.chat_id):
        d.tg.sende(d.chat_id, _TEXT_TEIL_SCHON_AUS)
        return _TEXT_TEIL_SCHON_AUS
    befehle._befehl_aufnahme(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Interview beendet"


def _wirkung_kernthema(conn, d: Druck) -> str:
    """Der eigentliche Punkt der Uebung: deterministisch schreiben, was der
    Erkenner live nicht zuverlaessig traf."""
    repo.setze_arbeitsstand(conn, d.chat_id, "kernthema", d.knopf["wert"])
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden", f"Kernthema: {d.knopf['wert']}",
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, f"Kernthema notiert: {d.knopf['wert']}")
    return "Kernthema uebernommen"


def _wirkung_aufnahme(conn, d: Druck) -> str:
    """Wortgleich dasselbe wie /aufnahme -- inklusive der Verdichtung im
    eigenen Thread. Kein zweiter Weg fuer dieselbe Sache.

    Import erst hier: ``befehle`` bietet Knoepfe an (biete_kernthema) und
    ``knoepfe`` ruft einen Befehl auf -- ein Modulimport oben waere ein Zyklus.
    Der Aufruf ist selten (ein Knopfdruck), der Import danach im
    sys.modules-Cache."""
    from interview_theater import befehle

    befehle._befehl_aufnahme(conn, d.tg, d.klm, d.e, d.chat_id)
    return "Aufnahme umgeschaltet"


def _wirkung_noch_nicht(conn, d: Druck) -> str:
    """Das Phasenangebot ist abgelehnt -- aber nicht fuer immer (06.09.2026,
    Nacht-Simulation Punkt 6). Der Merkposten wird NEGATIV gesetzt: still
    bleibt es weiterhin, bis die Gruppe wirklich etwas aendert; der naechste
    gespeicherte Parameter derselben Phase holt das Angebot dann einmal zurueck
    (``phasen.erneuere_nach_aenderung``). Vorher stand hier nichts, und das
    Angebot war nach diesem Druck fuer immer weg."""
    try:
        phasen.lehne_angebot_ab(conn, d.chat_id, int(d.knopf["wert"]))
    except (TypeError, ValueError):
        pass
    d.tg.sende(d.chat_id, _TEXT_NOCH_NICHT)
    return _TEXT_NOCH_NICHT


def _wirkung_phase(conn, d: Druck) -> str:
    nummer = int(d.knopf["wert"])
    if phasen.setze(conn, d.chat_id, nummer, "knopf"):
        d.tg.sende(d.chat_id, phasen.meldung(nummer))
    # Ein Weg fuer alle acht Phasen (06.09.2026): Eintrittsnachricht mit
    # Kopfzeile, Einleitung und Checkliste, darunter die Einstiegsknoepfe
    # dieser Phase.
    eintritt_in_phase(conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    return f"Phase {nummer}"


def _wirkung_auswerten(conn, d: Druck) -> str:
    """Zwei Faelle, beide deterministisch und ohne Modellaufruf in DIESEM
    Handler (Zusage 2 im Moduldocstring):

    1. Es gibt schon eine Verdichtung (der Normalfall seit 05.09.2026:
       verdichtet wird sofort, ausgespielt erst auf Wunsch) -- dann wird sie
       hier direkt aus der Datenbank in den Chat gestellt. Genau das hat im
       Live-Lauf gefehlt: die Gruppe fragte zweimal nach der Auswertung und
       bekam Text statt Inhalt.
    2. Es gibt keine (Interview unter ``aufnahme.MINDEST_WOERTER``) -- dann
       laeuft wortgleich das, was ``/auswerten`` tut:
       ``aufnahme.starte_auswertung`` in einem eigenen Thread, und die fertige
       Verdichtung geht von dort in den Chat (``_interview_abschliessen`` mit
       ``erzwungen=True``)."""
    from interview_theater import aufnahme

    kopf_id = int(d.knopf["wert"])
    kopf = repo.hole_aufnahme(conn, kopf_id)
    if kopf is None:
        d.tg.sende(d.chat_id, _TEXT_AUSWERTEN_UNBEKANNT)
        return _TEXT_AUSWERTEN_UNBEKANNT
    name = kopf["name"] or "Das Interview"
    if aufnahme.zeige_verdichtung(conn, d.tg, d.e, kopf_id):
        return "Auswertung"
    if d.klm is None:
        log.error("Auswerten-Knopf ohne Sprachmodell, chat_id=%s", d.chat_id)
        d.tg.sende(d.chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
        return _TEXT_AUSWERTEN_UNMOEGLICH
    d.tg.sende(d.chat_id, f"Ich werte {name} aus.")
    aufnahme.starte_auswertung(conn, d.tg, d.klm, d.e, kopf_id)
    return "Auswertung laeuft"


def _wirkung_zusammenfassung(conn, d: Druck) -> str:
    """Derselbe Anzeigepfad wie bisher hinter "Auswerten"
    (``aufnahme.zeige_verdichtung``), nur ehrlicher benannt: verdichtet ist
    laengst, gezeigt wird jetzt. Reine Leseabfrage, kein Modellaufruf
    (Zusage 2)."""
    from interview_theater import aufnahme

    kopf_id = int(d.knopf["wert"])
    if aufnahme.zeige_verdichtung(conn, d.tg, d.e, kopf_id):
        return "Zusammenfassung"
    d.tg.sende(d.chat_id, _TEXT_AUSWERTEN_UNBEKANNT)
    return _TEXT_AUSWERTEN_UNBEKANNT


def _wirkung_transkript(conn, d: Druck) -> str:
    """Der Wortlaut zum Gegenpruefen -- derselbe Text, den ``/wortlaut``
    ausspielt, in Teilen, wenn er laenger ist als ``telegram.NACHRICHT_GRENZE``.
    Deterministisch aus der Datenbank."""
    from interview_theater import telegram as telegram_modul

    kopf = repo.hole_aufnahme(conn, int(d.knopf["wert"]))
    text = (kopf["transkript"] or "").strip() if kopf is not None else ""
    if not text:
        d.tg.sende(d.chat_id, _TEXT_KEIN_TRANSKRIPT)
        return _TEXT_KEIN_TRANSKRIPT
    name = (kopf["name"] if kopf else None) or "Das Interview"
    for stueck in telegram_modul.teile_text(f"{name}, im Wortlaut:\n{text}"):
        d.tg.sende(d.chat_id, stueck)
    return "Transkript"


def _wirkung_stand(conn, d: Druck) -> str:
    from interview_theater import befehle

    befehle._befehl_stand(conn, d.tg, d.chat_id, d.e)
    return "Stand"


def _wirkung_hilfe(conn, d: Druck) -> str:
    from interview_theater import befehle

    befehle._befehl_hilfe(d.tg, d.e, d.chat_id)
    return "Hilfe"


def _wirkung_szenenform(conn, d: Druck) -> str:
    """Der wert traegt Nummer UND Form ("3:dialog") -- siehe biete_szenenform.
    Getrennt wird am ERSTEN ':', damit ein spaeter erweiterter Formname mit ':'
    nicht die Nummer zerlegt."""
    from interview_theater import szene as szene_modul

    roh_nummer, _, form = str(d.knopf["wert"]).partition(":")
    nummer = int(roh_nummer)
    szene_id = repo.stelle_szene_sicher(conn, d.chat_id, nummer)
    repo.setze_szenenfeld(conn, szene_id, "form", form)
    d.tg.sende(
        d.chat_id,
        szene_modul.planungszeile(conn, repo.hole_szene(conn, szene_id)),
    )
    # Jetzt, wo die Form bestaetigt ist, kommt die Schreibfrage: die
    # Formfrage steht seit dem 06.09.2026 VOR ihr, nicht neben ihr.
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is not None:
        biete_szene(conn, d.tg, d.chat_id, ziel)
    return f"Szene {nummer}: {form}"


def _wirkung_szene_usa(conn, d: Druck) -> str:
    """ACHTUNG, hier ist am 05.09.2026 schon ein Fehler passiert:
    ``repo.setze_szene_usa`` erwartet einen BOOL, nicht den String
    "ja"/"nein". Ein String ist in Python immer wahr -- ein "nein" haette als
    Zustimmung zur Datenuebermittlung in die USA geendet, also genau falsch
    herum bei der einen Entscheidung, bei der das niemand verzeiht. Deshalb der
    ausdrueckliche Vergleich."""
    ja = str(d.knopf["wert"]).strip().lower() == "ja"
    repo.setze_szene_usa(conn, d.chat_id, ja)
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        "US-Modell fuer Szenentexte: ja" if ja else "US-Modell fuer Szenentexte: nein",
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, _TEXT_USA_JA if ja else _TEXT_USA_NEIN)
    # Der Auftrag, der auf diese Antwort gewartet hat, laeuft jetzt --
    # ueber den Weg, den die Antwort festgelegt hat. Bisher tat das nur
    # der Erkenner-Pfad (gesprochenes "ja"); der Knopf setzte den Stand
    # und liess den Auftrag liegen (Live-Fall Testgruppe 05.09. 22:09:
    # "USA" gedrueckt, nichts passierte, ein spaeteres "ja" im Chat war
    # wirkungslos, weil der Stand nicht mehr "offen" war).
    auftrag = repo.hole_und_loesche_offenen_szenenauftrag(conn, d.chat_id)
    if auftrag:
        from interview_theater import szene

        szene.starte(conn, d.tg, d.klm, d.e, d.chat_id, auftrag)
    return "US-Modell: ja" if ja else "Bleibt in der Schweiz"


#: Die Dispatch-Tabelle: art -> Handler. Sie ersetzt die frueheren
#: if/elif-Kaskaden in ``_wirke`` und ``_wirke_phase6`` (06.09.2026) und ist
#: zugleich die Liste, an der sich die drei Zusagen aus dem Moduldocstring
#: pruefen lassen: ``tests/test_knoepfe_struktur.py`` liest sie per AST und
#: haelt fest, dass kein Handler ein Sprachmodell anfasst.
_WIRKUNGEN = {
    ART_SZENENFOLGE_SPEICHERN: _wirkung_szenenfolge_speichern,
    ART_GESCHICHTE_SPEICHERN: _wirkung_geschichte_speichern,
    ART_SCHAERFUNG_SZENE: _wirkung_schaerfung_szene,
    ART_SCHAERFUNG_FIGUR: _wirkung_schaerfung_figur,
    ART_SCHAERFUNG_RUNDE: _wirkung_schaerfung_runde,
    ART_SZENENFOLGE_ANZAHL: _wirkung_szenenfolge_anzahl,
    ART_SZENENFOLGE_ANZAHL_WERT: _wirkung_szenenfolge_anzahl_wert,
    ART_SZENENFOLGE_REIHENFOLGE: _wirkung_szenenfolge_reihenfolge,
    ART_SZENE_ZEIGEN: _wirkung_szene_zeigen,
    ART_SZENE_SCHREIBEN: _wirkung_szene_schreiben,
    ART_SZENE_PLANEN: _wirkung_szene_planen,
    ART_SZENE_FORM: _wirkung_szene_form,
    ART_SZENE_UEBERSPRINGEN: _wirkung_szene_ueberspringen,
    ART_SZENENFELDER_SPEICHERN: _wirkung_szenenfelder_speichern,
    ART_SZENE_PASST: _wirkung_szene_passt,
    ART_SZENE_ANDERS: _wirkung_szene_anders,
    ART_SZENE_NEU: _wirkung_szene_neu,
    ART_SZENE_SO_LASSEN: _wirkung_szene_so_lassen,
    ART_SZENE_NAECHSTE: _wirkung_szene_naechste,
    ART_DURCHLAUF_SZENE: _wirkung_durchlauf_szene,
    ART_PRUEFUNG_SZENE: _wirkung_pruefung_szene,
    ART_PRUEFUNG_LASSEN: _wirkung_pruefung_lassen,
    ART_PRUEFUNG_RUNDE: _wirkung_pruefung_runde,
    ART_TEXTBUCH: _wirkung_textbuch,
    ART_SPEICHERN: _wirkung_speichern,
    ART_ANDERS: _wirkung_anders,
    ART_EIGENE: _wirkung_eigene,
    ART_FRAGE_WAHL: _wirkung_frage_wahl,
    ART_FRAGEN_UEBERNEHMEN: _wirkung_frage_wahl,
    ART_FRAGEN_ANDERE: _wirkung_fragen_andere,
    ART_FRAGEN_EIGENE: _wirkung_fragen_eigene,
    ART_LEITFADEN: _wirkung_leitfaden,
    ART_RICHTUNG: _wirkung_richtung,
    ART_FIGUREN_ANZAHL_MENU: _wirkung_figuren_anzahl_menu,
    ART_FIGUREN_ANZAHL: _wirkung_figuren_anzahl,
    ART_FIGUREN_ANZAHL_FREI: _wirkung_figuren_anzahl_frei,
    ART_FIGUREN_NAMEN_MENU: _wirkung_figuren_namen_menu,
    ART_FIGUR_NAME_MENU: _wirkung_figur_name_menu,
    ART_FIGUR_NAME: _wirkung_figur_name,
    ART_FIGUR_PASST: _wirkung_figur_passt,
    ART_FIGUR_INTERVIEW_MENU: _wirkung_figur_interview_menu,
    ART_FIGUR_INTERVIEW: _wirkung_figur_interview,
    ART_FIGUR_DUKTUS_MENU: _wirkung_figur_duktus_menu,
    ART_FIGUR_DUKTUS: _wirkung_figur_duktus,
    ART_FIGUR_ENTFERNEN: _wirkung_figur_entfernen,
    ART_RAHMEN: _wirkung_rahmen,
    ART_WIR_ZUERST: _wirkung_wir_zuerst,
    ART_SCHLAG_VOR: _wirkung_schlag_vor,
    ART_AUSWERTEN_ALLE: _wirkung_auswerten_alle,
    ART_TEIL_WEITER: _wirkung_teil_weiter,
    ART_TEIL_FERTIG: _wirkung_teil_fertig,
    ART_KERNTHEMA: _wirkung_kernthema,
    ART_AUFNAHME: _wirkung_aufnahme,
    ART_NOCH_NICHT: _wirkung_noch_nicht,
    ART_PHASE: _wirkung_phase,
    ART_AUSWERTEN: _wirkung_auswerten,
    ART_ZUSAMMENFASSUNG: _wirkung_zusammenfassung,
    ART_TRANSKRIPT: _wirkung_transkript,
    ART_STAND: _wirkung_stand,
    ART_HILFE: _wirkung_hilfe,
    ART_SZENENFORM: _wirkung_szenenform,
    ART_SZENE_USA: _wirkung_szene_usa,
}


def _wirke(conn, tg, klm, e, knopf, chat_id: int) -> str:
    """Fuehrt die Wirkung eines beanspruchten Knopfes aus und liefert den
    kurzen Text fuer answerCallbackQuery.

    Wird NUR aufgerufen, wenn ``repo.beanspruche_knopf`` True geliefert hat --
    die Idempotenz haengt an dieser einen Bedingung und nicht daran, dass
    jede Wirkung fuer sich wiederholbar waere."""
    art = knopf["art"]
    wirkung = _WIRKUNGEN.get(art)
    if wirkung is None:
        # Unbekannte art: nur moeglich, wenn eine spaetere Fassung eine Art
        # einfuehrt und eine aeltere die Zeile liest. Nichts tun ist hier
        # richtig.
        log.error("Unbekannte Knopf-art %r, chat_id=%s", art, chat_id)
        return _TEXT_UNBEKANNT
    return wirkung(conn, Druck(tg, klm, e, knopf, chat_id))


def behandle(conn, tg, klm, e, druck: dict) -> bool:
    """Verarbeitet einen normalisierten Knopfdruck
    (``telegram.lies_knopfdruck``). Liefert True, wenn er zu diesem Bot
    gehoerte und beantwortet wurde.

    Antwortet IMMER mit answerCallbackQuery, auch wenn nichts geschieht --
    ohne diese Antwort dreht sich in der App eine Ladeanzeige weiter, und das
    sieht fuer die Gruppe nach einem haengenden Bot aus.

    Ein Knopf aus einer anderen Gruppe (``knopf.chat_id`` passt nicht) wirkt
    nicht: dieselbe Datenbank traegt alle Gruppen des Workshops, und eine
    weitergeleitete Nachricht darf nie in fremde Daten schreiben."""
    knopf_id = _id_aus_daten(druck["data"])
    if knopf_id is None:
        return False

    chat_id = druck["chat_id"]
    knopf = repo.hole_knopf(conn, knopf_id)
    if knopf is None or (chat_id is not None and knopf["chat_id"] != chat_id):
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_UNBEKANNT)
        return True

    chat_id = knopf["chat_id"]
    if not repo.beanspruche_knopf(conn, knopf_id):
        # Zweiter Druck: beantworten, aber nichts wiederholen (AGENTS.md).
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_SCHON_BENUTZT)
        _entferne_tastatur(tg, chat_id, druck["message_id"])
        return True

    meldung = _wirke(conn, tg, klm, e, knopf, chat_id)
    tg.beantworte_knopf(druck["callback_query_id"], meldung)
    _entferne_tastatur(tg, chat_id, druck["message_id"])
    return True


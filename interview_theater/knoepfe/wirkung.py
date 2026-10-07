"""Was ein gedrueckter Knopf tut -- die Dispatch-Tabelle und ihre Handler.

Je Knopfart eine benannte Funktion der Form ``(conn, d) -> str``, wobei ``d``
ein ``Druck`` ist (tg, klm, e, knopf, chat_id). Die Zuordnung steht in
``_WIRKUNGEN``; ``_wirke`` schlaegt nach und ruft auf, ``behandle`` ist der
Eingang aus ``bot.schleife``.

Vorher war das eine if/elif-Kaskade ueber 76 Knopfarten in drei Funktionen von
zusammen 937 Zeilen. Eine Tabelle laesst sich auslesen, eine Kaskade nicht --
genau darauf baut ``tests/test_knoepfe_struktur.py``, das die drei Zusagen des
Pakets am Quelltext prueft statt am Verhalten.
"""

from typing import NamedTuple

from interview_theater import phasen, repo, ruecknahme, sprache

from interview_theater.knoepfe.texte import (
    ART_ANDERS, ART_AUFNAHME, ART_AUSWERTEN, ART_AUSWERTEN_ALLE,
    ART_BOARD_AENDERN, ART_BOARD_UEBERNEHMEN,
    ART_DURCHLAUF_SZENE, ART_EIGENE, ART_ERSTENTWURF, ART_DRAMATURGIE,
    ART_DRAMATURGIE_LASSEN,
    ART_DRAMATURGIE_SZENE, ART_FASSUNGEN, ART_SPRECHANTEILE,
    ART_FIGUREN_ANZAHL, ART_FIGUREN_ANZAHL_FREI, ART_FIGUREN_ANZAHL_MENU,
    ART_FIGUREN_NAMEN_MENU, ART_FIGUREN_ZUFALL, ART_FIGUR_DUKTUS,
    ART_FIGUR_DUKTUS_MENU, ART_FIGUR_ENTFERNEN, ART_FIGUR_INTERVIEW,
    ART_FIGUR_INTERVIEW_MENU, ART_FIGUR_NAME, ART_FIGUR_NAME_MENU,
    ART_FIGUR_PASST, ART_FIGUR_STIL, ART_FIGUR_STIL_FREI, ART_FRAGEN_ANDERE,
    ART_FRAGEN_EIGENE, ART_FRAGEN_EINZELN, ART_FRAGEN_JA_VORSCHLAGEN,
    ART_FRAGEN_NOCH_EIGENE, ART_FRAGEN_UEBERNEHMEN,
    ART_FRAGEN_UMFORMULIEREN_ALLE, ART_FRAGEN_UMFORMULIEREN_ANBIETEN,
    ART_FRAGEN_UMFORMULIEREN_KEINE,
    ART_FRAGEN_VORSCHLAGEN,
    ART_FRAGEN_WEICH_LASSEN, ART_FRAGEN_WEICH_UEBERNEHMEN,
    ART_FRAGE_ANNEHMEN, ART_FRAGE_SCHAERFEN, ART_FRAGE_VERWERFEN,
    ART_FRAGE_WAHL,
    ART_GESCHICHTE_ANDERS, ART_GESCHICHTE_KUERZEN, ART_GESCHICHTE_NEU,
    ART_GESCHICHTE_PASST, ART_GESCHICHTE_SCHREIBEN, ART_GESCHICHTE_SPEICHERN,
    ART_HILFE, ART_INTERVIEWS_FERTIG, ART_KERNTHEMA, ART_LEITFADEN, ART_NOCH_NICHT,
    ART_OHNE_KNOPF_FERTIG, ART_OHNE_KNOPF_JA, ART_OHNE_KNOPF_NEIN,
    ART_OHNE_KNOPF_WEITER, ART_PHASE, ART_PRUEFUNG_LASSEN, ART_PRUEFUNG_RUNDE,
    ART_PRUEFUNG_SZENE, ART_RAHMEN, ART_REDO, ART_RICHTUNG, ART_SCHAERFUNG_FIGUR,
    ART_SCHAERFUNG_KEINE, ART_SCHAERFUNG_RUNDE, ART_SCHAERFUNG_STELLE,
    ART_SCHAERFUNG_SZENE, ART_SCHLAG_VOR, ART_SPEICHERN, ART_STAND,
    ART_SZENENFELDER_SPEICHERN, ART_SZENENFOLGE_ANZAHL,
    ART_SZENENFOLGE_ANZAHL_WERT, ART_SZENENFOLGE_REIHENFOLGE,
    ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM, ART_SZENENSTIL,
    ART_SZENE_ANDERS, ART_SZENE_FORM, ART_SZENE_KUERZEN, ART_SZENE_NAECHSTE,
    ART_SZENE_NEU, ART_SZENE_PASST, ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN,
    ART_SZENE_SO_LASSEN, ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA,
    ART_UEBERSICHT_ANDERS, ART_UEBERSICHT_PASST,
    ART_SPRECHWEISEN_ANDERS, ART_SPRECHWEISEN_PASST,
    ART_STT_SPRACHE, STT_KNOEPFE, T, ART_SZENE_ZEIGEN, ART_TEIL_FERTIG,
    ART_TEIL_WEITER, ART_TEXTBUCH, ART_TRANSKRIPT, ART_UNDO, ART_WIR_ZUERST,
    ART_FORMBERATER,
    ART_ZUSAMMENFASSUNG, PHASE_SETTING, PHASE_STUECKPRUEFUNG, PHASE_SZENEN, TRENNER, _KETTE, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _entferne_tastatur, _id_aus_daten, _merke_botnachricht, _mit_leiste,
    _sende_knoepfe,
    _speichere, _starte_auftrag, offene_art, redo_leiste,
)
from interview_theater.knoepfe.fragen import (
    _speichere_eroeffnung, entscheide, fragen_umformulierung_alle_annehmen,
    fragen_umformulierung_alle_verwerfen, frage_nach_eigenen,
    frage_nach_umformulierung, frage_waehlt_schaerfen,
    frage_warten_auf_richtung, frage_weich_lassen,
    frage_weich_uebernehmen, ja_vorschlagen, noch_eigene, starte_durchgehen,
    starte_eroeffnung,
)
from interview_theater.knoepfe.figuren import (
    _biete_interviews, _entwurfszeilen, _ersetze_namen, _interviewkoepfe,
    _kette_weiter, _schliesse_figuren_ab, _zahl_aus, biete_figurenanzahl,
    erwarte_figurenanzahl, ordne_figuren_zufaellig_zu, stelle_figur_vor,
    stelle_stil_vor, uebernimm_figurenanzahl,
)
from interview_theater.knoepfe.szenen import (
    _biete_weiter_nach_szene, _geschichte_notiz_erwartet, _melde_spaetere,
    _naechste_offene, _pruefbefund, _schreibe_szene, _speichere_geschichte,
    _speichere_szenenfelder, _speichere_szenenfolge, _szene_mit_nummer,
    biete_kurzgeschichte, biete_schaerfung, biete_szene, biete_szenenform,
    _zeige_fassungen, skript_verweis, starte_dramaturgie,
    biete_szenenstil, erwarte_geschichte_notiz, starte_schaerfung,
    starte_stueckpruefung, uebernimm_schaerfung_figur,
    uebernimm_schaerfung_szene, verwirf_schaerfung, zeige_szenentext,
)
from interview_theater.knoepfe.interviews import (
    _werte_alle_aus, biete_interview_ohne_knopf_weiter,
)
from interview_theater.knoepfe.stationen import (
    biete_phase_proaktiv, eintritt_in_phase,
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


# --- Die Wirkungen der Szenenfolge, der Geschichte und der Pruefung --------


def _wirkung_szenenfolge_speichern(conn, d: Druck) -> str:
    return _speichere_szenenfolge(conn, d.tg, d.klm, d.e, d.chat_id, d.wert)


def _wirkung_geschichte_schreiben(conn, d: Druck) -> str:
    """Der EINE Weg in den Prosa-Lauf (06.09.2026, Birk 11:50/12:25). Kein
    Modellaufruf hier: ``kurzgeschichte.starte`` gibt an einen Thread ab
    (Zusage 2)."""
    from interview_theater import kurzgeschichte

    _geschichte_notiz_erwartet.discard(d.chat_id)
    if kurzgeschichte.starte(conn, d.tg, d.klm, d.e, d.chat_id, None) is None:
        return T._ANTWORT_LAEUFT_SCHON
    return T._ANTWORT_GESCHICHTE_LAEUFT


def _wirkung_geschichte_passt(conn, d: Druck) -> str:
    from interview_theater import ueberarbeitung

    if ueberarbeitung.aktiv() and phasen.aktuelle(conn, d.chat_id) == PHASE_SZENEN:
        # Padua (Phase 6, Rewrite): das Ganze ist fixiert, jetzt Szene fuer
        # Szene. Kein Modellaufruf hier -- der Prueflauf laeuft im Thread.
        # Ein veralteter Knopf auf dem schon fixierten Ganzen wirkt nicht
        # noch einmal (Fix-Runde 1): kurzer Toast, keine Zustandsaenderung.
        if ueberarbeitung.gesamttext_fixiert(conn, d.chat_id):
            return ueberarbeitung.T._ANTWORT_SCHON_GESPEICHERT
        return ueberarbeitung.bestaetige_gesamt(conn, d.tg, d.klm, d.e, d.chat_id)
    d.tg.sende(d.chat_id, T._TEXT_GESCHICHTE_PASST)
    biete_phase_proaktiv(conn, d.tg, d.chat_id)
    return T._ANTWORT_PASST


def _wirkung_geschichte_anders(conn, d: Druck) -> str:
    """Speichert nichts: die naechste Nachricht der Gruppe ist die Regie-Notiz.
    ``ablauf.antworte`` greift sie ueber ``nimm_geschichte_notiz`` auf und
    startet damit den naechsten Lauf -- dieselbe Bauart wie
    ``szenenfolge.nimm_regienotiz`` fuer die einzelne Szene."""
    erwarte_geschichte_notiz(d.chat_id)
    d.tg.sende(d.chat_id, T._TEXT_GESCHICHTE_ANDERS)
    return T._ANTWORT_WAS_ANDERS


def _wirkung_geschichte_kuerzen(conn, d: Druck) -> str:
    """"Kuerzer" unter der ganzen Kurzgeschichte (30.09.2026, C4).

    Anders als "Etwas aendern" fragt es nichts: die Notiz steht fest
    (``kuerzung.notiz_fuer_prosa``), und der Lauf startet sofort. Kein
    Modellaufruf hier -- ``kuerzung.starte`` gibt an einen Thread ab
    (Zusage 2)."""
    from interview_theater import kuerzung

    _geschichte_notiz_erwartet.discard(d.chat_id)
    meldung, _gestartet = kuerzung.starte(conn, d.tg, d.klm, d.e, d.chat_id)
    return meldung


def _wirkung_geschichte_neu(conn, d: Druck) -> str:
    """"Ganz neu" ist eine vollstaendige Aussage: kein Rueckfragen, der Lauf
    startet sofort und ohne Notiz."""
    from interview_theater import kurzgeschichte

    _geschichte_notiz_erwartet.discard(d.chat_id)
    if kurzgeschichte.starte(conn, d.tg, d.klm, d.e, d.chat_id, None) is None:
        return T._ANTWORT_LAEUFT_SCHON
    return T._ANTWORT_GESCHICHTE_LAEUFT


def _wirkung_geschichte_speichern(conn, d: Druck) -> str:
    return _speichere_geschichte(conn, d.tg, d.klm, d.e, d.chat_id, d.wert)


def _wirkung_schaerfung_szene(conn, d: Druck) -> str:
    """Die Uebernahme ist deterministisch (Felder ergaenzen), der naechste
    Vorschlag kommt aus der Datenbank -- kein Modellaufruf (Zusage 2). Der
    Rumpf steht in ``szenen.uebernimm_schaerfung_szene`` -- derselbe fuer
    den Erkenner (``schaerfung_entscheidung``, Padua Phasen TEIL 2)."""
    modus, _, nummer_roh = d.wert.partition(TRENNER)
    return uebernimm_schaerfung_szene(
        conn, d.tg, d.chat_id, int(nummer_roh or d.wert),
        anders=modus.strip() == "anders")


def _wirkung_schaerfung_figur(conn, d: Druck) -> str:
    modus, _, name = d.wert.partition(TRENNER)
    return uebernimm_schaerfung_figur(
        conn, d.tg, d.chat_id, name or d.wert, anders=modus.strip() == "anders")


def _wirkung_schaerfung_stelle(conn, d: Druck) -> str:
    """EIN Knopf, EINE Stelle (06.09.2026). Deterministisch, kein
    Modellaufruf; die naechste offene Stelle kommt sofort danach."""
    from interview_theater import schaerfung as schaerfung_modul

    roh = d.wert.strip()
    ziel = (
        schaerfung_modul.uebernimm_stelle(conn, d.chat_id, int(roh))
        if roh.isdigit()
        else None
    )
    if ziel is None:
        d.tg.sende(d.chat_id, T._TEXT_SCHAERFUNG_STELLE_UNBEKANNT)
        return T._TEXT_SCHAERFUNG_STELLE_UNBEKANNT
    d.tg.sende(d.chat_id, T._TEXT_SCHAERFUNG_STELLE_UEBERNOMMEN.format(ziel=ziel))
    biete_schaerfung(conn, d.tg, d.chat_id)
    return T._ANTWORT_UEBERNOMMEN.format(was=ziel)


def _wirkung_schaerfung_keine(conn, d: Druck) -> str:
    ids = [t.strip() for t in d.wert.split(TRENNER) if t.strip().isdigit()]
    return verwirf_schaerfung(conn, d.tg, d.chat_id, [int(t) for t in ids])


def _wirkung_schaerfung_runde(conn, d: Druck) -> str:
    """Eine weitere Runde mit dem inzwischen geschaerften Stand -- der Lauf
    haengt im Thread, hier wird nur angestossen."""
    starte_schaerfung(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_NOCH_EINE_RUNDE


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
    _mit_leiste(conn, d.tg, d.chat_id, T._TEXT_ANZAHL_FRAGE, leiste)
    return T._ANTWORT_WIE_VIELE


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
    return T._ANTWORT_SZENEN_ANZAHL.format(anzahl=d.wert)


def _wirkung_szenenfolge_reihenfolge(conn, d: Druck) -> str:
    """Der Bot fragt; die naechste Nachricht wirkt ueber den normalen
    Gespraechszug, der den Vorschlag neu baut. Kein Modellaufruf hier."""
    d.tg.sende(d.chat_id, T._TEXT_REIHENFOLGE_FRAGE)
    return T._ANTWORT_REIHENFOLGE


def _wirkung_szene_zeigen(conn, d: Druck) -> str:
    ziel = _szene_mit_nummer(conn, d.chat_id, int(d.wert))
    if ziel is None:
        d.tg.sende(d.chat_id, T._TEXT_SZENE_UNBEKANNT)
        return T._TEXT_SZENE_UNBEKANNT
    biete_szene(conn, d.tg, d.chat_id, ziel)
    return T._TEXT_SZENE_KOPF.format(nummer=d.wert)


def _wirkung_szene_schreiben(conn, d: Druck) -> str:
    return _schreibe_szene(conn, d.tg, d.klm, d.e, d.chat_id, int(d.wert))


def _wirkung_szene_planen(conn, d: Druck) -> str:
    """Wie "Nochmal anders": ein Satz, kein Modellaufruf. Was die Gruppe danach
    sagt, laeuft ueber den Erkenner (art szene_planen) oder den Gespraechszug
    -- beide Wege setzen die Felder und stellen die Szene neu vor."""
    d.tg.sende(d.chat_id, T._TEXT_SZENE_PLANEN_FRAGE)
    return T._ANTWORT_WAS_ANDERS


def _wirkung_szene_form(conn, d: Druck) -> str:
    biete_szenenform(conn, d.tg, d.chat_id, int(d.wert))
    return T._ANTWORT_WELCHE_FORM


def _wirkung_szene_ueberspringen(conn, d: Druck) -> str:
    nummer = int(d.wert)
    # Weich (N3): die Szene ist raus, aber nichts ist weg -- eine Gruppe,
    # die es sich anders ueberlegt, hat sie noch.
    entfernt = repo.entferne_szene(conn, d.chat_id, nummer)
    if entfernt is None:
        d.tg.sende(d.chat_id, T._TEXT_SZENE_UNBEKANNT)
        return T._TEXT_SZENE_UNBEKANNT
    d.tg.sende(d.chat_id, T._TEXT_SZENE_UEBERSPRUNGEN.format(nummer=nummer))
    naechste = _naechste_offene(conn, d.chat_id, nummer)
    if naechste is not None:
        biete_szene(conn, d.tg, d.chat_id, naechste)
    return T._ANTWORT_SZENE_RAUS.format(nummer=nummer)


def _wirkung_szenenfelder_speichern(conn, d: Druck) -> str:
    modus, _, rest = d.wert.partition(TRENNER)
    meldung = _speichere_szenenfelder(conn, d.tg, d.chat_id, rest)
    if modus.strip() == "anders":
        d.tg.sende(d.chat_id, T._TEXT_ANDERS)
    return meldung


def _wirkung_szene_passt(conn, d: Druck) -> str:
    nummer = int(d.wert)
    # Padua Phasen TEIL 1 (03.10.2026): derselbe Knopf, zwei Bedeutungen --
    # in Phase 5 ist "Passt" die Abnahme EINES Prosa-Entwurfs in Stufe B
    # (``entwurf.py``), nicht die Abnahme eines fertigen Theatertexts. Die
    # Phase entscheidet, welcher Weg laeuft; fuer jede andere Phase (heute 7)
    # bleibt alles darunter unveraendert.
    if phasen.aktuelle(conn, d.chat_id) == 5:
        return _wirkung_entwurf_szene_passt(conn, d, nummer)
    from interview_theater import ueberarbeitung

    if ueberarbeitung.aktiv() and phasen.aktuelle(conn, d.chat_id) == PHASE_SZENEN:
        # Padua (Phase 6, Rewrite): Szene abnehmen, naechste pruefen -- nach
        # der letzten automatisch Phase 7.
        return ueberarbeitung.bestaetige_szene_6(
            conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    if ueberarbeitung.aktiv() and phasen.aktuelle(conn, d.chat_id) == PHASE_STUECKPRUEFUNG:
        # Padua (Phase 7, Stage Version): Szene abnehmen, naechste
        # uebertragen -- nach der letzten die Pruefung des ganzen Textbuchs.
        return ueberarbeitung.bestaetige_szene_7(
            conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is None:
        d.tg.sende(d.chat_id, T._TEXT_SZENE_UNBEKANNT)
        return T._TEXT_SZENE_UNBEKANNT
    repo.setze_szene_fertig(conn, ziel["id"], True)
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_SZENE_ABGENOMMEN.format(
            nummer=nummer, titel=ziel["titel"] or ""
        ).strip(),
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, T._TEXT_PASST.format(nummer=nummer))
    _biete_weiter_nach_szene(conn, d.tg, d.chat_id, nummer)
    return T._ANTWORT_SZENE_STEHT.format(nummer=nummer)


def _wirkung_entwurf_szene_passt(conn, d: Druck, nummer: int) -> str:
    """"Yes, save" auf einem Prosa-Entwurf in Stufe B von Phase 5 (Padua
    Phasen TEIL 1): Szene abnehmen, automatisch weiter -- zur naechsten
    offenen Szene (kein Knopf, kein Warten) oder, wenn keine mehr offen
    ist, automatisch nach Phase 6. Das ist die EINE, ausdruecklich von
    Birk gewuenschte Ausnahme vom sonst geltenden "Datenstand ist nicht
    Absicht" (AGENTS.md) -- lokal auf diesen Abschluss begrenzt,
    ``phasen.moegliche_naechste``/``offenes_angebot`` bleiben fuer jeden
    anderen Uebergang unveraendert. Der Rumpf steht seit Padua Phasen TEIL 2
    in ``entwurf.bestaetige_szene`` -- derselbe fuer den Erkenner
    (``fassung_abnehmen``)."""
    from interview_theater import entwurf

    return entwurf.bestaetige_szene(conn, d.tg, d.klm, d.e, d.chat_id, nummer)


def _wirkung_szene_anders(conn, d: Druck) -> str:
    """Der Regie-Vermerk kommt als naechste Nachricht; ``ablauf.antworte``
    greift ihn auf (``szenenfolge.nimm_regienotiz``) und schreibt die Szene
    damit neu. Kein Modellaufruf hier."""
    from interview_theater import szenenfolge

    nummer = int(d.wert)
    szenenfolge.erwarte_regienotiz(d.chat_id, nummer)
    d.tg.sende(d.chat_id, T._TEXT_SZENE_ANDERS_FRAGE)
    _melde_spaetere(conn, d.tg, d.chat_id, nummer)
    return T._ANTWORT_WAS_ANDERS_WERDEN


def _wirkung_uebersicht_passt(conn, d: Druck) -> str:
    """"Yes, save": die Geschichts-Uebersicht aus Stufe A von Phase 5 (Prose
    Draft, ``entwurf.py``) ist fix (Padua Phasen TEIL 1, 03.10.2026).

    Kein Modellaufruf hier (Zusage 2): die Pflichtfelder der Szenen werden
    rein aus dem schon erzeugten Uebersicht-Text uebernommen
    (``entwurf.uebernimm_szenenfelder``), und die erste noch offene Szene
    geht ueber das bestehende ``szene.starte`` -- das gibt seinerseits sofort
    an einen eigenen Thread ab. Der Rumpf steht seit Padua Phasen TEIL 2 in
    ``entwurf.fixiere_uebersicht`` -- derselbe fuer den Erkenner
    (``fassung_abnehmen``)."""
    from interview_theater import entwurf

    return entwurf.fixiere_uebersicht(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_erstentwurf(conn, d: Druck) -> str:
    """"Erste Fassung zeigen" unter dem Hinweis nach einem Prueflauf (Padua
    Phasen TEIL 2). Kein Modellaufruf (Zusage 2), und auch kein Volltext im
    Chat: der Knopf sagt, wo die Fassung vor der Pruefung steht. ``wert``
    ``""`` heisst die ganze Geschichte, sonst eine Szenennummer."""
    if d.wert.strip():
        ziel = _szene_mit_nummer(conn, d.chat_id, int(d.wert))
        szenen = [ziel] if ziel is not None else []
    else:
        szenen = list(repo.hole_szenen(conn, d.chat_id))
    if not any(repo.erstentwurf_text(conn, s["id"]) for s in szenen):
        message_id = d.tg.sende(d.chat_id, T._TEXT_KEIN_ERSTENTWURF)
        repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e,
                             T._TEXT_KEIN_ERSTENTWURF)
        return T._TEXT_KEIN_ERSTENTWURF
    text = f"{T._TEXT_ERSTENTWURF}\n{skript_verweis(conn, d.e, d.chat_id)}"
    message_id = d.tg.sende(d.chat_id, text)
    repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, text)
    return text


def _wirkung_uebersicht_anders(conn, d: Druck) -> str:
    """"No, change it again": ein neuer Uebersicht-Lauf (Padua Phasen TEIL 1).

    Kein Modellaufruf hier (Zusage 2) -- ``entwurf.starte_uebersicht`` gibt
    sofort an einen eigenen Thread ab, wie jeder andere Vorschlagslauf."""
    from interview_theater import entwurf

    entwurf.starte_uebersicht(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._TEXT_UEBERSICHT_WIRD_NEU_ERZEUGT


def _wirkung_sprechweisen_passt(conn, d: Druck) -> str:
    """"Yes, save" unter den Sprechweisen (Padua, Phase 7): fixieren und
    weiter zur ersten Szene. Kein Modellaufruf hier -- der Szenenlauf geht
    ueber ``szene.starte`` in einen eigenen Thread."""
    from interview_theater import ueberarbeitung

    return ueberarbeitung.bestaetige_sprechweisen(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_sprechweisen_anders(conn, d: Druck) -> str:
    """"No, change it again" unter den Sprechweisen: nur nachfragen. Die
    Antwort im Chat setzt der Erkenner (``sprechweise_setzen``, Task 10)."""
    message_id = d.tg.sende(d.chat_id, T._TEXT_SPRECHWEISEN_AENDERN)
    repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, T._TEXT_SPRECHWEISEN_AENDERN)
    return T._TEXT_SPRECHWEISEN_AENDERN


def _wirkung_szene_kuerzen(conn, d: Druck) -> str:
    """"Kuerzer" unter EINEM Szenentext (30.09.2026, C4).

    Derselbe Ueberarbeitungspfad wie "Passt, aber anders", nur ohne
    Rueckfrage: die Notiz steht fest. Spaetere geschriebene Szenen bekommen
    ihren Pruef-Vermerk wie bei jeder Aenderung -- das setzt
    ``kuerzung.starte`` selbst, nur mit Lauf und fuer Knopf und Erkenner
    gleich (``_melde_spaetere``). Kein
    Modellaufruf hier (Zusage 2)."""
    from interview_theater import kuerzung

    nummer = kuerzung.nummer_aus_wert(d.wert)
    if nummer is None:
        d.tg.sende(d.chat_id, T._TEXT_SZENE_UNBEKANNT)
        return T._TEXT_SZENE_UNBEKANNT
    meldung, _gestartet = kuerzung.starte(
        conn, d.tg, d.klm, d.e, d.chat_id, nummer,
    )
    return meldung


def _wirkung_szene_neu(conn, d: Druck) -> str:
    from interview_theater import szene as szene_modul, szenenfolge

    nummer = int(d.wert)
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is None:
        d.tg.sende(d.chat_id, T._TEXT_SZENE_UNBEKANNT)
        return T._TEXT_SZENE_UNBEKANNT
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
    d.tg.sende(d.chat_id, T._TEXT_SZENE_SO_GELASSEN.format(nummer=nummer))
    _biete_weiter_nach_szene(conn, d.tg, d.chat_id, nummer)
    return T._ANTWORT_SZENE_BLEIBT.format(nummer=nummer)


def _wirkung_szene_naechste(conn, d: Druck) -> str:
    naechste = _naechste_offene(conn, d.chat_id, int(d.wert))
    if naechste is None:
        _biete_weiter_nach_szene(conn, d.tg, d.chat_id, int(d.wert))
        return T._ANTWORT_LETZTE
    biete_szene(conn, d.tg, d.chat_id, naechste)
    return T._TEXT_SZENE_KOPF.format(nummer=naechste["nummer"])


def _wirkung_durchlauf_szene(conn, d: Druck) -> str:
    return zeige_szenentext(conn, d.tg, d.chat_id, int(d.wert))


def _wirkung_pruefung_szene(conn, d: Druck) -> str:
    """"Szene N ueberarbeiten" geht den bestehenden Weg "Passt, aber anders":
    ein Szenenauftrag mit dem Vorschlag als Regie-Notiz. Kein Modellaufruf hier
    -- ``ablauf.starte_auftrag`` gibt an einen eigenen Thread ab (Zusage 2)."""
    befund = _pruefbefund(conn, d.chat_id, int(d.wert))
    if befund is None or befund["szene_nummer"] is None:
        d.tg.sende(d.chat_id, T._TEXT_PRUEFUNG_UNBEKANNT)
        return T._TEXT_PRUEFUNG_UNBEKANNT
    from interview_theater import ablauf, stueckpruefung as pruefung_modul
    from interview_theater import szene as szene_modul

    nummer = int(befund["szene_nummer"])
    ablauf.starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        szene_modul.T.TEXT_AUFTRAG_NEU.format(
            nummer=nummer, notiz=pruefung_modul.regienotiz(befund)),
    )
    # Nach einer Ueberarbeitung gilt der Stand als ungeprueft -- gesagt,
    # nicht automatisch nachgelaufen (Birk).
    d.tg.sende(d.chat_id, T._TEXT_PRUEFUNG_UEBERHOLT)
    return T._ANTWORT_SZENE_UEBERARBEITET.format(nummer=nummer)


def _wirkung_pruefung_lassen(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, T._TEXT_PRUEFUNG_LASSEN)
    return T._ANTWORT_BLEIBT


def _wirkung_dramaturgie(conn, d: Druck) -> str:
    """Kein Modellaufruf im Handler: ``fanout.starte`` gibt an einen eigenen
    Thread ab (Zusage 2)."""
    starte_dramaturgie(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_SZENEN_EINZELN


def _wirkung_dramaturgie_szene(conn, d: Druck) -> str:
    """Derselbe Weg wie "Szene N ueberarbeiten" nach der Stueckpruefung: ein
    Szenenauftrag mit dem Umbauvorschlag als Regie-Notiz. **Erst der
    Knopfdruck** loest ihn aus -- ein Befund allein aendert nichts."""
    from interview_theater.dramaturgie import fanout

    befund = repo.hole_dramaturgie_befund(conn, d.chat_id, int(d.wert))
    if befund is None or befund["szene"] is None:
        d.tg.sende(d.chat_id, T._TEXT_DRAMATURGIE_UNBEKANNT)
        return T._TEXT_DRAMATURGIE_UNBEKANNT
    from interview_theater import ablauf

    nummer = int(befund["szene"])
    ablauf.starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id, fanout.szenenauftrag(befund),
    )
    d.tg.sende(d.chat_id, T._TEXT_DRAMATURGIE_UEBERHOLT)
    return T._ANTWORT_SZENE_UEBERARBEITET.format(nummer=nummer)


def _wirkung_dramaturgie_lassen(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, T._TEXT_DRAMATURGIE_LASSEN)
    return T._ANTWORT_BLEIBT


def _wirkung_pruefung_runde(conn, d: Druck) -> str:
    """Noch eine Pruefrunde: derselbe Weg wie beim Eintritt in die Phase, die
    Runde zaehlt in ``repo.letzte_pruefrunde`` von selbst hoch."""
    starte_stueckpruefung(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_NOCH_EINMAL


def _wirkung_textbuch(conn, d: Druck) -> str:
    from interview_theater import szenenfolge

    text = szenenfolge.textbuch(conn, d.chat_id)
    try:
        d.tg.sende_datei(
            d.chat_id, szenenfolge.dateiname(d.chat_id), text,
            T._TEXT_TEXTBUCH_BESCHREIBUNG,
        )
    except Exception:
        # Scheitert sendDocument (alte Telegram-Attrappe, Rechte in der
        # Gruppe), soll die Gruppe nicht ratlos dastehen: eine Zeile, und
        # die Szenen sind ueber "Szene N ansehen" weiter erreichbar.
        log.exception("Textbuch-Datei fehlgeschlagen, chat_id=%s", d.chat_id)
        d.tg.sende(d.chat_id, T._TEXT_TEXTBUCH_FEHLER)
        return T._TEXT_TEXTBUCH_FEHLER
    return T._ANTWORT_TEXTBUCH


def _wirkung_formberater(conn, d: Druck) -> str:
    """"Weitere Formen & Gegenpol" (Karte t_256ec777): der Formberater
    schlaegt im eigenen Thread nach und schreibt selbst in den Chat --
    Zusage 2, hier faellt kein Modellaufruf an."""
    from interview_theater import formberater

    formberater.starte(conn, d.tg, d.klm, d.e, d.chat_id,
                       formberater.AUSLOESER_KNOPF)
    return T._ANTWORT_FORMBERATER


def _wirkung_sprechanteile(conn, d: Druck) -> str:
    """Deterministisch aus der Datenbank (``sprecher.anteile``), kein
    Modellaufruf -- Zusage 2 gilt auch fuer diesen Handler."""
    from interview_theater import sprecher

    d.tg.sende(
        d.chat_id,
        sprecher.text(
            sprecher.anteile(
                repo.hole_szenen(conn, d.chat_id), repo.figuren(conn, d.chat_id)
            )
        ),
    )
    return sprecher.T.UEBERSCHRIFT


def _wirkung_fassungen(conn, d: Druck) -> str:
    return _zeige_fassungen(conn, d.tg, d.chat_id, int(d.wert))


# --- Die Wirkungen der Grundleiste, der Fragen und der Figuren -------------


def _wirkung_board_uebernehmen(conn, d: Druck) -> str:
    """"Take these" unter dem Top-5-Vorschlag (Karte t_4517d4ad): derselbe
    Speicherweg wie "Ja, speichern" -- also auch ``begriffe_detail``
    (``_speichere`` -> ``begriffsboard.schreibe_detail``), dieselbe
    Ruecknahme, derselbe Uebergang in Phase 2. Ueberschreibt nie still einen
    schon gesetzten Wert (``nur_bestaetigen``)."""
    return _speichere(
        conn, d.tg, d.chat_id, f"begriffe{TRENNER}{d.wert}",
        nur_bestaetigen=True, uebergang=True, klm=d.klm, e=d.e,
    )


def _wirkung_board_aendern(conn, d: Druck) -> str:
    """"Etwas aendern" unter der Abschlussnachricht des Begriffsboards (Birk
    05.10.2026): EIN Satz, was sich aendern soll -- als Bot-Zeile
    mitgeschrieben, damit der naechste Gespraechszug die Frage im Fenster
    sieht und die Antwort der Gruppe als Korrektur der Liste liest (dort
    speichert der Vorschlagsblock automatisch, und die Frage kommt mit der
    neuen Liste wieder -- ``basis._korrigiere_begriffe``, ohne
    Phasenwechsel). Kein Modellaufruf (Zusage 2), nichts gespeichert."""
    text = T._TEXT_BOARD_WAS_AENDERN
    message_id = d.tg.sende(d.chat_id, text)
    _merke_botnachricht(conn, d.chat_id, message_id, text)
    return text


def _wirkung_speichern(conn, d: Druck) -> str:
    """"Gefaellt uns, weiter". Drei Wege, je nach der Art im ``wert``: die
    Eroeffnung geht in ZWEI Felder, Kernthema/Kernfrage haben ihre eigene
    Kette, alles andere ist der Regelfall.

    Die Fragen selbst laufen seit dem 02.10.2026 nicht mehr hierueber --
    ``fragen`` wird ausschliesslich am Ende der Frage-fuer-Frage-Stufe
    gesetzt (``knoepfe.fragen._schliesse_fragen_ab``); ein "Gefaellt uns,
    weiter" mit ``gespeicherte_art == "fragen"`` kann deshalb nur noch aus
    einer alten, vor dem Umbau verschickten Nachricht kommen und faellt in
    den Regelfall (``_speichere`` kennt die Art weiterhin)."""
    roh = d.wert
    gespeicherte_art = roh.partition(TRENNER)[0].strip()
    if gespeicherte_art == "eroeffnung":
        # Eroeffnung und Abschluss stecken in EINEM Block und gehen in
        # ZWEI Felder -- deshalb ein eigener Speicherweg statt des
        # Arbeitsstand-Setters (wie bei der Geschichte in Phase 5).
        return _speichere_eroeffnung(
            conn, d.tg, d.chat_id, roh.partition(TRENNER)[2], e=d.e, klm=d.klm,
        )
    if gespeicherte_art in _KETTE:
        return _speichere_kettenglied(conn, d, roh, gespeicherte_art)
    # "Gefaellt uns, weiter" ueberschreibt nie still, was schon steht
    # (06.09.2026): ist das Feld gesetzt und keine Aenderung offen, ist
    # der Druck eine Bestaetigung (``_ist_bestaetigung``).
    meldung = _speichere(
        conn, d.tg, d.chat_id, roh, nur_bestaetigen=True,
        uebergang=True, klm=d.klm, e=d.e,
    )
    if gespeicherte_art == "figuren" and meldung not in (
        T._TEXT_UNBEKANNT, T._TEXT_SCHON_GESETZT,
    ):
        # Ebene 1 ist abgenommen -- ab hier geht es Figur fuer Figur
        # weiter (Ebene 2), ohne dass jemand etwas antippen muss.
        stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    return meldung


def _speichere_kettenglied(conn, d: Druck, roh: str, gespeicherte_art: str) -> str:
    """Kernthema und Kernfrage tragen den Weg selbst weiter (Stufe 2 ->
    Stufe 3 -> Filter -> Figurenanzahl). Die allgemeine Weiterfrage ("Wollt ihr
    noch etwas hinzufuegen?") wuerde sich dazwischen stellen, deshalb
    ``weiterfrage=False``."""
    meldung = _speichere(
        conn, d.tg, d.chat_id, roh, weiterfrage=False, nur_bestaetigen=True,
    )
    if meldung not in (T._TEXT_UNBEKANNT, T._TEXT_SCHON_GESETZT):
        repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", None)
        _kette_weiter(conn, d.tg, d.klm, d.e, d.chat_id, gespeicherte_art)
    return meldung


def _wirkung_anders(conn, d: Druck) -> str:
    """"Nein, nochmal aendern" SPEICHERT VORLAEUFIG (02.10.2026, Birk, Padua;
    die Idee stammt von "Passt, aber anders", 05.09.2026): damit ueberhaupt
    etwas in der Datenbank steht, auch wenn die Gruppe danach abbricht. Dann
    die gezielte Frage -- deterministisch, kein Modellaufruf (Zusage 2).

    ``aenderung_offen`` haelt die Leiste fuer die naechste Fassung offen
    (``offene_art``), ein spaeteres Ja ueberschreibt den vorlaeufigen Wert.
    Stand schon ein Angebot fuer die naechste Phase, ist es damit abgelehnt
    (``phasen.lehne_angebot_ab`` -- es kommt nach der naechsten Aenderung
    wieder). Arten ohne Arbeitsstand-Feld (Eroeffnung) speichern nichts und
    sagen das auch nicht."""
    roh = d.wert
    gespeicherte_art = roh.partition(TRENNER)[0].strip()
    if gespeicherte_art in T._NOTIERT:
        _speichere(conn, d.tg, d.chat_id, roh, weiterfrage=False)
        text = T._TEXT_ANDERS
    else:
        text = T._TEXT_EIGENE
    repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", gespeicherte_art)
    gemerkt = repo.hole_phase_angeboten(conn, d.chat_id)
    if gemerkt is not None and gemerkt > 0:
        phasen.lehne_angebot_ab(conn, d.chat_id, gemerkt)
    # Das "Ja" daneben verfaellt: es traegt den alten Wert, und eine offene
    # Speicher-Leiste haelt sonst das Phasenangebot zurueck.
    mid = d.knopf["message_id"] if "message_id" in d.knopf.keys() else None
    if mid is not None:
        geschwister = [
            k["id"] for k in repo.offene_knoepfe_der_nachricht(conn, d.chat_id, mid)
            if k["art"] != ART_UNDO
        ]
        if geschwister:
            repo.verfallen_lassen(conn, geschwister)
    d.tg.sende(d.chat_id, text)
    return T._TEXT_GESPEICHERT_WAS_ANDERS_QUITTUNG


def _wirkung_eigene(conn, d: Druck) -> str:
    """Speichert NICHT. Der naechste Gruppenbeitrag ist der Vorschlag, und die
    Antwort darauf traegt die Leiste erneut."""
    repo.setze_arbeitsstand(conn, d.chat_id, "aenderung_offen", d.wert)
    d.tg.sende(d.chat_id, T._TEXT_EIGENE)
    return T._ANTWORT_ERZAEHLT


def _wirkung_frage_wahl(conn, d: Druck) -> str:
    """**Stillgelegt** (06.09.2026, 10:05, Birk): die Toggle-Auswahl
    funktionierte am Telefon nicht. Angeboten werden diese Knoepfe nicht mehr
    (``_fragenleiste``); ein Druck aus einer alten Nachricht laeuft hier ins
    Leere und bekommt den Weg gesagt, statt still nichts zu tun."""
    d.tg.sende(d.chat_id, T._TEXT_FRAGEN_WAHL)
    return T._TEXT_FRAGEN_WAHL


def _wirkung_fragen_andere(conn, d: Druck) -> str:
    """"Andere Richtung" unter dem Fragenueberblick (02.10.2026): fragt
    deterministisch nach der Richtung, statt sofort neu vorzuschlagen -- die
    naechste freie Nachricht loest den Auftrag aus
    (``fragen.nimm_offene_frage_text``, aufgerufen aus ``ablauf.py``)."""
    frage_warten_auf_richtung(conn, d.tg, d.chat_id)
    return T._TEXT_FRAGEN_RICHTUNG_GEFRAGT


def _wirkung_fragen_eigene(conn, d: Druck) -> str:
    """**Stillgelegt seit 02.10.2026** (die alte Fragenauswahl ist durch den
    Ueberblick mit Richtungsfrage ersetzt): ein Druck aus einer alten
    Nachricht bekommt eine Antwort statt still zu verpuffen, speichert aber
    nichts mehr."""
    d.tg.sende(d.chat_id, T._TEXT_FRAGEN_EIGENE)
    return T._ANTWORT_ERZAEHLT


def _wirkung_fragen_vorschlagen(conn, d: Druck) -> str:
    """"Suggest questions" (Padua Phase 2, Birk 05.10.2026): erst die
    Rueckfrage zum Selberdenken, kein KI-Vorschlag."""
    frage_nach_eigenen(conn, d.tg, d.chat_id)
    return T._TEXT_FRAGE_ENTSCHIEDEN


def _wirkung_fragen_noch_eigene(conn, d: Druck) -> str:
    """"We have more": einladen, nichts erzeugen."""
    noch_eigene(conn, d.tg, d.chat_id)
    return T._TEXT_FRAGE_ENTSCHIEDEN


def _wirkung_fragen_ja_vorschlagen(conn, d: Druck) -> str:
    """"Yes, suggest some": die Gegenueberstellung mit den KI-Fragen, die
    beim Eintritt in Phase 2 im Hintergrund entstanden sind. ``klm``/``e``
    reichen durch, damit ein gescheiterter Lauf im Hintergrund nachgeholt
    wird (Feedbackloop P1-2, R-3) -- der Modellaufruf selbst laeuft im
    Thread von ``fragen_ki.starte``, nie hier."""
    ja_vorschlagen(conn, d.tg, d.chat_id, klm=d.klm, e=d.e)
    return T._TEXT_FRAGE_ENTSCHIEDEN


def _wirkung_fragen_einzeln(conn, d: Druck) -> str:
    """"Ja, einzeln durchgehen" -- zeigt die erste Frage."""
    starte_durchgehen(conn, d.tg, d.chat_id)
    return T._TEXT_FRAGE_ENTSCHIEDEN


def _wirkung_frage_annehmen(conn, d: Druck) -> str:
    return entscheide(conn, d.tg, d.klm, d.e, d.chat_id, int(d.wert), "ja")


def _wirkung_frage_verwerfen(conn, d: Druck) -> str:
    return entscheide(conn, d.tg, d.klm, d.e, d.chat_id, int(d.wert), "nein")


def _wirkung_frage_schaerfen(conn, d: Druck) -> str:
    return frage_waehlt_schaerfen(conn, d.tg, d.chat_id, int(d.wert))


def _wirkung_fragen_weich_uebernehmen(conn, d: Druck) -> str:
    return frage_weich_uebernehmen(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_fragen_weich_lassen(conn, d: Druck) -> str:
    return frage_weich_lassen(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_fragen_umformulieren_alle(conn, d: Druck) -> str:
    fragen_umformulierung_alle_annehmen(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._TEXT_UMFORMULIEREN_ALLE_KNOPF


def _wirkung_fragen_umformulieren_keine(conn, d: Druck) -> str:
    fragen_umformulierung_alle_verwerfen(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._TEXT_UMFORMULIEREN_KEINE_KNOPF


def _wirkung_fragen_umformulieren_anbieten(conn, d: Druck) -> str:
    """Der Knopf "Fragen umformulieren" nach "Fragen uebernommen"
    (Review-Fix t_b371c0f1): loest denselben versteckten Befehl aus wie
    ``/umformulieren`` -- kein Modellaufruf hier, nur die Rueckfrage."""
    frage_nach_umformulierung(conn, d.tg, d.chat_id)
    return T._TEXT_FRAGE_ENTSCHIEDEN


def _wirkung_leitfaden(conn, d: Druck) -> str:
    from interview_theater import leitfaden

    leitfaden.sende(conn, d.tg, d.chat_id, e=d.e)
    return T._ANTWORT_LEITFADEN


def _wirkung_richtung(conn, d: Druck) -> str:
    """Stufe 1 der zweistufigen Kernthema-Wahl: die Richtung wird festgehalten,
    ``kernthema`` bleibt LEER -- eine Richtung ist kein Kernthema, und ein halb
    gefuelltes Feld waere schlimmer als ein leeres. Der zweite Schritt ist ein
    Gespraechszug im Thread."""
    richtung = d.wert.strip()
    repo.setze_arbeitsstand(conn, d.chat_id, "kernthema_richtung", richtung)
    repo.schreibe_journal(
        conn, d.chat_id, "vorgeschlagen",
        T._JOURNAL_RICHTUNG.format(richtung=richtung), quelle="knopf",
    )
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        T.ANWEISUNG_KERNTHEMA.format(richtung=richtung),
    )
    return T._TEXT_RICHTUNG_QUITTUNG


def _wirkung_figuren_anzahl_menu(conn, d: Druck) -> str:
    """"Anzahl aendern" im Listen-Menue und die Erstfrage sind derselbe Weg und
    schreiben dasselbe Feld -- nur der Fragetext ist ein anderer, weil hier
    schon eine Liste dasteht."""
    biete_figurenanzahl(conn, d.tg, d.chat_id, T._TEXT_FIGUREN_ANZAHL_FRAGE)
    return T._ANTWORT_WIE_VIELE


def _wirkung_figuren_anzahl(conn, d: Druck) -> str:
    anzahl = _zahl_aus(d.wert.strip())
    if anzahl is None:
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    uebernimm_figurenanzahl(conn, d.tg, d.klm, d.e, d.chat_id, anzahl)
    return T._ANTWORT_FIGUREN_ANZAHL.format(anzahl=d.knopf["wert"])


def _wirkung_figuren_anzahl_frei(conn, d: Druck) -> str:
    """Kein Modellaufruf, kein Wert: nur der Merkposten, dass die naechste
    Nachricht der Gruppe die Zahl ist (``ablauf.antworte`` liest ihn)."""
    erwarte_figurenanzahl(d.chat_id)
    d.tg.sende(d.chat_id, T._TEXT_FIGUREN_ANZAHL_FREI_FRAGE)
    return T._ANTWORT_ZAHL


def _wirkung_figuren_namen_menu(conn, d: Druck) -> str:
    zeilen = _entwurfszeilen(conn, d.chat_id)
    if not zeilen:
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    leiste = []
    for nr, zeile in enumerate(zeilen, start=1):
        name = zeile.split("—")[0].split(" - ")[0].strip()
        leiste.append(
            (
                T._TEXT_FIGUR_NR_KNOPF.format(nr=nr, name=name),
                _daten(repo.lege_knopf_an(
                    conn, d.chat_id, ART_FIGUR_NAME_MENU, str(nr - 1)
                )),
            )
        )
    message_id = _sende_knoepfe(
        conn, d.tg, d.chat_id, T._TEXT_FIGUREN_NAMEN_FRAGE, leiste
    )
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return T._ANTWORT_WELCHER_NAME


def _wirkung_figur_name_menu(conn, d: Druck) -> str:
    zeilen = _entwurfszeilen(conn, d.chat_id)
    index = int(d.knopf["wert"])
    if index >= len(zeilen):
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    # Der Index wandert in den Merkposten, damit der Namensdruck weiss,
    # WELCHE Zeile er ersetzt -- der Knopf traegt nur den Namen.
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", str(index))
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        T.ANWEISUNG_NAMEN.format(zeile=zeilen[index]),
    )
    return T._ANTWORT_NAMEN_VORSCHLAGEN


def _wirkung_figur_name(conn, d: Druck) -> str:
    return _ersetze_namen(conn, d.tg, d.chat_id, d.wert.strip())


def _wirkung_figur_passt(conn, d: Druck) -> str:
    figur = repo.hole_figur(conn, d.chat_id, d.wert)
    if figur is not None:
        repo.setze_figur_geprueft(conn, figur["id"], repo._jetzt())
    stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_PASST


def _wirkung_figur_interview_menu(conn, d: Druck) -> str:
    return _biete_interviews(conn, d.tg, d.chat_id, d.wert)


def _wirkung_figur_interview(conn, d: Druck) -> str:
    name, _, roh_id = d.wert.partition(TRENNER)
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None or not roh_id.isdigit():
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    repo.setze_figur_quelle(conn, figur["id"], int(roh_id))
    # Das alte Sprachprofil gehoert zum alten Interview -- es wird neu
    # erzeugt (im Thread), und die Figur ist wieder offen.
    repo.setze_sprachprofil(conn, figur["id"], "", [])
    repo.setze_figur_geprueft(conn, figur["id"], None)
    stelle_figur_vor(
        conn, d.tg, d.klm, d.e, d.chat_id, repo.hole_figur(conn, d.chat_id, name)
    )
    return T._ANTWORT_INTERVIEW_GEWECHSELT


def _wirkung_figur_duktus_menu(conn, d: Druck) -> str:
    name = d.wert
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", name)
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id, T.ANWEISUNG_DUKTUS.format(name=name)
    )
    return T._ANTWORT_DUKTUS_VORSCHLAEGE


def _wirkung_figur_duktus(conn, d: Druck) -> str:
    stand = repo.hole_arbeitsstand(conn, d.chat_id)
    name = (stand["figur_aktuell"] if stand else "") or ""
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None:
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    # Die Zitate bleiben stehen: sie sind belegt (``zitat.pruefe``) und
    # haengen am Interview, nicht an der Beschreibung.
    zitate = [z for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER) if z]
    repo.setze_sprachprofil(conn, figur["id"], d.wert.strip(), zitate)
    repo.setze_figur_geprueft(conn, figur["id"], None)
    stelle_figur_vor(
        conn, d.tg, d.klm, d.e, d.chat_id, repo.hole_figur(conn, d.chat_id, name)
    )
    return T._ANTWORT_DUKTUS_UEBERNOMMEN


def _wirkung_figur_stil(conn, d: Druck) -> str:
    """Der gewaehlte Sprachstil (06.09.2026, Birk 12:20): er schreibt
    ``figur.sprachstil`` und -- wenn der Stil aus einem Interview kommt --
    zusaetzlich ``quelle_aufnahme_id``. Additiv: das Sprachprofil aus einem
    frueheren Lauf bleibt stehen."""
    name, _, rest = d.wert.partition(TRENNER)
    roh_id, _, stil = rest.partition(TRENNER)
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None or not stil.strip():
        d.tg.sende(d.chat_id, T._TEXT_UNBEKANNT)
        return T._TEXT_UNBEKANNT
    repo.setze_figur_sprachstil(conn, figur["id"], stil.strip())
    if roh_id.strip().isdigit():
        repo.setze_figur_quelle(conn, figur["id"], int(roh_id))
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_SPRACHSTIL.format(name=name, stil=stil.strip()),
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, T._TEXT_STIL_GESPEICHERT.format(name=name))
    # Sofort weiter: naechste Figur, sonst die Geschichte.
    if not stelle_stil_vor(conn, d.tg, d.klm, d.e, d.chat_id):
        _schliesse_figuren_ab(conn, d.tg, d.chat_id)
    return T._ANTWORT_STIL_UEBERNOMMEN


def _wirkung_figuren_zufall(conn, d: Druck) -> str:
    """Ein Druck statt zwoelf Modellaufrufen (06.09.2026, Analyse Abschnitt 1).
    Reine DB-Operation, keine Sprachstile, bestehende Zuordnungen bleiben
    unangetastet."""
    if not _interviewkoepfe(conn, d.chat_id):
        d.tg.sende(d.chat_id, T._TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW)
        return T._TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW
    anzahl, interviews = ordne_figuren_zufaellig_zu(conn, d.chat_id)
    if not anzahl:
        d.tg.sende(d.chat_id, T._TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN)
        return T._TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN
    meldung = T._TEXT_FIGUREN_ZUFALL_FERTIG.format(
        figuren=anzahl, interviews=interviews
    )
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_ZUFALL_ZUGEORDNET.format(
            figuren=anzahl, interviews=interviews
        ),
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, meldung)
    return T._ANTWORT_ZUGEORDNET.format(anzahl=anzahl)


def _wirkung_figur_stil_frei(conn, d: Druck) -> str:
    """Speichert nichts (Knopfregel: nur was fix ist). Der naechste Beitrag der
    Gruppe ist der Stil, und der Erkenner traegt ihn ein."""
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", d.wert)
    d.tg.sende(d.chat_id, T._TEXT_STIL_EIGENER)
    return T._ANTWORT_ERZAEHLT


def _wirkung_figur_entfernen(conn, d: Druck) -> str:
    name = repo.entferne_figur(conn, d.chat_id, d.wert)
    if name:
        repo.schreibe_journal(
            conn, d.chat_id, "entschieden",
            T._JOURNAL_FIGUR_ENTFERNT.format(name=name),
            quelle="knopf",
        )
        d.tg.sende(d.chat_id, T._TEXT_FIGUR_RAUS.format(name=name))
    stelle_figur_vor(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_ENTFERNT


def _wirkung_rahmen(conn, d: Druck) -> str:
    return _speichere(
        conn, d.tg, d.chat_id, f"rahmen{TRENNER}{d.knopf['wert']}"
    )


def _wirkung_wir_zuerst(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, T._TEXT_WIR_ZUERST)
    return T._ANTWORT_WIR_HOEREN_ZU


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
        return T._ANTWORT_ICH_SCHLAGE_VOR
    if phase == PHASE_SZENEN:
        # Die Szenentexte-Phase hat einen eigenen Weg
        # (``szenenfolge.starte``): der Vorschlag ist eine Szenenfolge
        # mit fester Zeilenform, kein freier Gespraechszug -- und er
        # traegt danach seine eigenen Knoepfe ("Anzahl aendern",
        # "Reihenfolge aendern"). Auch er laeuft in einem eigenen
        # Thread, kein Modellaufruf hier.
        from interview_theater import szenenfolge

        szenenfolge.starte(conn, d.tg, d.klm, d.e, d.chat_id)
        return T._ANTWORT_ICH_SCHLAGE_VOR
    _starte_auftrag(
        conn, d.tg, d.klm, d.e, d.chat_id,
        T.ANWEISUNGEN.get(phase, T._ANWEISUNG_ALLGEMEIN),
    )
    return T._ANTWORT_ICH_SCHLAGE_VOR


def _wirkung_auswerten_alle(conn, d: Druck) -> str:
    return _werte_alle_aus(conn, d.tg, d.klm, d.e, d.chat_id)


def _wirkung_teil_weiter(conn, d: Druck) -> str:
    """Kein Modellaufruf (Zusage 2), keine Schreibwirkung: die Aufnahme laeuft
    ohnehin weiter. Der Knopf ist die Antwort auf eine Frage, die sonst offen
    im Chat stuende -- und die Tastatur ist danach weg (``behandle`` nimmt sie
    ab), was fuer sich schon die Rueckmeldung ist."""
    d.tg.sende(d.chat_id, T._TEXT_TEIL_WEITER)
    return T._ANTWORT_HOERE_WEITER_ZU


def _wirkung_teil_fertig(conn, d: Druck) -> str:
    """Wortgleich dasselbe wie "Interview beenden": derselbe Umschalter,
    dieselbe Verdichtung, dieselbe Nach-Interview-Leiste. Kein zweiter Weg fuer
    dieselbe Sache -- deshalb der Umweg ueber /aufnahme statt einer eigenen
    Abfolge hier."""
    from interview_theater import befehle

    if not repo.ist_interviewmodus_an(conn, d.chat_id):
        d.tg.sende(d.chat_id, T._TEXT_TEIL_SCHON_AUS)
        return T._TEXT_TEIL_SCHON_AUS
    befehle._befehl_aufnahme(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_INTERVIEW_BEENDET


def _wirkung_interviews_fertig(conn, d: Druck) -> str:
    """Der eine Web-Knopf nach einem Interview (Phase 3 Web-UX, 02.10.2026):
    springt direkt nach Phase 4, wenn die Materiallage es hergibt, oder
    merkt den Wunsch fuer den Auto-Uebergang nach der letzten Verdichtung
    (``aufnahme._interview_abschliessen``). Kein Modellaufruf hier (Zusage
    2): ``schliesse_interviews_ab`` ruft ``eintritt_in_phase`` direkt, wie
    ``_wirkung_phase`` es seit laengerem tut -- was die Phase 4 dabei braucht,
    ist deterministisch (``phasentexte.eintritt`` + ``biete_proaktiv``)."""
    from interview_theater import aufnahme
    from interview_theater.knoepfe.stationen import schliesse_interviews_ab

    # P34 Final-Review (A12): ein stehengebliebener Knopf, gedrueckt erst
    # ausserhalb von Phase 3, tut nichts -- kein Wunsch (eine spaetere
    # Verdichtung schaltete sonst still um), kein Abschluss (der koennte
    # 4 -> 5 springen). Die Phase setzt allein die Gruppe; die Quittung nennt
    # die aktuelle Phase.
    aktuell = phasen.aktuelle(conn, d.chat_id)
    if aktuell != 3:
        return T._ANTWORT_PHASE.format(nummer=aktuell)
    if aufnahme.unausgewertete_interviews(conn, d.chat_id):
        repo.setze_arbeitsstand(
            conn, d.chat_id, "interviews_fertig_wunsch_seit", repo._jetzt(),
        )
        offen = len(aufnahme.unausgewertete_interviews(conn, d.chat_id))
        # Keine Dopplung (Praezedenz Commit 7f0782e, "Knopf-Quittung steht
        # unter der Nachricht, an der gedrueckt wurde"): der Rueckgabewert
        # IST die Quittung, ``behandle`` schickt sie via answerCallbackQuery
        # -- ein zusaetzliches d.tg.sende() hier waere derselbe Text zweimal.
        return T._TEXT_INTERVIEWS_NOCH_OFFEN.format(anzahl=offen)
    if schliesse_interviews_ab(conn, d.tg, d.klm, d.e, d.chat_id):
        # Der Tab-Hinweis steht schon als Chatzeile da
        # (``schliesse_interviews_ab``); als Quittung kaeme er ein zweites
        # Mal (P34 Runde 2, Befund A9). Die Quittung nennt die Phase wie
        # ``_wirkung_phase``.
        return T._ANTWORT_PHASE.format(nummer=phasen.aktuelle(conn, d.chat_id))
    # Sollte wegen phasen.voraussetzungen[4] nicht vorkommen, wenn
    # unausgewertete_interviews() oben schon leer war -- defensiv trotzdem
    # wie "noch offen" behandeln statt zu schweigen. Dieselbe Keine-Dopplung-
    # Regel wie oben gilt auch hier.
    repo.setze_arbeitsstand(conn, d.chat_id, "interviews_fertig_wunsch_seit", repo._jetzt())
    return T._TEXT_INTERVIEWS_NOCH_OFFEN.format(anzahl=0)


# --- Die vier Knoepfe rund um die lange Sprachnachricht --------------------
#
# 06.09.2026, Live-Fall Gruppe 1 13:32: eine lange Sprachnachricht ausserhalb
# des Interviewmodus. **Kein Modellaufruf in diesen Handlern** (Zusage 2):
# "Ja" schreibt nur in die Datenbank, "Fertig" gibt die Verdichtung an
# ``starte_abschluss`` (eigener Thread), "Nein" gibt den nachgeholten
# Gespraechszug an ``aufnahme.starte_nachgeholten_zug`` (eigener Thread).


def _ohne_knopf_kennung(d: Druck) -> int | None:
    """Die Aufnahme-id aus dem Knopfwert -- None, wenn sie fehlt oder krumm
    ist. Ohne sie ist keiner der vier Knoepfe zu bedienen."""
    try:
        return int(str(d.knopf["wert"]))
    except (TypeError, ValueError):
        log.error(
            "Knopf %s ohne brauchbaren wert %r, chat_id=%s",
            d.knopf["art"], d.knopf["wert"], d.chat_id,
        )
        return None


def _wirkung_ohne_knopf_ja(conn, d: Druck) -> str:
    """"Ja, das war ein Interview": die Aufnahme wird nachtraeglich zu einem
    Interviewkopf, und die Gruppe bekommt die Weiter-Frage."""
    from interview_theater import aufnahme

    kennung = _ohne_knopf_kennung(d)
    if kennung is None:
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    if repo.hole_aufnahme(conn, kennung) is None:
        d.tg.sende(d.chat_id, T._TEXT_OHNE_KNOPF_UNBEKANNT)
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    kopf_id = aufnahme.nimm_als_interview(conn, d.tg, d.chat_id, kennung)
    kopf = repo.hole_aufnahme(conn, kopf_id) if kopf_id else None
    name = (aufnahme.anzeigename(conn, kopf, T._TEXT_DAS_INTERVIEW_ANFANG)
            if kopf else T._TEXT_DAS_INTERVIEW_ANFANG)
    biete_interview_ohne_knopf_weiter(
        conn, d.tg, d.chat_id,
        T._TEXT_INTERVIEW_STEHT.format(
            name=name, weiter=aufnahme.T._TEXT_INTERVIEW_OHNE_KNOPF_WEITER
        ),
        kopf_id,
    )
    return T._ANTWORT_ANGELEGT.format(name=name)


def _wirkung_ohne_knopf_nein(conn, d: Druck) -> str:
    """"Nein, das war ein Beitrag": der nachgeholte Gespraechszug laeuft in
    einem eigenen Thread."""
    from interview_theater import aufnahme

    kennung = _ohne_knopf_kennung(d)
    if kennung is None:
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    if not aufnahme.nimm_als_beitrag(conn, d.tg, d.klm, d.e, d.chat_id, kennung):
        d.tg.sende(d.chat_id, T._TEXT_OHNE_KNOPF_UNBEKANNT)
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    d.tg.sende(d.chat_id, aufnahme.T._TEXT_INTERVIEW_OHNE_KNOPF_NEIN)
    return T._ANTWORT_ALS_BEITRAG


def _wirkung_ohne_knopf_weiter(conn, d: Druck) -> str:
    """Nichts zu tun: der Modus ist an, der Kopf offen. Die Tastatur ist nach
    ``behandle`` weg, das ist die Rueckmeldung."""
    if _ohne_knopf_kennung(d) is None:
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    d.tg.sende(d.chat_id, T._TEXT_OHNE_KNOPF_WEITER)
    return T._ANTWORT_HOERE_WEITER_ZU


def _wirkung_ohne_knopf_fertig(conn, d: Druck) -> str:
    """Wortgleich derselbe Weg wie "Interview beenden": beenden, dann
    verdichten im eigenen Thread."""
    from interview_theater import aufnahme

    kennung = _ohne_knopf_kennung(d)
    if kennung is None:
        return T._TEXT_OHNE_KNOPF_UNBEKANNT
    kopf_id = aufnahme.beende_interview(conn, d.chat_id)
    if kopf_id is None:
        kopf_id = kennung
    if d.klm is not None:
        aufnahme.starte_abschluss(conn, d.tg, d.klm, d.e, kopf_id)
    return T._ANTWORT_INTERVIEW_BEENDET


# --- Kernthema, Aufnahme, Phase, Auswertung, Szenenform --------------------


def _wirkung_kernthema(conn, d: Druck) -> str:
    """Der eigentliche Punkt der Uebung: deterministisch schreiben, was der
    Erkenner live nicht zuverlaessig traf."""
    repo.setze_arbeitsstand(conn, d.chat_id, "kernthema", d.knopf["wert"])
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_KERNTHEMA.format(kernthema=d.knopf["wert"]),
        quelle="knopf",
    )
    d.tg.sende(
        d.chat_id, T._TEXT_KERNTHEMA_NOTIERT.format(kernthema=d.knopf["wert"])
    )
    return T._ANTWORT_KERNTHEMA


def _wirkung_aufnahme(conn, d: Druck) -> str:
    """Wortgleich dasselbe wie /aufnahme -- inklusive der Verdichtung im
    eigenen Thread. Kein zweiter Weg fuer dieselbe Sache.

    Import erst hier: ``befehle`` bietet Knoepfe an (biete_kernthema) und
    ``knoepfe`` ruft einen Befehl auf -- ein Modulimport oben waere ein Zyklus.
    Der Aufruf ist selten (ein Knopfdruck), der Import danach im
    sys.modules-Cache."""
    from interview_theater import befehle

    befehle._befehl_aufnahme(conn, d.tg, d.klm, d.e, d.chat_id)
    return T._ANTWORT_AUFNAHME_UMGESCHALTET


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
    d.tg.sende(d.chat_id, T._TEXT_NOCH_NICHT)
    return T._TEXT_NOCH_NICHT


def _wirkung_phase(conn, d: Druck) -> str:
    nummer = int(d.knopf["wert"])
    # Abnahme P3-4 A3 Nachtrag (06.10.2026): derselbe Waechter wie in
    # ``befehle.wechsle_phase`` -- die Phasenleiste im Browser geht genau
    # hier entlang (``/phaseklick``), nicht durch ``wechsle_phase``. Import
    # erst hier: ein Modulimport oben waere ein Zyklus (derselbe Grund wie
    # in ``_wirkung_aufnahme``).
    from interview_theater import befehle

    befehle.schliesse_offenes_interview_vor_phasenwechsel(
        conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    if phasen.setze(conn, d.chat_id, nummer, "knopf"):
        d.tg.sende(d.chat_id, phasen.meldung(nummer))
    # Ein Weg fuer alle acht Phasen (06.09.2026): Eintrittsnachricht mit
    # Kopfzeile, Einleitung und Checkliste, darunter die Einstiegsknoepfe
    # dieser Phase.
    eintritt_in_phase(conn, d.tg, d.klm, d.e, d.chat_id, nummer)
    return T._ANTWORT_PHASE.format(nummer=nummer)


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
        d.tg.sende(d.chat_id, T._TEXT_AUSWERTEN_UNBEKANNT)
        return T._TEXT_AUSWERTEN_UNBEKANNT
    name = aufnahme.anzeigename(conn, kopf, T._TEXT_DAS_INTERVIEW_ANFANG)
    if aufnahme.zeige_verdichtung(conn, d.tg, d.e, kopf_id):
        return T._ANTWORT_AUSWERTUNG
    if d.klm is None:
        log.error("Auswerten-Knopf ohne Sprachmodell, chat_id=%s", d.chat_id)
        d.tg.sende(d.chat_id, T._TEXT_AUSWERTEN_UNMOEGLICH)
        return T._TEXT_AUSWERTEN_UNMOEGLICH
    d.tg.sende(d.chat_id, T._TEXT_ICH_WERTE_AUS.format(name=name))
    aufnahme.starte_auswertung(conn, d.tg, d.klm, d.e, kopf_id)
    return T._ANTWORT_AUSWERTUNG_LAEUFT


def _wirkung_zusammenfassung(conn, d: Druck) -> str:
    """Derselbe Anzeigepfad wie bisher hinter "Auswerten"
    (``aufnahme.zeige_verdichtung``), nur ehrlicher benannt: verdichtet ist
    laengst, gezeigt wird jetzt. Reine Leseabfrage, kein Modellaufruf
    (Zusage 2)."""
    from interview_theater import aufnahme

    kopf_id = int(d.knopf["wert"])
    if aufnahme.zeige_verdichtung(conn, d.tg, d.e, kopf_id):
        return T._ANTWORT_ZUSAMMENFASSUNG
    d.tg.sende(d.chat_id, T._TEXT_AUSWERTEN_UNBEKANNT)
    return T._TEXT_AUSWERTEN_UNBEKANNT


def _wirkung_transkript(conn, d: Druck) -> str:
    """Der Wortlaut zum Gegenpruefen -- derselbe Text, den ``/wortlaut``
    ausspielt, in Teilen, wenn er laenger ist als ``telegram.NACHRICHT_GRENZE``.
    Deterministisch aus der Datenbank."""
    from interview_theater import telegram as telegram_modul

    kopf = repo.hole_aufnahme(conn, int(d.knopf["wert"]))
    text = (kopf["transkript"] or "").strip() if kopf is not None else ""
    if not text:
        d.tg.sende(d.chat_id, T._TEXT_KEIN_TRANSKRIPT)
        return T._TEXT_KEIN_TRANSKRIPT
    from interview_theater import aufnahme

    name = aufnahme.anzeigename(conn, kopf, T._TEXT_DAS_INTERVIEW_ANFANG)
    for stueck in telegram_modul.teile_text(
        T._TEXT_IM_WORTLAUT.format(name=name, text=text)
    ):
        d.tg.sende(d.chat_id, stueck)
    return T._ANTWORT_TRANSKRIPT


def _wirkung_stand(conn, d: Druck) -> str:
    from interview_theater import befehle

    befehle._befehl_stand(conn, d.tg, d.chat_id, d.e)
    return T._ANTWORT_STAND


def _wirkung_hilfe(conn, d: Druck) -> str:
    from interview_theater import befehle

    befehle._befehl_hilfe(conn, d.tg, d.e, d.chat_id)
    return T._ANTWORT_HILFE


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
    # Jetzt, wo die Form bestaetigt ist, kommt die STILFRAGE (06.09.2026,
    # Birk 12:50) -- und erst danach die Schreibfrage. Beides zusammen
    # entscheidet, wie der Text klingt; die Reihenfolge ist Form, Stil,
    # schreiben.
    biete_szenenstil(conn, d.tg, d.chat_id, nummer)
    return T._TEXT_SZENE_EINTRAG.format(nummer=nummer, was=form)


def _wirkung_szenenstil(conn, d: Druck) -> str:
    """Wert wie bei der Form: "3:litanei". ``ohne`` ist die ausdrueckliche
    Abwahl und wird als NULL gespeichert -- ein Slug "ohne" in der Datenbank
    waere ein Stil, den es nicht gibt."""
    from interview_theater import stile

    roh_nummer, _, slug = str(d.knopf["wert"]).partition(":")
    nummer = int(roh_nummer)
    szene_id = repo.stelle_szene_sicher(conn, d.chat_id, nummer)
    gewaehlt = slug if stile.hole(slug) is not None else None
    repo.setze_szenenfeld(conn, szene_id, "stil", gewaehlt)
    if gewaehlt:
        d.tg.sende(
            d.chat_id,
            T._TEXT_SZENE_STIL_GESETZT.format(
                nummer=nummer, stil=stile.beschriftung(gewaehlt),
                herkunft=stile.herkunft(gewaehlt),
            ),
        )
    else:
        d.tg.sende(
            d.chat_id, T._TEXT_SZENE_OHNE_STIL.format(nummer=nummer)
        )
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_SZENE_STIL.format(
            nummer=nummer,
            stil=stile.beschriftung(gewaehlt) if gewaehlt else T._TEXT_STIL_OHNE_WORT,
        ),
        quelle="knopf",
    )
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is not None:
        biete_szene(conn, d.tg, d.chat_id, ziel)
    return T._ANTWORT_SZENE_STIL.format(
        nummer=nummer, stil=gewaehlt or T._TEXT_STIL_OHNE_WORT
    )


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
        T._JOURNAL_USA_JA if ja else T._JOURNAL_USA_NEIN,
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, T._TEXT_USA_JA if ja else T._TEXT_USA_NEIN)
    # Der Auftrag, der auf diese Antwort gewartet hat, laeuft jetzt --
    # ueber den Weg, den die Antwort festgelegt hat. Bisher tat das nur
    # der Erkenner-Pfad (gesprochenes "ja"); der Knopf setzte den Stand
    # und liess den Auftrag liegen (Live-Fall Testgruppe 05.09. 22:09:
    # "USA" gedrueckt, nichts passierte, ein spaeteres "ja" im Chat war
    # wirkungslos, weil der Stand nicht mehr "offen" war).
    #
    # ERST die Phase, DANN der Auftrag (06.09.2026, Analyse
    # docs/analyse-phase5-chaos-2026-09-06.md Abschnitt 3). Bis dahin
    # stand der Auftrag zuerst -- und weil in Phase 6 immer ein gemerkter
    # Einzelszenen-Auftrag ("Schreib Szene 1.") herumlag, war der
    # Kurzgeschichte-Zweig darunter toter Code. Gemessener Live-Fall
    # Gruppe 1, 13:55:26: USA "ja" -> Einzelszene statt der durchgehenden
    # Geschichte. In Phase 6 gilt: der gemerkte Einzelauftrag wird
    # verworfen (er gehoert zum Phase-5-Weg), und die Gruppe bekommt den
    # Knopf, aus dem der Prosa-Lauf startet.
    auftrag = repo.hole_und_loesche_offenen_szenenauftrag(conn, d.chat_id)
    if phasen.aktuelle(conn, d.chat_id) == PHASE_SZENEN:
        # Gestartet wird von der Gruppe, nicht von dieser Antwort.
        from interview_theater import ueberarbeitung

        if ueberarbeitung.aktiv():
            # Padua (Phase 6, Rewrite): die vorhandene Prosa wird geprueft,
            # nicht neu geschrieben -- im Thread (Zusage 2).
            ueberarbeitung.weiter_6(conn, d.tg, d.klm, d.e, d.chat_id,
                                    aus_eintritt=True)
        else:
            biete_kurzgeschichte(conn, d.tg, d.chat_id, T._TEXT_KURZGESCHICHTE_BEREIT)
    elif auftrag:
        from interview_theater import szene

        szene.starte(conn, d.tg, d.klm, d.e, d.chat_id, auftrag)
    return T._ANTWORT_USA_JA if ja else T._ANTWORT_USA_NEIN


def _wirkung_stt_sprache(conn, d: Druck) -> str:
    """Die Interviewsprache fuer Whisper (Karte A1, D2). Kein Modellaufruf:
    nur ein Feld in ``gruppe`` und eine Journalzeile."""
    wert = d.wert.strip().lower()
    if wert not in {w for w, _ in STT_KNOEPFE}:
        return T._TEXT_UNBEKANNT
    repo.setze_stt_sprache(conn, d.chat_id, wert)
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_STT_SPRACHE.format(sprache=wert), quelle="knopf")
    anzeige = (T._TEXT_STT_SPRACHE_AUTO if wert == sprache.AUTO
               else sprache.SPRACHNAMEN.get(wert, wert))
    d.tg.sende(d.chat_id, T._TEXT_STT_SPRACHE_GESETZT.format(sprache=anzeige))
    return T._TEXT_STT_SPRACHE_KURZ


def _wirkung_undo(conn, d: Druck) -> str:
    """Nimmt einen ganzen Erkennerlauf zurueck (Karte U, 01.10.2026).

    Eine Meldung, eine Ruecknahme -- keine Einzelauswahl. **Kein
    Modellaufruf** (Zusage 2): die Schritte liegen seit dem Lauf in
    ``erkenner_lauf_schritt``, und was hier passiert, ist ein
    ``UPDATE``/``DELETE`` je Schritt in EINER Transaktion
    (``repo.nimm_erkenner_lauf_zurueck``).

    Drei Ausgaenge: zurueckgenommen (die Zeilen der Meldung gehen als
    "Rueckgaengig gemacht:" zurueck in den Chat und ins Journal), seitdem
    geaendert (nichts passiert, die Gruppe erfaehrt, wo sie stattdessen
    hingeht) und schon zurueckgenommen (zweiter Druck -- beantwortet, wirkt
    nicht; die Sperre steht doppelt, hier und in ``behandle``).

    Nach der wirksamen Ruecknahme werden die **Grundleisten-Knoepfe derselben
    Nachricht verfallen gelassen**: der Wert steckt im Knopf, und "Ja,
    speichern" schriebe sonst genau den Wert wieder, den die Gruppe gerade
    weggetippt hat. Die Tastatur selbst nimmt ``behandle`` ab, wie bei jedem
    Knopf.

    **Ein lokaler Faenger um genau den einen Aufruf** (Review-Fix,
    Praezedenz ``_wirkung_textbuch``): der generische Faenger in
    ``bot._bearbeite_knopfdruck`` reicht hier nicht. Der Knopf ist zu diesem
    Zeitpunkt schon ueber ``beanspruche_knopf`` verbraucht -- wirft
    ``repo.nimm_erkenner_lauf_zurueck`` (etwa ``sqlite3.OperationalError``
    "database is locked" beim Stempel-UPDATE, vier Bots und das Web teilen
    dieselbe Datei), bekaeme die Gruppe ohne diesen Faenger gar keine Antwort,
    die Tastatur bliebe haengen, und ein zweiter Druck liefe in
    ``repo.beanspruche_knopf`` ins Leere und antwortete
    ``_TEXT_SCHON_BENUTZT`` ("Das habe ich schon uebernommen.") -- fuer ein
    gescheitertes Undo eine falsche Erfolgsmeldung, obwohl der Wert
    unveraendert steht. Die Transaktion selbst ist in jedem Fall sauber: sie
    rollt bei einer Ausnahme vollstaendig zurueck
    (``except BaseException: conn.rollback(); raise`` in
    ``repo.nimm_erkenner_lauf_zurueck``)."""
    if not d.wert.strip().isdigit():
        return T._TEXT_UNBEKANNT
    lauf_id = int(d.wert.strip())
    lauf = repo.hole_erkenner_lauf(conn, lauf_id)
    if lauf is None or lauf["chat_id"] != d.chat_id:
        return T._TEXT_UNBEKANNT

    try:
        stand = repo.nimm_erkenner_lauf_zurueck(
            conn, lauf_id, ruecknahme.verweise(),
            ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
        )
    except Exception:
        log.exception(
            "Ruecknahme fehlgeschlagen, lauf_id=%s, chat_id=%s",
            lauf_id, d.chat_id,
        )
        repo.merke_vorfall(
            conn, d.chat_id, getattr(d.e, "bot_name", None),
            "undo_fehlgeschlagen",
            f"nimm_erkenner_lauf_zurueck(lauf_id={lauf_id}) hat eine "
            "Ausnahme geworfen -- die Transaktion ist intern zurueckgerollt, "
            "zurueckgenommen wurde nichts.",
        )
        message_id = d.tg.sende(d.chat_id, T._TEXT_UNDO_FEHLER, system=True)
        repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, T._TEXT_UNDO_FEHLER)
        return T._TEXT_UNDO_FEHLER
    if stand == repo.ZURUECK_GEAENDERT:
        message_id = d.tg.sende(d.chat_id, T._TEXT_UNDO_GEAENDERT, system=True)
        repo.merke_bot_zeile(
            conn, d.chat_id, message_id, d.e, T._TEXT_UNDO_GEAENDERT
        )
        return T._ANTWORT_UNDO_GEAENDERT
    if stand != repo.ZURUECK_OK:
        return T._TEXT_SCHON_BENUTZT

    if lauf["message_id"]:
        repo.verfallen_lassen(conn, [
            k["id"] for k in repo.offene_knoepfe_der_nachricht(
                conn, d.chat_id, lauf["message_id"])
        ])
    zeilen = lauf["meldung"] or ""
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_UNDO.format(zeilen=" / ".join(zeilen.splitlines())),
        quelle="undo",
    )
    text = T._TEXT_UNDO_ERLEDIGT.format(zeilen=zeilen)
    leiste = redo_leiste(conn, d.chat_id, lauf_id)
    message_id = _sende_knoepfe(conn, d.tg, d.chat_id, text, leiste, system=True)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return T._ANTWORT_UNDO


def _wirkung_redo(conn, d: Druck) -> str:
    """Stellt einen zurueckgenommenen Erkennerlauf wieder her (Befund 1a,
    Padua Phase-2-Ende 04.10.2026) -- der Spiegel von ``_wirkung_undo``,
    gleiche drei Ausgaenge, gleicher lokaler Faenger (Praezedenz dort)."""
    if not d.wert.strip().isdigit():
        return T._TEXT_UNBEKANNT
    lauf_id = int(d.wert.strip())
    lauf = repo.hole_erkenner_lauf(conn, lauf_id)
    if lauf is None or lauf["chat_id"] != d.chat_id:
        return T._TEXT_UNBEKANNT

    try:
        stand = repo.stelle_erkenner_lauf_wieder_her(
            conn, lauf_id, ruecknahme.verweise(),
            ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
        )
    except Exception:
        log.exception(
            "Wiederherstellung fehlgeschlagen, lauf_id=%s, chat_id=%s",
            lauf_id, d.chat_id,
        )
        repo.merke_vorfall(
            conn, d.chat_id, getattr(d.e, "bot_name", None),
            "redo_fehlgeschlagen",
            f"stelle_erkenner_lauf_wieder_her(lauf_id={lauf_id}) hat "
            "eine Ausnahme geworfen -- die Transaktion ist intern "
            "zurueckgerollt, wiederhergestellt wurde nichts.",
        )
        message_id = d.tg.sende(d.chat_id, T._TEXT_REDO_FEHLER, system=True)
        repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, T._TEXT_REDO_FEHLER)
        return T._TEXT_REDO_FEHLER
    if stand == repo.ZURUECK_GEAENDERT:
        message_id = d.tg.sende(d.chat_id, T._TEXT_REDO_GEAENDERT, system=True)
        repo.merke_bot_zeile(
            conn, d.chat_id, message_id, d.e, T._TEXT_REDO_GEAENDERT
        )
        return T._ANTWORT_REDO_GEAENDERT
    if stand != repo.ZURUECK_OK:
        return T._TEXT_SCHON_BENUTZT

    # Befund 2 (Padua Phase-2-Ende): steht nach dem Redo arbeitsstand.fragen
    # wieder und fehlt die Eroeffnung noch, startet sie automatisch --
    # derselbe Weg wie _schliesse_fragen_ab/frage_weich_uebernehmen/
    # frage_weich_lassen in fragen.py. Ohne das blieb die Gruppe nach einem
    # Redo bei der allgemeinen Interview-Bedienhilfe haengen, weil
    # interview_eroeffnung/-abschluss nie gesetzt wurden.
    #
    # Nur, wenn der Durchgang Frage fuer Frage abgeschlossen ist
    # (``fragen_herkunft_final`` gesetzt -- nur ``_schliesse_fragen_ab``
    # schreibt es, dieselbe Marke wie ``roadmap.fragenuebersicht``). Befund
    # H1 (Feedbackloop P1-2, Runde 2): das Redo eines Erkennerlaufs, der die
    # eigenen Fragen der Gruppe schon VOR KI-Vergleich und Einzeldurchgang
    # gespeichert hatte, startete die Eroeffnung -- deren Autosave sprang
    # ohne Zutun der Gruppe nach Phase 3. Redo stellt Daten her; die Phase
    # setzt allein die Gruppe (AGENTS.md).
    stand_jetzt = repo.hole_arbeitsstand(conn, d.chat_id)
    if (stand_jetzt is not None
            and (stand_jetzt["fragen"] or "").strip()
            and stand_jetzt["fragen_herkunft_final"] is not None
            and not (stand_jetzt["interview_eroeffnung"] or "").strip()):
        starte_eroeffnung(conn, d.tg, d.klm, d.e, d.chat_id)

    zeilen = lauf["meldung"] or ""
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        T._JOURNAL_REDO.format(zeilen=" / ".join(zeilen.splitlines())),
        quelle="redo",
    )
    text = T._TEXT_REDO_ERLEDIGT.format(zeilen=zeilen)
    message_id = d.tg.sende(d.chat_id, text, system=True)
    repo.merke_bot_zeile(conn, d.chat_id, message_id, d.e, text)
    return T._ANTWORT_REDO


#: Die Dispatch-Tabelle: art -> Handler. Sie ersetzt die frueheren
#: if/elif-Kaskaden in ``_wirke`` und ``_wirke_phase6`` (06.09.2026) und ist
#: zugleich die Liste, an der sich die drei Zusagen aus dem Moduldocstring
#: pruefen lassen: ``tests/test_knoepfe_struktur.py`` liest sie per AST und
#: haelt fest, dass kein Handler ein Sprachmodell anfasst.
_WIRKUNGEN = {
    ART_SZENENFOLGE_SPEICHERN: _wirkung_szenenfolge_speichern,
    ART_GESCHICHTE_SCHREIBEN: _wirkung_geschichte_schreiben,
    ART_GESCHICHTE_PASST: _wirkung_geschichte_passt,
    ART_GESCHICHTE_ANDERS: _wirkung_geschichte_anders,
    ART_GESCHICHTE_KUERZEN: _wirkung_geschichte_kuerzen,
    ART_GESCHICHTE_NEU: _wirkung_geschichte_neu,
    ART_GESCHICHTE_SPEICHERN: _wirkung_geschichte_speichern,
    ART_SCHAERFUNG_SZENE: _wirkung_schaerfung_szene,
    ART_SCHAERFUNG_FIGUR: _wirkung_schaerfung_figur,
    ART_SCHAERFUNG_STELLE: _wirkung_schaerfung_stelle,
    ART_SCHAERFUNG_KEINE: _wirkung_schaerfung_keine,
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
    ART_SZENE_KUERZEN: _wirkung_szene_kuerzen,
    ART_UEBERSICHT_PASST: _wirkung_uebersicht_passt,
    ART_SPRECHWEISEN_PASST: _wirkung_sprechweisen_passt,
    ART_SPRECHWEISEN_ANDERS: _wirkung_sprechweisen_anders,
    ART_UEBERSICHT_ANDERS: _wirkung_uebersicht_anders,
    ART_ERSTENTWURF: _wirkung_erstentwurf,
    ART_SZENE_NEU: _wirkung_szene_neu,
    ART_SZENE_SO_LASSEN: _wirkung_szene_so_lassen,
    ART_SZENE_NAECHSTE: _wirkung_szene_naechste,
    ART_DURCHLAUF_SZENE: _wirkung_durchlauf_szene,
    ART_PRUEFUNG_SZENE: _wirkung_pruefung_szene,
    ART_PRUEFUNG_LASSEN: _wirkung_pruefung_lassen,
    ART_PRUEFUNG_RUNDE: _wirkung_pruefung_runde,
    ART_DRAMATURGIE: _wirkung_dramaturgie,
    ART_DRAMATURGIE_SZENE: _wirkung_dramaturgie_szene,
    ART_DRAMATURGIE_LASSEN: _wirkung_dramaturgie_lassen,
    ART_TEXTBUCH: _wirkung_textbuch,
    ART_FORMBERATER: _wirkung_formberater,
    ART_SPRECHANTEILE: _wirkung_sprechanteile,
    ART_FASSUNGEN: _wirkung_fassungen,
    ART_SPEICHERN: _wirkung_speichern,
    ART_BOARD_UEBERNEHMEN: _wirkung_board_uebernehmen,
    ART_BOARD_AENDERN: _wirkung_board_aendern,
    ART_ANDERS: _wirkung_anders,
    ART_EIGENE: _wirkung_eigene,
    ART_FRAGE_WAHL: _wirkung_frage_wahl,
    ART_FRAGEN_UEBERNEHMEN: _wirkung_frage_wahl,
    ART_FRAGEN_ANDERE: _wirkung_fragen_andere,
    ART_FRAGEN_EIGENE: _wirkung_fragen_eigene,
    ART_FRAGEN_EINZELN: _wirkung_fragen_einzeln,
    ART_FRAGEN_VORSCHLAGEN: _wirkung_fragen_vorschlagen,
    ART_FRAGEN_NOCH_EIGENE: _wirkung_fragen_noch_eigene,
    ART_FRAGEN_JA_VORSCHLAGEN: _wirkung_fragen_ja_vorschlagen,
    ART_FRAGE_ANNEHMEN: _wirkung_frage_annehmen,
    ART_FRAGE_VERWERFEN: _wirkung_frage_verwerfen,
    ART_FRAGE_SCHAERFEN: _wirkung_frage_schaerfen,
    ART_FRAGEN_WEICH_UEBERNEHMEN: _wirkung_fragen_weich_uebernehmen,
    ART_FRAGEN_WEICH_LASSEN: _wirkung_fragen_weich_lassen,
    ART_FRAGEN_UMFORMULIEREN_ALLE: _wirkung_fragen_umformulieren_alle,
    ART_FRAGEN_UMFORMULIEREN_KEINE: _wirkung_fragen_umformulieren_keine,
    ART_FRAGEN_UMFORMULIEREN_ANBIETEN: _wirkung_fragen_umformulieren_anbieten,
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
    ART_FIGUR_STIL: _wirkung_figur_stil,
    ART_FIGUR_STIL_FREI: _wirkung_figur_stil_frei,
    ART_FIGUREN_ZUFALL: _wirkung_figuren_zufall,
    ART_FIGUR_ENTFERNEN: _wirkung_figur_entfernen,
    ART_RAHMEN: _wirkung_rahmen,
    ART_WIR_ZUERST: _wirkung_wir_zuerst,
    ART_SCHLAG_VOR: _wirkung_schlag_vor,
    ART_AUSWERTEN_ALLE: _wirkung_auswerten_alle,
    ART_TEIL_WEITER: _wirkung_teil_weiter,
    ART_TEIL_FERTIG: _wirkung_teil_fertig,
    ART_INTERVIEWS_FERTIG: _wirkung_interviews_fertig,
    ART_OHNE_KNOPF_JA: _wirkung_ohne_knopf_ja,
    ART_OHNE_KNOPF_NEIN: _wirkung_ohne_knopf_nein,
    ART_OHNE_KNOPF_WEITER: _wirkung_ohne_knopf_weiter,
    ART_OHNE_KNOPF_FERTIG: _wirkung_ohne_knopf_fertig,
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
    ART_SZENENSTIL: _wirkung_szenenstil,
    ART_SZENE_USA: _wirkung_szene_usa,
    ART_STT_SPRACHE: _wirkung_stt_sprache,
    ART_UNDO: _wirkung_undo,
    ART_REDO: _wirkung_redo,
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
        return T._TEXT_UNBEKANNT
    return wirkung(conn, Druck(tg, klm, e, knopf, chat_id))


def _beantworte(tg, callback_query_id: str, text: str = "") -> None:
    """``answerCallbackQuery`` mit geschlucktem Fehler (06.09.2026, Birk
    12:05).

    Telegram antwortet mit **400**, sobald der Druck aelter als rund eine
    Minute ist ("query is too old"). Das ist kein Fehler des Bots: die
    Wirkung ist laengst eingetreten, nur die Ladeanzeige laesst sich nicht
    mehr abschalten. Bis heute stand dafuer ein Traceback im Log und
    verdeckte die echten Fehler."""
    try:
        tg.beantworte_knopf(callback_query_id, text)
    except Exception as fehler:
        log.info("answerCallbackQuery nicht zugestellt: %s", fehler)


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
        _beantworte(tg, druck["callback_query_id"], T._TEXT_UNBEKANNT)
        return True

    chat_id = knopf["chat_id"]
    if not repo.beanspruche_knopf(conn, knopf_id):
        # Zweiter Druck: beantworten, aber nichts wiederholen (AGENTS.md).
        _beantworte(tg, druck["callback_query_id"], T._TEXT_SCHON_BENUTZT)
        _entferne_tastatur(tg, chat_id, druck["message_id"])
        return True

    meldung = _wirke(conn, tg, klm, e, knopf, chat_id)
    _beantworte(tg, druck["callback_query_id"], meldung)
    _entferne_tastatur(tg, chat_id, druck["message_id"])
    return True

"""Inline-Knoepfe fuer die Auswahl-Momente (05.09.2026).

**Warum es das gibt.** Die Sprachnavigation ist an Auswahl-Momenten
unzuverlaessig -- gemessen am 05.09.2026: der Absichtserkenner
(``erkenner.py``) erkennt eine Kernthema-Festlegung zuverlaessig, wenn er das
ganze Gespraech sieht (3/3), aber live sieht er nur ein Fenster von ein bis
drei Nachrichten. Im Fenster mit der Zustimmung schrieb er ``entschieden``
(eine Journalnotiz) statt ``kernthema_setzen`` (ein Arbeitsstand-Feld). Die
Festlegung landete deshalb nicht in der Datenbank und erschien nicht auf der
Weboberflaeche.

Ein Knopf traegt die Auswahl selbst -- es ist nichts zu erraten. Genau dafuer,
und nur dafuer, sind Knoepfe hier gedacht: **Stellen, an denen die Gruppe aus
wenigen benannten Moeglichkeiten waehlt** (Kernthema, Aufnahme an/aus,
naechste Phase, Form und Stil je Szene, USA-Einwilligung). Alles andere --
Begriffe, Fragen, Figurenbeschreibungen -- bleibt bewusst Sprache: dort gibt
es keine Liste, aus der sich waehlen liesse.

**Drei Zusagen, an denen sich dieser Code messen laesst:**

1. ``callback_data`` bleibt unter 64 Bytes (Telegram-Grenze). Ein Knopf traegt
   nur ``k:<id>`` -- der eigentliche Wert (ein Kernthema kann laenger sein als
   die ganze Grenze) steht in der Tabelle ``knopf``. Geprueft wird die Grenze
   in ``telegram.Telegram.sende_mit_knoepfen``, nicht hier.
2. **Kein Modellaufruf.** Wie bei den Slash-Befehlen (``befehle.py``) greift
   ein Knopf frueh und deterministisch: ``bot.schleife`` gibt ihn ab, bevor
   irgendein Kontext gebaut wird. Was ein Modell braucht, geht wie ueberall an
   einen eigenen Thread (``basis._starte_auftrag``).
3. **Idempotent.** Jeder Druck wird ueber ``repo.beanspruche_knopf``
   beansprucht -- ein bedingtes UPDATE, das nur einmal gewinnt. Der zweite
   Druck bekommt eine freundliche Rueckmeldung und loest nichts aus.

``tests/test_knoepfe_struktur.py`` haelt alle drei am Quelltext fest.

**Der Aufbau** (06.09.2026: die Datei war auf 5.500 Zeilen gewachsen und
zerfiel entlang dieser Schichten von selbst). Jede Schicht liest nur nach
unten; die fuenf Aufrufe nach oben stehen als lokaler Import in der Funktion,
die sie braucht:

* ``texte.py`` -- Arten, Wortlaute, Phasennummern, Auftragsvorlagen
* ``basis.py`` -- callback_data, Grundleiste, Speicherweg, Auftragsabgabe
* ``fragen.py`` -- Phase 2
* ``figuren.py`` -- Phase 4
* ``szenen.py`` -- Phasen 5 bis 8
* ``interviews.py`` -- Phase 3
* ``stationen.py`` -- der Phasenrahmen im Chat
* ``wirkung.py`` -- die Dispatch-Tabelle und ihre Handler

Dieses ``__init__`` re-exportiert die vollstaendige bisherige Modulflaeche,
damit kein Aufrufer angepasst werden muss: ``knoepfe.behandle``,
``knoepfe.biete_phase_proaktiv``, ``knoepfe.ART_SPEICHERN`` und alles Weitere
sind unveraendert erreichbar.
"""

import random
import re
from typing import NamedTuple

from interview_theater import phasen, repo

#: Arten, Wortlaute, Phasennummern, Auftragsvorlagen
from interview_theater.knoepfe.texte import (  # noqa: F401
    ANWEISUNGEN, ANWEISUNG_DUKTUS, ANWEISUNG_EINLEITUNGEN,
    ANWEISUNG_EROEFFNUNG, ANWEISUNG_FIGURENZAHL, ANWEISUNG_FRAGEN_ANDERE,
    ANWEISUNG_FRAGEN_EIGENE, ANWEISUNG_KERNFRAGE, ANWEISUNG_KERNTHEMA,
    ANWEISUNG_NAMEN, ART_ANDERS, ART_AUFNAHME, ART_AUSWERTEN,
    ART_AUSWERTEN_ALLE, ART_DURCHLAUF_SZENE, ART_EIGENE, ART_FIGUREN_ANZAHL,
    ART_FIGUREN_ANZAHL_FREI, ART_FIGUREN_ANZAHL_MENU, ART_FIGUREN_NAMEN_MENU,
    ART_FIGUREN_ZUFALL, ART_FIGUR_DUKTUS, ART_FIGUR_DUKTUS_MENU,
    ART_FIGUR_ENTFERNEN, ART_FIGUR_INTERVIEW, ART_FIGUR_INTERVIEW_MENU,
    ART_FIGUR_NAME, ART_FIGUR_NAME_MENU, ART_FIGUR_PASST, ART_FIGUR_STIL,
    ART_FIGUR_STIL_FREI, ART_FRAGEN_ANDERE, ART_FRAGEN_EIGENE,
    ART_FRAGEN_UEBERNEHMEN, ART_FRAGE_WAHL, ART_GESCHICHTE_ANDERS,
    ART_GESCHICHTE_NEU, ART_GESCHICHTE_PASST, ART_GESCHICHTE_SCHREIBEN,
    ART_GESCHICHTE_SPEICHERN, ART_HILFE, ART_KERNTHEMA, ART_LEITFADEN,
    ART_NOCH_NICHT, ART_OHNE_KNOPF_FERTIG, ART_OHNE_KNOPF_JA,
    ART_OHNE_KNOPF_NEIN, ART_OHNE_KNOPF_WEITER, ART_PHASE, ART_PRUEFUNG_LASSEN,
    ART_PRUEFUNG_RUNDE, ART_PRUEFUNG_SZENE, ART_RAHMEN, ART_RICHTUNG,
    ART_SCHAERFUNG_FIGUR, ART_SCHAERFUNG_KEINE, ART_SCHAERFUNG_RUNDE,
    ART_SCHAERFUNG_STELLE, ART_SCHAERFUNG_SZENE, ART_SCHLAG_VOR, ART_SPEICHERN,
    ART_STAND, ART_SZENENFELDER_SPEICHERN, ART_SZENENFOLGE_ANZAHL,
    ART_SZENENFOLGE_ANZAHL_WERT, ART_SZENENFOLGE_REIHENFOLGE,
    ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM, ART_SZENENSTIL,
    ART_SZENE_ANDERS, ART_SZENE_FORM, ART_SZENE_NAECHSTE, ART_SZENE_NEU,
    ART_SZENE_PASST, ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN,
    ART_SZENE_SO_LASSEN, ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA,
    ART_SZENE_ZEIGEN, ART_TEIL_FERTIG, ART_TEIL_WEITER, ART_TEXTBUCH,
    ART_TRANSKRIPT, ART_WIR_ZUERST, ART_ZUSAMMENFASSUNG, FIGURENZAHLEN,
    FIGURENZAHL_MAX, FIGURENZAHL_MIN, FRAGEN_ANZAHL, FRAGEN_JE_BEGRIFF,
    FRAGEN_ZUR_WAHL, KNOPF_LAENGE, MAX_AUSWAHL, MAX_VORSCHLAEGE,
    MENUE_KNOPF_LAENGE, PHASE_DURCHLAUF, PHASE_GESCHICHTE, PHASE_INTERVIEWS,
    PHASE_RAHMEN, PHASE_SCHAERFUNG, PHASE_SETTING, PHASE_STUECKPRUEFUNG,
    PHASE_SZENEN, PRAEFIX, TEXT_ABLAUF, TEXT_ANDERS_KNOPF, TEXT_ANZAHL_KNOPF,
    TEXT_ARBEIT_EROEFFNUNG, TEXT_ARBEIT_SENSIBILITAET,
    TEXT_DURCHLAUF_SZENE_KNOPF, TEXT_EIGENE_IDEE_KNOPF,
    TEXT_FORM_VORSCHLAG_ZUSATZ, TEXT_GESCHICHTE_SCHREIBEN_KNOPF,
    TEXT_NAECHSTE_KNOPF, TEXT_NEU_KNOPF, TEXT_PASST_KNOPF,
    TEXT_PRUEFUNG_LAEUFT, TEXT_REIHENFOLGE_KNOPF, TEXT_SCHAERFUNG_RUNDE_KNOPF,
    TEXT_SZENE_FORM_KNOPF, TEXT_SZENE_PLANEN_KNOPF, TEXT_SZENE_SCHREIBEN_KNOPF,
    TEXT_SZENE_SO_LASSEN_KNOPF, TEXT_SZENE_UEBERSPRINGEN_KNOPF,
    TEXT_TEXTBUCH_KNOPF, TEXT_WEITER_KNOPF, TRENNER, _ANWEISUNG_ALLGEMEIN,
    _AUSWAHLMARKER, _ERSTER_ALS_WERT, _FELD_FUER, _HAKEN, _KETTE, _NOTIERT,
    _TEXT_ANDERS, _TEXT_ANDERS_KNOPF, _TEXT_ANZAHL_FRAGE,
    _TEXT_AUFNAHME_BEENDEN, _TEXT_AUFNAHME_STARTEN, _TEXT_AUSWERTEN_ALLE_KNOPF,
    _TEXT_AUSWERTEN_ALLE_LAEUFT, _TEXT_AUSWERTEN_ALLE_NICHTS,
    _TEXT_AUSWERTEN_KNOPF, _TEXT_AUSWERTEN_UNBEKANNT,
    _TEXT_AUSWERTEN_UNMOEGLICH, _TEXT_DUKTUS_FEHLT, _TEXT_DUKTUS_LAEUFT,
    _TEXT_DUKTUS_OHNE_QUELLE, _TEXT_EIGENE, _TEXT_EIGENE_IDEE,
    _TEXT_EIGENE_KNOPF, _TEXT_FIGURENZAHL_UNKLAR,
    _TEXT_FIGUREN_ANZAHL_ERSTFRAGE, _TEXT_FIGUREN_ANZAHL_FRAGE,
    _TEXT_FIGUREN_ANZAHL_FREI_FRAGE, _TEXT_FIGUREN_ANZAHL_FREI_KNOPF,
    _TEXT_FIGUREN_ANZAHL_KNOPF, _TEXT_FIGUREN_FIXIERT, _TEXT_FIGUREN_KEINE,
    _TEXT_FIGUREN_NAMEN_FRAGE, _TEXT_FIGUREN_NAMEN_KNOPF,
    _TEXT_FIGUREN_ZUFALL_FERTIG, _TEXT_FIGUREN_ZUFALL_KNOPF,
    _TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN, _TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW,
    _TEXT_FIGUR_DUKTUS_KNOPF, _TEXT_FIGUR_ENTFERNEN_KNOPF,
    _TEXT_FIGUR_INTERVIEW_FRAGE, _TEXT_FIGUR_INTERVIEW_KNOPF,
    _TEXT_FIGUR_PASST_KNOPF, _TEXT_FOLGE_GESPEICHERT, _TEXT_FOLGE_LEER,
    _TEXT_FRAGEN_ANDERE_KNOPF, _TEXT_FRAGEN_EIGENE, _TEXT_FRAGEN_EIGENE_KNOPF,
    _TEXT_FRAGEN_KEINE_AUSWAHL, _TEXT_FRAGEN_NICHT_DREI, _TEXT_FRAGEN_NOTIERT,
    _TEXT_FRAGEN_NUMMERN_FALSCH, _TEXT_FRAGEN_UEBERNEHMEN_KNOPF,
    _TEXT_FRAGEN_UEBERNOMMEN, _TEXT_FRAGEN_WAHL, _TEXT_GESCHICHTE_ANDERS,
    _TEXT_GESCHICHTE_ANDERS_KNOPF, _TEXT_GESCHICHTE_GESPEICHERT,
    _TEXT_GESCHICHTE_LEER, _TEXT_GESCHICHTE_NEU_KNOPF, _TEXT_GESCHICHTE_PASST,
    _TEXT_GESCHICHTE_PASST_KNOPF, _TEXT_HILFE_KNOPF, _TEXT_KEINE_NAECHSTE,
    _TEXT_KEIN_INTERVIEW, _TEXT_KEIN_TRANSKRIPT, _TEXT_KERNTHEMA_FRAGE,
    _TEXT_KERNTHEMA_KEINE, _TEXT_KURZGESCHICHTE_BEREIT, _TEXT_LEITFADEN_KNOPF,
    _TEXT_MENUE_ANDERS_KNOPF, _TEXT_NACH_SPEICHERN_FRAGE,
    _TEXT_NAECHSTE_AUFNAHME_KNOPF, _TEXT_NOCH_NICHT,
    _TEXT_OHNE_KNOPF_FERTIG_KNOPF, _TEXT_OHNE_KNOPF_JA_KNOPF,
    _TEXT_OHNE_KNOPF_NEIN_KNOPF, _TEXT_OHNE_KNOPF_UNBEKANNT,
    _TEXT_OHNE_KNOPF_WEITER, _TEXT_OHNE_KNOPF_WEITER_KNOPF, _TEXT_PASST,
    _TEXT_PHASE_ANGEBOT, _TEXT_PHASE_NOCH_NICHT_KNOPF, _TEXT_PHASE_WEITER,
    _TEXT_PROAKTIV, _TEXT_PROBENANSICHT, _TEXT_PRUEFUNG_LAEUFT,
    _TEXT_PRUEFUNG_LASSEN, _TEXT_PRUEFUNG_LASSEN_KNOPF,
    _TEXT_PRUEFUNG_RUNDE_KNOPF, _TEXT_PRUEFUNG_SZENE_KNOPF,
    _TEXT_PRUEFUNG_UEBERHOLT, _TEXT_PRUEFUNG_UNBEKANNT,
    _TEXT_REIHENFOLGE_FRAGE, _TEXT_RICHTUNG_GESPEICHERT,
    _TEXT_SCHAERFUNG_ALLE_KNOPF, _TEXT_SCHAERFUNG_DURCH,
    _TEXT_SCHAERFUNG_KEINE_KNOPF, _TEXT_SCHAERFUNG_LAEUFT,
    _TEXT_SCHAERFUNG_NICHTS, _TEXT_SCHAERFUNG_STELLE_UEBERNOMMEN,
    _TEXT_SCHAERFUNG_STELLE_UNBEKANNT, _TEXT_SCHAERFUNG_UEBERNOMMEN,
    _TEXT_SCHAERFUNG_VERWORFEN, _TEXT_SCHLAG_VOR_KNOPF, _TEXT_SCHON_BENUTZT,
    _TEXT_SCHON_GESETZT, _TEXT_SPAETERE_GEPRUEFT, _TEXT_SPEICHERN_KNOPF,
    _TEXT_STAND_KNOPF, _TEXT_STIL_EIGENER, _TEXT_STIL_EIGENER_KNOPF,
    _TEXT_STIL_FRAGE, _TEXT_STIL_GESPEICHERT, _TEXT_SZENENFORM_FRAGE,
    _TEXT_SZENE_ANDERS_FRAGE, _TEXT_SZENE_OHNE_TEXT, _TEXT_SZENE_PLANEN_FRAGE,
    _TEXT_SZENE_SO_GELASSEN, _TEXT_SZENE_UEBERSPRUNGEN, _TEXT_SZENE_UNBEKANNT,
    _TEXT_TEIL_FERTIG_KNOPF, _TEXT_TEIL_SCHON_AUS, _TEXT_TEIL_WEITER,
    _TEXT_TEIL_WEITER_KNOPF, _TEXT_TEXTBUCH_BESCHREIBUNG,
    _TEXT_TEXTBUCH_FEHLER, _TEXT_TRANSKRIPT_KNOPF,
    _TEXT_TROTZDEM_AUSWERTEN_KNOPF, _TEXT_UNBEKANNT, _TEXT_USA_FRAGE_KNOEPFE,
    _TEXT_USA_JA, _TEXT_USA_JA_KNOPF, _TEXT_USA_NEIN, _TEXT_USA_NEIN_KNOPF,
    _TEXT_WEITER_FRAGE, _TEXT_WIR_ZUERST, _TEXT_WIR_ZUERST_KNOPF,
    _TEXT_ZITATE_VORSPANN, _TEXT_ZUR_GESCHICHTE, _TEXT_ZUSAMMENFASSUNG_KNOPF,
    log,
)

#: callback_data, Grundleiste, Speicherweg, Auftragsabgabe
from interview_theater.knoepfe.basis import (  # noqa: F401
    _auswahlleiste, _daten, _ein_feld_je_nachricht, _entferne_tastatur,
    _erster_block, _feld_ist_frei, _id_aus_daten, _ist_bestaetigung,
    _leistenwert, _merke_botnachricht, _mit_leiste, _nimm_alte_leiste_ab,
    _phasenknopf, _sende_knoepfe, _sende_menue, _sende_rueckspiegelung,
    _speichere, _starte_auftrag, biete_kernthema, biete_phase, grundleiste,
    kernthema_vorschlaege, offene_art, sende_mit_speicherleiste,
    sende_notiert_mit_leiste, speicherleiste,
)

#: Phase 2
from interview_theater.knoepfe.fragen import (  # noqa: F401
    _ORDINALWOERTER, _auswahlfragen, _fragenleiste, _gewaehlte, _knopftext,
    _leitfaden_knopf, _speichere_eroeffnung, _uebernimm_fragen,
    biete_fragenauswahl, fragenliste, lies_fragennummern, nimm_fragennummern,
    starte_eroeffnung, starte_sensibilitaetspruefung,
)

def biete_aufnahme(conn, tg, chat_id: int, text: str, knopf: bool = True) -> int:
    """Haengt den Aufnahme-Umschalter unter ``text``; liefert die
    ``message_id`` der Angebotsnachricht.

    Die message_id wird zurueckgegeben, weil der Erkenner-Pfad
    (``erkenner._melde_interviewmodus``) seine Bestaetigung wie jede andere
    Bot-Nachricht mitschreibt (``repo.merke_nachricht``) und dafuer die id
    braucht -- vorher stand dort ein ``tg.sende``, das sie ohnehin lieferte.

    Die Beschriftung richtet sich nach dem Zustand JETZT: laeuft eine
    Aufnahme, heisst der Knopf "Aufnahme beenden", sonst "Aufnahme starten".
    Die Wirkung ist beide Male dieselbe wie ``/aufnahme`` -- ein Umschalter,
    kein Ein- und ein Ausschalter (befehle._befehl_aufnahme): sonst gaebe es
    zwei Zustaende und drei Bedienelemente, und genau daran ist die
    gesprochene Variante am 05.09.2026 gescheitert.

    ``knopf=False`` schickt denselben Text OHNE Tastatur (05.09.2026,
    Live-Fall Gruppe 1, 14:21): unter der Startbestaetigung ("Aufnahme
    laeuft ...") hing bis dahin sofort "Aufnahme beenden" -- sieben Sekunden
    spaeter war er gedrueckt, und es entstand ein leeres Interview. Die
    Beenden-Moeglichkeit kommt seitdem erst mit dem ersten Teil-Transkript
    (``biete_nach_teil``), also dann, wenn es ueberhaupt etwas zu beenden
    gibt."""
    if not knopf:
        return tg.sende(chat_id, text)
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = _TEXT_AUFNAHME_BEENDEN if laeuft else _TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    return _sende_knoepfe(conn, tg, chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_nach_teil(conn, tg, chat_id: int, text: str) -> int:
    """Die Leiste unter einem Teil-Transkript: "Interview geht weiter" ·
    "Interview ist fertig" (05.09.2026, Birk nach dem Live-Lauf Gruppe 1).

    Der gemessene Fall: nach dem Echo "Interview 4, Teil 1: ..." stand das
    Transkript einfach da. Die Gruppe im Raum konnte nicht sehen, ob der Bot
    weiter aufnimmt oder ob das Interview zu Ende ist -- Birk: "das sollte
    aktiv als naechste Antwort angeboten werden nach dem Transkript, nicht
    mit Transkript einfach so stehen lassen."

    Zwei Knoepfe, beide ohne Modellaufruf: "geht weiter" nimmt nur die
    Tastatur ab und sagt einen Satz, "ist fertig" ist wortgleich derselbe
    Weg wie "Aufnahme beenden" (``befehle._befehl_aufnahme``).

    Ein neues Echo nimmt der vorherigen Leiste die Tastatur ab
    (``_nimm_alte_leiste_ab``): sonst staenden nach fuenf Sprachnachrichten
    fuenf Leisten im Chat, und ein Druck auf die von vor drei Nachrichten
    beendete das Interview, ohne dass jemand das gemeint haette.

    Liefert die ``message_id`` der Echo-Nachricht."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_WEITER)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_FERTIG)
    leiste = [
        (
            _TEXT_TEIL_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_WEITER, None)),
        ),
        (
            _TEXT_TEIL_FERTIG_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_FERTIG, None)),
        ),
    ]
    # **Hier NICHT ueber ``_sende_knoepfe``**: der Text ist ein
    # Teil-Transkript, und das schreibt ``aufnahme.py`` selbst mit
    # ``typ='transkript'`` mit -- sonst laege Interviewinhalt als
    # Gruppenbeitrag im Erkenner-Fenster (§ 10.6).
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def biete_interview_ohne_knopf(
    conn, tg, chat_id: int, text: str, aufnahme_id: int
) -> int:
    """Die zwei Knoepfe unter \"Das klingt nach einem Interview (M:SS)\":
    \"Ja, als Interview\" · \"Nein, war ein Beitrag\" (06.09.2026, Live-Fall
    Gruppe 1 13:32).

    Die Knopfregel ist erfuellt (AGENTS.md): es gibt etwas Fixes zu
    speichern, naemlich diese eine Aufnahme, und genau zwei benannte
    Moeglichkeiten. Die ``aufnahme.id`` steht im ``wert`` der Knopfzeile, nie
    in ``callback_data`` (Zusage 1).

    Eine aeltere, ungedrueckte Leiste derselben Art wird abgenommen: schickt
    eine Gruppe zwei lange Sprachnachrichten hintereinander, soll der Druck
    nicht die vorletzte treffen.

    Liefert die ``message_id`` der Frage."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_OHNE_KNOPF_JA)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_OHNE_KNOPF_NEIN)
    wert = str(aufnahme_id)
    leiste = [
        (
            _TEXT_OHNE_KNOPF_JA_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_JA, wert)),
        ),
        (
            _TEXT_OHNE_KNOPF_NEIN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_NEIN, wert)),
        ),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def biete_interview_ohne_knopf_weiter(conn, tg, chat_id: int, text: str, kopf_id: int) -> int:
    """Die Folgefrage nach \"Ja, als Interview\": \"Fertig, auswerten\" ·
    \"Es kommt noch was\" (06.09.2026).

    Ohne sie waere die Gruppe im Interviewmodus, ohne es entschieden zu
    haben -- und der Kopf bliebe offen, bis jemand zufaellig \"Interview
    beenden\" findet. Der ``wert`` traegt die Kopf-id, damit \"Fertig\" genau
    dieses Interview abschliesst."""
    wert = str(kopf_id)
    leiste = [
        (
            _TEXT_OHNE_KNOPF_FERTIG_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_FERTIG, wert)),
        ),
        (
            _TEXT_OHNE_KNOPF_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_WEITER, wert)),
        ),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def _auswerten_alle_knopf(conn, chat_id: int, ausser: int | None = None) -> tuple[str, str] | None:
    """"Alle auswerten", solange ein beendetes Interview ohne Verdichtung
    offen ist -- sonst None.

    Das Gegenstueck zur Phase-4-Sperre: wo "Weiter zu Phase 4" wegfaellt,
    soll nicht einfach nichts stehen, sondern der Weg dorthin.

    ``ausser`` nimmt das Interview aus, fuer das schon ein eigener
    "Auswerten"-Knopf danebensteht (``biete_nach_aufnahme``): zwei Knoepfe
    fuer dieselbe eine Auswertung waeren keine Auswahl, sondern eine
    Verdopplung -- die Gruppe steht im Raum und trifft den ersten."""
    from interview_theater import aufnahme

    offen = [
        kopf for kopf in aufnahme.unausgewertete_interviews(conn, chat_id)
        if kopf["id"] != ausser
    ]
    if not offen:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN_ALLE, None)
    return (_TEXT_AUSWERTEN_ALLE_KNOPF, _daten(knopf_id))


def _aufnahme_anbieten(conn, chat_id: int, nur_phase_3: bool = False) -> bool:
    """Darf eine Knopfleiste von sich aus eine Aufnahme ANBIETEN?

    Ja ab ``PHASE_INTERVIEWS`` -- und ja, solange eine Aufnahme laeuft, egal
    in welcher Phase: dann heisst der Knopf "Aufnahme beenden", und ein
    laufendes Interview ohne Ausschalter waere die schlechtere Falle als ein
    Angebot zur falschen Zeit.

    Nein in Phase 1 (Begriffe) und 2 (Fragen). Mit ``nur_phase_3`` auch nein
    ab Phase 4: das ist die Leiste NACH einem Interview
    (``biete_nach_aufnahme``) -- hat die Gruppe inzwischen zum Kernthema
    weitergeschaltet, ist "Naechste Aufnahme" dort kein Angebot mehr, sondern
    ein Rueckschritt. In der Einstiegsleiste bleibt der Knopf dagegen auch
    spaeter stehen: nachtraeglich ein Interview zu ergaenzen ist ein normaler
    Vorgang, nur eben keiner, den der Bot vorschlaegt.

    Das ist ausdruecklich nur eine Regel fuer die ANGEBOTE: ``/aufnahme`` und
    der Erkenner-Pfad (``biete_aufnahme``) bleiben phasenunabhaengig, die
    Gruppe darf jederzeit ausdruecklich aufnehmen (AGENTS.md, "Fokus, kein
    Kaefig"). Nur das unaufgeforderte Angebot richtet sich nach der
    Reihenfolge der Phasen."""
    if repo.ist_interviewmodus_an(conn, chat_id):
        return True
    jetzige = phasen.aktuelle(conn, chat_id)
    if nur_phase_3:
        return jetzige == PHASE_INTERVIEWS
    return jetzige >= PHASE_INTERVIEWS


def _interviewknoepfe(conn, chat_id: int, kopf_id: int) -> list[tuple[str, str]]:
    """Die beiden Knoepfe, die an EINEM beendeten Interview haengen:
    Zusammenfassung (oder "Trotzdem auswerten") und Wortlaut.

    **Kein "Auswerten" mehr** (06.09.2026, Birk 09:55): verdichtet wird seit
    dem 05.09. ohnehin sofort, und der Knopf hiess nach einer Handlung, die
    schon passiert war. An seiner Stelle stehen die beiden Wege, die die Gruppe
    wirklich braucht -- die Zusammenfassung lesen und den Wortlaut
    gegenpruefen. Die art ``ART_AUSWERTEN`` bleibt im Code: sie traegt weiter
    den Sonderfall unter ``aufnahme.MINDEST_WOERTER`` ("Trotzdem
    auswerten")."""
    if repo.verdichtung_zu_aufnahme(conn, kopf_id) is not None:
        erster = (
            _TEXT_ZUSAMMENFASSUNG_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_ZUSAMMENFASSUNG, str(kopf_id))
            ),
        )
    else:
        # Unter der Mindestlaenge: hier gibt es nichts zu zeigen, nur
        # etwas zu erzwingen.
        erster = (
            _TEXT_TROTZDEM_AUSWERTEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN, str(kopf_id))),
        )
    return [
        erster,
        (
            _TEXT_TRANSKRIPT_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TRANSKRIPT, str(kopf_id))),
        ),
    ]


def biete_nach_aufnahme(conn, tg, chat_id: int, text: str, kopf_id: int | None) -> int:
    """Die Knopfleiste nach einem beendeten Interview (05.09.2026, Birk:
    "ersetze am besten alle slash befehl vorschlaege mit knoepfen. und gib
    auch immer sinnvolle alternativvorschlaege").

    Der gemessene Fall (Gruppe 2, 13:59): ein Interview unter
    ``aufnahme.MINDEST_WOERTER`` endete mit einem Text, der ``/auswerten``
    empfahl; die Gruppe fragte zweimal nach, und ausgewertet wurde nie. Der
    Grund ist derselbe wie ueberall hier: ein empfohlener Slash-Befehl ist
    eine Bedienungsanleitung, ein Knopf ist der Weg.

    Drei Knoepfe, in dieser Reihenfolge -- der wahrscheinlichste zuletzt ist
    hier falsch, weil die Gruppe im Raum steht und den ersten trifft:

    * **Auswerten** -- die Verdichtung dieses Interviews in den Chat. Liegt
      sie schon vor (der Normalfall: verdichtet wird sofort, ausgespielt
      erst auf Wunsch), wird sie aus der Datenbank ausgespielt; liegt keine
      vor (Interview unter der Mindestlaenge), laeuft wortgleich das, was
      ``/auswerten`` tut. Faellt nur weg, wenn es gar kein Interview gibt
      (``kopf_id`` ist None).
    * **Naechste Aufnahme** -- derselbe Umschalter wie ``/aufnahme``, aber
      nur in Phase 3 (``_aufnahme_anbieten(nur_phase_3=True)``): ist die
      Gruppe schon weiter, waere es ein Rueckschritt statt eines Angebots.
    * **Weiter zu Phase N** -- nur, wenn ``phasen.naechste_moegliche`` es
      hergibt. Das ist die Alternative, die im Live-Fall gefehlt hat: statt
      direkt das naechste Interview zu starten, haette die Gruppe auch in die
      Auswertung gehen koennen.

    Kein Modellaufruf, alles aus der Datenbank -- wie jedes Angebot hier.
    Liefert die ``message_id`` der Angebotsnachricht."""
    knoepfe: list[tuple[str, str]] = []
    if kopf_id is not None:
        knoepfe.extend(_interviewknoepfe(conn, chat_id, kopf_id))
    # "Naechste Aufnahme" statt "Aufnahme starten": nach einem beendeten
    # Interview ist genau das gemeint, und der Wortlaut sagt es. Laeuft wider
    # Erwarten schon wieder eine Aufnahme (ein Knopf aus einer alten
    # Nachricht), heisst er wie ueberall "Aufnahme beenden" -- die Wirkung ist
    # in beiden Faellen der Umschalter aus ``/aufnahme``.
    #
    # Seit 05.09.2026 nur noch, wenn die Phase es hergibt
    # (``_aufnahme_anbieten``): ist die Gruppe waehrend des Interviews schon
    # auf 4 (Kernthema & Figuren) weitergegangen, ist "Naechste Aufnahme"
    # kein Angebot mehr, sondern ein Rueckschritt. "Auswerten" und "Weiter zu
    # Phase N" bleiben davon unberuehrt.
    if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
        knoepfe.append(
            (
                _TEXT_NAECHSTE_AUFNAHME_KNOPF
                if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    # Solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    # ``phasen.naechste_moegliche`` die 4 nicht her (Phase-4-Sperre) -- an
    # ihre Stelle tritt der Weg dorthin: alle offenen auswerten.
    alle = _auswerten_alle_knopf(conn, chat_id, ausser=kopf_id)
    if alle is not None:
        knoepfe.append(alle)
    # Der Leitfaden, solange die Gruppe noch Interviews fuehrt: zwischen zwei
    # Gespraechen ist genau der Moment, in dem jemand nachsehen will, wie der
    # Einstieg nochmal ging (06.09.2026).
    if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
        leitfadenknopf = _leitfaden_knopf(conn, chat_id)
        if leitfadenknopf is not None:
            knoepfe.append(leitfadenknopf)
    # **Nach JEDER Auswertung kommt das Angebot erneut** (06.09.2026, Birk
    # 10:45). Der Merkposten ``phase_angeboten`` haelt sonst fest, dass die
    # Stufe schon einmal angeboten wurde, und ab dem zweiten Interview stand
    # unter der Auswertung kein Weg mehr nach vorn -- die Gruppe im Raum
    # sah nur noch "Naechstes Interview". Hier wird er deshalb abgeraeumt:
    # das Angebot haengt an der Auswertung, nicht am Merkposten.
    if kopf_id is not None and phasen.aktuelle(conn, chat_id) == PHASE_INTERVIEWS:
        phasen.vergiss_angebot(conn, chat_id)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        knoepfe.append(phasenknopf)
    return _sende_knoepfe(conn, tg, chat_id, text, knoepfe)


def biete_einstieg(conn, tg, chat_id: int, text: str) -> int:
    """Die Knopfleiste unter einer Begruessung (Erstkontakt, Wiederkehr):
    "Stand zeigen", "Hilfe" -- und, wenn die Materiallage es hergibt,
    "Weiter zu Phase N".

    "Aufnahme starten" steht seit 05.09.2026 nur noch davor, wenn die Phase
    es hergibt (``_aufnahme_anbieten``): ab Phase 3 (Interviews) oder solange
    eine Aufnahme laeuft. In Phase 1 (Begriffe) und 2 (Fragen) gibt es nichts
    aufzunehmen -- die Begriffe kommen aus dem Plenum als Text oder
    Sprachnachricht, die Fragen entstehen im Gespraech mit dem Bot. Der erste
    Knopf ist der, den die Gruppe im Raum trifft; er darf nicht zwei
    Arbeitsschritte zu weit zeigen.

    Damit steht in der Begruessung selbst kein Slash-Befehl mehr: der Weg ist
    der Knopf, ``/hilfe`` listet die Befehle weiterhin auf, wenn jemand sie
    sucht."""
    knoepfe: list[tuple[str, str]] = []
    if _aufnahme_anbieten(conn, chat_id):
        knoepfe.append(
            (
                _TEXT_AUFNAHME_STARTEN if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    # Der Leitfaden steht im Einstieg der Phase 3 direkt neben dem Start:
    # wer den Bot in der Pause aufmacht, sucht genau diese zwei Dinge
    # (06.09.2026). In anderen Phasen waere er ein Angebot ins Leere.
    if phasen.aktuelle(conn, chat_id) == PHASE_INTERVIEWS:
        leitfadenknopf = _leitfaden_knopf(conn, chat_id)
        if leitfadenknopf is not None:
            knoepfe.append(leitfadenknopf)
    knoepfe += [
        (
            _TEXT_STAND_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_STAND, None)),
        ),
        (
            _TEXT_HILFE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_HILFE, None)),
        ),
    ]
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        # Direkt hinter der Aufnahme, wenn es sie gibt -- sonst ganz vorn: der
        # Schritt in die naechste Phase ist dann die wahrscheinlichste Absicht.
        knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, phasenknopf)
    else:
        # Kein Phasenknopf, aber offene Auswertungen: dann ist DAS der
        # naechste Schritt (Phase-4-Sperre) -- an derselben Stelle.
        alle = _auswerten_alle_knopf(conn, chat_id)
        if alle is not None:
            knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, alle)
    return _sende_knoepfe(conn, tg, chat_id, text, knoepfe)


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
    Abschnitt ist eine Szene."""
    from interview_theater import telegram as telegram_modul

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
        tg.sende(chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
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
    return "Name geaendert"


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
            _TEXT_FIGUREN_ANZAHL_FREI_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_FREI, None)),
        )
    )
    message_id = _sende_knoepfe(conn, tg, chat_id, text or _TEXT_FIGUREN_ANZAHL_ERSTFRAGE, leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id


def uebernimm_figurenanzahl(conn, tg, klm, e, chat_id: int, anzahl: int) -> None:
    """Speichert die Anzahl und laesst im Thread eine Liste mit genau so
    vielen Figuren vorschlagen -- der eine Weg, auf dem eine Zahl wirkt,
    egal ob sie aus einem Knopf oder aus einer Nachricht kam."""
    repo.setze_arbeitsstand(conn, chat_id, "figuren_anzahl", str(anzahl))
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Figurenanzahl: {anzahl}", quelle="knopf",
    )
    _starte_auftrag(
        conn, tg, klm, e, chat_id, ANWEISUNG_FIGURENZAHL.format(anzahl=anzahl),
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
            ANWEISUNG_KERNFRAGE.format(
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
            _TEXT_FIGUREN_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_MENU, None)),
        ),
        (
            _TEXT_FIGUREN_NAMEN_KNOPF,
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
        return _TEXT_UNBEKANNT
    repo.setze_arbeitsstand(conn, chat_id, "figuren_entwurf", wert)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Figuren: {', '.join(angelegt)}",
        quelle="knopf",
    )
    tg.sende(chat_id, "Notiert:\n" + _figurenzeile(angelegt))
    return "Figuren uebernommen"


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
            zeilen.append(f"Sprachduktus: {profil}")
        elif ohne_beleg:
            from interview_theater import sprachprofil

            zeilen.append(
                sprachprofil._TEXT_KEIN_ZITAT.format(name=figur["name"])
            )
        else:
            zeilen.append(_TEXT_DUKTUS_FEHLT)
        zitate = [
            z.strip()
            for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER)
            if z.strip()
        ]
        if zitate:
            zeilen.append("")
            zeilen.append(_TEXT_ZITATE_VORSPANN)
            zeilen.extend(f"– {z}" for z in zitate)
    else:
        zeilen.append(_TEXT_DUKTUS_OHNE_QUELLE)
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
            _TEXT_STIL_EIGENER_KNOPF,
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
        _TEXT_STIL_FRAGE.format(name=name), "\n".join(zeilen_text)
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
        _TEXT_FIGUREN_ZUFALL_KNOPF,
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
            ) or "das Interview"
            tg.sende(
                chat_id,
                _TEXT_DUKTUS_LAEUFT.format(quelle=quelle, name=figur["name"]),
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
        (_TEXT_FIGUR_PASST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_PASST, name))),
        (_TEXT_FIGUR_INTERVIEW_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_INTERVIEW_MENU, name))),
        (_TEXT_FIGUR_DUKTUS_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_DUKTUS_MENU, name))),
        (_TEXT_FIGUR_ENTFERNEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_ENTFERNEN, name))),
        (_TEXT_EIGENE_KNOPF,
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
        tg.sende(chat_id, _TEXT_FIGUREN_KEINE)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", "Figurenliste steht", quelle="knopf",
    )
    leiste = [
        (_TEXT_WIR_ZUERST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_WIR_ZUERST, str(PHASE_SETTING)))),
        (_TEXT_SCHLAG_VOR_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHLAG_VOR, str(PHASE_SETTING)))),
    ]
    # Genau hier startete bisher die Figur-fuer-Figur-Schleife mit einem
    # Modellaufruf je Figur (06.09.2026, gemessen: 12 Laeufe, 718 s, und
    # trotzdem fuenf Figuren ohne Quelle). Der Knopf daneben erledigt die
    # Zuordnung in einem Druck, ohne Modell.
    zufall = _zufallsknopf(conn, chat_id)
    if zufall is not None:
        leiste.append(zufall)
    message_id = _sende_knoepfe(conn, tg, chat_id, _TEXT_ZUR_GESCHICHTE, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return False


def _biete_interviews(conn, tg, chat_id: int, name: str) -> str:
    """Ein Knopf je vorhandenem Interview -- die Auswahl fuer "Anderes
    Interview". Ohne Interviews gibt es nichts zu waehlen."""
    from interview_theater import aufnahme as aufnahme_modul
    from interview_theater import kontext

    koepfe = aufnahme_modul.interviews(conn, chat_id)
    if not koepfe:
        tg.sende(chat_id, _TEXT_KEIN_INTERVIEW)
        return _TEXT_KEIN_INTERVIEW
    leiste = [
        (
            kontext.interviewbezeichnung(conn, chat_id, kopf["id"]),
            _daten(repo.lege_knopf_an(
                conn, chat_id, ART_FIGUR_INTERVIEW, f"{name}{TRENNER}{kopf['id']}"
            )),
        )
        for kopf in koepfe
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, _TEXT_FIGUR_INTERVIEW_FRAGE.format(name=name), leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return "Interview waehlen"

#: Was je Zielphase erledigt ist -- der halbe Satz vor "Weiter zu ...".
#: Kurz und konkret, damit die Gruppe sieht, WORAUF sich das Angebot stuetzt,
#: ohne dass der Bot den Arbeitsstand nacherzaehlt.
_ERLEDIGT_FUER = {
    2: "Eure Begriffe",
    3: "Eure Fragen",
    4: "Die Interviews sind ausgewertet und",
    5: "Setting, Figuren und Geschichte",
    6: "Geschichte und Szenenfolge",
    7: "Alle Szenentexte",
}


def biete_phase_proaktiv(conn, tg, chat_id: int) -> bool:
    """Die eigene, kurze Nachricht "<Was steht>. Weiter zu <Phase>?" -- genau
    einmal je Stufe, sofort wenn die Voraussetzungen gespeichert sind.

    Liefert ``True``, wenn eine Nachricht rausging.

    **Warum eine eigene Nachricht.** Bis zum 06.09.2026 stand das Angebot nur
    als Prompt-Hinweis (``kontext._baue_phasenhinweis``) und als Knopf am Ende
    einer Gespraechsantwort. Am Testabend wurde keiner der neun angebotenen
    Phasenknoepfe gedrueckt: das Angebot ging im Text unter, und der Bot
    redete danach weiter ueber die alte Phase. Jetzt steht es allein da, mit
    zwei Knoepfen und ohne Fliesstext drumherum.

    **Genau einmal.** Der Merkposten ist derselbe wie fuer den Prompt-Hinweis
    (``phasen.offenes_angebot`` / ``merke_angebot``,
    ``arbeitsstand.phase_angeboten``) -- deshalb verschluckt diese Nachricht
    den Prompt-Hinweis und umgekehrt: es gibt EIN Angebot je Stufe, nicht
    zwei aus zwei Kanaelen. Sagt die Gruppe "Noch nicht", bleibt es still,
    bis die naechste Stufe erreichbar wird.

    Deterministisch, kein Modellaufruf (Zusage 2)."""
    stufe = phasen.offenes_angebot(conn, chat_id)
    if stufe is None:
        return False
    phasen.merke_angebot(conn, chat_id, stufe)
    weiter_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(stufe))
    noch_nicht_id = repo.lege_knopf_an(conn, chat_id, ART_NOCH_NICHT, str(stufe))
    leiste = [
        (f"Weiter zu {phasen.knopfbezeichnung(stufe)}", _daten(weiter_id)),
        (_TEXT_PHASE_NOCH_NICHT_KNOPF, _daten(noch_nicht_id)),
    ]
    text = _abschlusstext(conn, chat_id, stufe)
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return True


def _abschlusstext(conn, chat_id: int, stufe: int) -> str:
    """Die Abschlussnachricht der GERADE FERTIGEN Phase plus die Frage nach
    der naechsten (06.09.2026, Birk) -- eine Nachricht, nicht zwei.

    Welche Phase fertig ist, steht nicht in ``stufe``: das ist die Zielphase.
    Fertig ist die, in der die Gruppe gerade steht (``phasen.aktuelle``) --
    und wenn die schon ueber dem Ziel liegt (Rueckkehr aus einer hoeheren
    Phase), gibt es nichts abzuschliessen, dann bleibt es beim alten,
    kurzen Angebot."""
    from interview_theater import phasentexte

    jetzige = phasen.aktuelle(conn, chat_id)
    frage = _TEXT_PHASE_WEITER.format(phase=phasen.knopfbezeichnung(stufe))
    if jetzige >= stufe:
        return _TEXT_PHASE_ANGEBOT.format(
            erledigt=_ERLEDIGT_FUER.get(stufe, "Alles Noetige"),
            phase=phasen.knopfbezeichnung(stufe),
        )
    return f"{phasentexte.abschluss(conn, chat_id, jetzige)}\n\n{frage}"


def biete_proaktiv(conn, tg, chat_id: int, phase: int, vorspann: str | None = None) -> None:
    """Die **offene Frage** beim Eintritt in eine Phase.

    Bis zum 06.09.2026 standen darunter zwei Einstiegsknoepfe -- "Ja, wir
    zuerst" und "Schlag du vor". Sie sind weg (Birk, 11:10): unter einer
    OFFENEN FRAGE gibt es keine Knoepfe, weil dahinter nichts Fixes zu
    speichern ist. Der Bot fragt, die Gruppe antwortet in Sprache; sagt sie
    ausdruecklich "schlag du vor", erkennt das der Erkenner
    (``ART_SCHLAG_VOR`` bleibt als Knopf-Art fuer die Wege bestehen, die ihn
    weiterhin auslegen).

    Deterministischer Systemtext, kein Modellaufruf. ``vorspann`` ist die
    Eintrittsnachricht der Phase (``phasentexte.eintritt``): Kopfzeile,
    Einleitung, Checkliste -- in DERSELBEN Nachricht wie die Frage."""
    message_id = tg.sende(chat_id, _mit_vorspann(vorspann, _TEXT_PROAKTIV))
    repo.merke_nachricht(
        conn, chat_id, message_id, None, 1, "text",
        _mit_vorspann(vorspann, _TEXT_PROAKTIV), repo._jetzt(),
    )


def _mit_vorspann(vorspann: str | None, text: str) -> str:
    """Haengt einen Text unter die Eintrittsnachricht -- oder gibt ihn allein
    zurueck, wenn es keine gibt."""
    return f"{vorspann}\n\n{text}" if vorspann else text


def eintritt_in_phase(conn, tg, klm, e, chat_id: int, nummer: int) -> None:
    """Was beim Eintritt in eine Phase passiert -- fuer ALLE sieben gleich
    aufgebaut (06.09.2026, Birk).

    Eine deterministische Nachricht (``phasentexte.eintritt``: Kopfzeile
    "▶️ Phase N von 7 · Name", zwei bis vier Saetze Einleitung, die
    Parameter-Checkliste aus dem Arbeitsstand) und darunter die Knoepfe, die
    zum Einstieg DIESER Phase gehoeren. Neu erfunden wird dabei nichts: es
    sind dieselben Wege wie bisher -- die Eintritt-Frage mit "Ja, wir
    zuerst · Schlag du vor", in Phase 3 der Leitfaden, in 5 die Schaerfung,
    in 7 die Szenenfolge mit der Pruefung des Stuecks.

    **Kein Modellaufruf** (Zusage 2): alles kommt aus der Datenbank, und was
    ein Modell braucht (Schaerfung), geht in einen eigenen Thread.

    Ein Aufrufweg fuer alle vier Eintrittswege -- Knopf "Weiter zu ...",
    ``/phase N``, Erkenner-art ``phase_setzen`` und die proaktive
    Phasenmeldung: die Gruppe soll denselben Rahmen sehen, egal wie sie
    hergekommen ist."""
    from interview_theater import phasentexte

    kopf = phasentexte.eintritt(conn, chat_id, nummer)
    if nummer == PHASE_INTERVIEWS:
        # Der Schritt in die Interviews ist der Moment, in dem die Gruppe
        # den Leitfaden braucht -- gleich geht sie damit auf fremde
        # Menschen zu. Einmal ungefragt (``sende_einmal``), danach nur
        # noch ueber den Knopf: deterministisch, kein Modellaufruf.
        from interview_theater import leitfaden

        biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)
        leitfaden.sende_einmal(conn, tg, chat_id)
    elif nummer == PHASE_STUECKPRUEFUNG:
        # Die Schaerfung des Stuecks (06.09.2026, Birk): das komplette
        # Textbuch geht EINMAL beim Eintritt an den Stueck-Judge, im Thread
        # (Zusage 2: kein Modellaufruf in diesem Handler). Bis der Befund da
        # ist, steht die Szenenfolge mit Status und den Knoepfen "Szene N
        # ansehen" / "Textbuch als Datei" -- alles aus der Datenbank.
        tg.sende(chat_id, kopf)
        biete_durchlauf(conn, tg, chat_id, e)
        starte_stueckpruefung(conn, tg, klm, e, chat_id)
    elif nummer == PHASE_SCHAERFUNG:
        # Die Schaerfung fragt nicht nach Ideen: sie legt die Geschichte
        # neben die Interviews. Das Mapping laeuft automatisch beim
        # Eintritt, im Thread (Zusage 2).
        tg.sende(chat_id, kopf)
        starte_schaerfung(conn, tg, klm, e, chat_id)
    else:
        # Beim Eintritt in eine Phase fragt der Bot zuerst die Gruppe,
        # statt sofort vorzuschlagen (Zusage: proaktiv, aber nicht
        # vorlaut).
        biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)
        if nummer == PHASE_SZENEN:
            # **Die USA-Frage steht beim EINTRITT** (06.09.2026, Birk
            # 12:25), als eigene Nachricht direkt nach der Einleitung und
            # VOR dem ersten Prosa-Lauf. Bis dahin kam sie mitten aus dem
            # Szenenlauf heraus, wenn die Gruppe schon wartete -- und der
            # Lauf brach dafuer ab. Einmal je Gruppe: steht die Antwort
            # oder wurde schon gefragt, passiert nichts.
            from interview_theater import szene_claude

            if szene_claude.angebot_faellig(e, conn, chat_id):
                from interview_theater import szene as szene_modul

                repo.merke_szene_usa_angeboten(conn, chat_id)
                tg.sende(chat_id, szene_modul._TEXT_ANGEBOT_USA)
                biete_szene_usa(conn, tg, chat_id)
            else:
                # Die Frage ist beantwortet (oder es gibt kein US-Modell):
                # dann steht hier gleich der Knopf, aus dem der Lauf startet.
                biete_kurzgeschichte(conn, tg, chat_id, _TEXT_KURZGESCHICHTE_BEREIT)


def _werte_alle_aus(conn, tg, klm, e, chat_id: int) -> str:
    """Wertet ALLE beendeten, noch nicht verdichteten Interviews aus --
    nacheinander, in einem eigenen Thread (Zusage 2: kein Modellaufruf im
    Handler selbst).

    Nacheinander und nicht parallel: Infomaniak drosselt Parallelitaet mit
    429/5xx statt mit einer Warteschlange (AGENTS.md, Falle 8). Jede fertige
    Verdichtung geht von ``aufnahme._interview_abschliessen`` aus in den
    Chat, die Gruppe sieht also den Fortschritt."""
    import threading

    from interview_theater import aufnahme

    offen = aufnahme.unausgewertete_interviews(conn, chat_id)
    if not offen:
        tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_NICHTS)
        return _TEXT_AUSWERTEN_ALLE_NICHTS
    if klm is None:
        log.error("Auswerten-alle ohne Sprachmodell, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
        return _TEXT_AUSWERTEN_UNMOEGLICH

    ids = [kopf["id"] for kopf in offen]
    tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_LAEUFT)

    def _lauf() -> None:
        for kopf_id in ids:
            try:
                aufnahme._auswerten(conn, tg, klm, e, kopf_id)
            except Exception:
                log.exception("Auswertung fehlgeschlagen, aufnahme_id=%s", kopf_id)

    threading.Thread(target=_lauf, daemon=True).start()
    return _TEXT_AUSWERTEN_ALLE_LAEUFT


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
        return "Laeuft schon"
    return "Geschichte laeuft"


def _wirkung_geschichte_passt(conn, d: Druck) -> str:
    d.tg.sende(d.chat_id, _TEXT_GESCHICHTE_PASST)
    biete_phase_proaktiv(conn, d.tg, d.chat_id)
    return "Passt"


def _wirkung_geschichte_anders(conn, d: Druck) -> str:
    """Speichert nichts: die naechste Nachricht der Gruppe ist die Regie-Notiz.
    ``ablauf.antworte`` greift sie ueber ``nimm_geschichte_notiz`` auf und
    startet damit den naechsten Lauf -- dieselbe Bauart wie
    ``szenenfolge.nimm_regienotiz`` fuer die einzelne Szene."""
    erwarte_geschichte_notiz(d.chat_id)
    d.tg.sende(d.chat_id, _TEXT_GESCHICHTE_ANDERS)
    return "Was soll anders sein?"


def _wirkung_geschichte_neu(conn, d: Druck) -> str:
    """"Ganz neu" ist eine vollstaendige Aussage: kein Rueckfragen, der Lauf
    startet sofort und ohne Notiz."""
    from interview_theater import kurzgeschichte

    _geschichte_notiz_erwartet.discard(d.chat_id)
    if kurzgeschichte.starte(conn, d.tg, d.klm, d.e, d.chat_id, None) is None:
        return "Laeuft schon"
    return "Geschichte laeuft"


def _wirkung_geschichte_speichern(conn, d: Druck) -> str:
    return _speichere_geschichte(conn, d.tg, d.klm, d.e, d.chat_id, d.wert)


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
        d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_STELLE_UNBEKANNT)
        return _TEXT_SCHAERFUNG_STELLE_UNBEKANNT
    d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_STELLE_UEBERNOMMEN.format(ziel=ziel))
    biete_schaerfung(conn, d.tg, d.chat_id)
    return f"Uebernommen: {ziel}"


def _wirkung_schaerfung_keine(conn, d: Druck) -> str:
    from interview_theater import schaerfung as schaerfung_modul

    ids = [t.strip() for t in d.wert.split(TRENNER) if t.strip().isdigit()]
    schaerfung_modul.verwirf_stellen(conn, [int(t) for t in ids])
    d.tg.sende(d.chat_id, _TEXT_SCHAERFUNG_VERWORFEN)
    biete_schaerfung(conn, d.tg, d.chat_id)
    return _TEXT_SCHAERFUNG_VERWORFEN


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
    message_id = _sende_knoepfe(
        conn, d.tg, d.chat_id, _TEXT_FIGUREN_NAMEN_FRAGE, leiste
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


def _wirkung_figur_stil(conn, d: Druck) -> str:
    """Der gewaehlte Sprachstil (06.09.2026, Birk 12:20): er schreibt
    ``figur.sprachstil`` und -- wenn der Stil aus einem Interview kommt --
    zusaetzlich ``quelle_aufnahme_id``. Additiv: das Sprachprofil aus einem
    frueheren Lauf bleibt stehen."""
    name, _, rest = d.wert.partition(TRENNER)
    roh_id, _, stil = rest.partition(TRENNER)
    figur = repo.hole_figur(conn, d.chat_id, name)
    if figur is None or not stil.strip():
        d.tg.sende(d.chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    repo.setze_figur_sprachstil(conn, figur["id"], stil.strip())
    if roh_id.strip().isdigit():
        repo.setze_figur_quelle(conn, figur["id"], int(roh_id))
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        f"Sprachstil {name}: {stil.strip()}", quelle="knopf",
    )
    d.tg.sende(d.chat_id, _TEXT_STIL_GESPEICHERT.format(name=name))
    # Sofort weiter: naechste Figur, sonst die Geschichte.
    if not stelle_stil_vor(conn, d.tg, d.klm, d.e, d.chat_id):
        _schliesse_figuren_ab(conn, d.tg, d.chat_id)
    return "Stil uebernommen"


def _wirkung_figuren_zufall(conn, d: Druck) -> str:
    """Ein Druck statt zwoelf Modellaufrufen (06.09.2026, Analyse Abschnitt 1).
    Reine DB-Operation, keine Sprachstile, bestehende Zuordnungen bleiben
    unangetastet."""
    if not _interviewkoepfe(conn, d.chat_id):
        d.tg.sende(d.chat_id, _TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW)
        return _TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW
    anzahl, interviews = ordne_figuren_zufaellig_zu(conn, d.chat_id)
    if not anzahl:
        d.tg.sende(d.chat_id, _TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN)
        return _TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN
    meldung = _TEXT_FIGUREN_ZUFALL_FERTIG.format(
        figuren=anzahl, interviews=interviews
    )
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        f"Interviews zufaellig zugeordnet: {anzahl} Figuren auf "
        f"{interviews} Interviews",
        quelle="knopf",
    )
    d.tg.sende(d.chat_id, meldung)
    return f"Zugeordnet: {anzahl}"


def _wirkung_figur_stil_frei(conn, d: Druck) -> str:
    """Speichert nichts (Knopfregel: nur was fix ist). Der naechste Beitrag der
    Gruppe ist der Stil, und der Erkenner traegt ihn ein."""
    repo.setze_arbeitsstand(conn, d.chat_id, "figur_aktuell", d.wert)
    d.tg.sende(d.chat_id, _TEXT_STIL_EIGENER)
    return "Erzaehlt"


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
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    if repo.hole_aufnahme(conn, kennung) is None:
        d.tg.sende(d.chat_id, _TEXT_OHNE_KNOPF_UNBEKANNT)
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    kopf_id = aufnahme.nimm_als_interview(conn, d.tg, d.chat_id, kennung)
    kopf = repo.hole_aufnahme(conn, kopf_id) if kopf_id else None
    name = (kopf["name"] if kopf else None) or "Das Interview"
    biete_interview_ohne_knopf_weiter(
        conn, d.tg, d.chat_id,
        f"{name} steht. {aufnahme._TEXT_INTERVIEW_OHNE_KNOPF_WEITER}",
        kopf_id,
    )
    return f"{name} angelegt"


def _wirkung_ohne_knopf_nein(conn, d: Druck) -> str:
    """"Nein, das war ein Beitrag": der nachgeholte Gespraechszug laeuft in
    einem eigenen Thread."""
    from interview_theater import aufnahme

    kennung = _ohne_knopf_kennung(d)
    if kennung is None:
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    if not aufnahme.nimm_als_beitrag(conn, d.tg, d.klm, d.e, d.chat_id, kennung):
        d.tg.sende(d.chat_id, _TEXT_OHNE_KNOPF_UNBEKANNT)
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    d.tg.sende(d.chat_id, aufnahme._TEXT_INTERVIEW_OHNE_KNOPF_NEIN)
    return "Als Beitrag genommen"


def _wirkung_ohne_knopf_weiter(conn, d: Druck) -> str:
    """Nichts zu tun: der Modus ist an, der Kopf offen. Die Tastatur ist nach
    ``behandle`` weg, das ist die Rueckmeldung."""
    if _ohne_knopf_kennung(d) is None:
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    d.tg.sende(d.chat_id, _TEXT_OHNE_KNOPF_WEITER)
    return "Ich hoere weiter zu"


def _wirkung_ohne_knopf_fertig(conn, d: Druck) -> str:
    """Wortgleich derselbe Weg wie "Interview beenden": beenden, dann
    verdichten im eigenen Thread."""
    from interview_theater import aufnahme

    kennung = _ohne_knopf_kennung(d)
    if kennung is None:
        return _TEXT_OHNE_KNOPF_UNBEKANNT
    kopf_id = aufnahme.beende_interview(conn, d.chat_id)
    if kopf_id is None:
        kopf_id = kennung
    if d.klm is not None:
        aufnahme.starte_abschluss(conn, d.tg, d.klm, d.e, kopf_id)
    return "Interview beendet"


# --- Kernthema, Aufnahme, Phase, Auswertung, Szenenform --------------------


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
    # Jetzt, wo die Form bestaetigt ist, kommt die STILFRAGE (06.09.2026,
    # Birk 12:50) -- und erst danach die Schreibfrage. Beides zusammen
    # entscheidet, wie der Text klingt; die Reihenfolge ist Form, Stil,
    # schreiben.
    biete_szenenstil(conn, d.tg, d.chat_id, nummer)
    return f"Szene {nummer}: {form}"


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
            f"Szene {nummer}, Stil: {stile.beschriftung(gewaehlt)} "
            f"(Vorlage: {stile.herkunft(gewaehlt)}).",
        )
    else:
        d.tg.sende(
            d.chat_id, f"Szene {nummer}: ohne Stilvorlage, es bleibt bei der Form."
        )
    repo.schreibe_journal(
        conn, d.chat_id, "entschieden",
        f"Szene {nummer} Stil: {stile.beschriftung(gewaehlt) if gewaehlt else 'ohne'}",
        quelle="knopf",
    )
    ziel = _szene_mit_nummer(conn, d.chat_id, nummer)
    if ziel is not None:
        biete_szene(conn, d.tg, d.chat_id, ziel)
    return f"Szene {nummer}: Stil {gewaehlt or 'ohne'}"


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
        biete_kurzgeschichte(conn, d.tg, d.chat_id, _TEXT_KURZGESCHICHTE_BEREIT)
    elif auftrag:
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
    ART_GESCHICHTE_SCHREIBEN: _wirkung_geschichte_schreiben,
    ART_GESCHICHTE_PASST: _wirkung_geschichte_passt,
    ART_GESCHICHTE_ANDERS: _wirkung_geschichte_anders,
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
        _beantworte(tg, druck["callback_query_id"], _TEXT_UNBEKANNT)
        return True

    chat_id = knopf["chat_id"]
    if not repo.beanspruche_knopf(conn, knopf_id):
        # Zweiter Druck: beantworten, aber nichts wiederholen (AGENTS.md).
        _beantworte(tg, druck["callback_query_id"], _TEXT_SCHON_BENUTZT)
        _entferne_tastatur(tg, chat_id, druck["message_id"])
        return True

    meldung = _wirke(conn, tg, klm, e, knopf, chat_id)
    _beantworte(tg, druck["callback_query_id"], meldung)
    _entferne_tastatur(tg, chat_id, druck["message_id"])
    return True

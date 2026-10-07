"""Die Ueberarbeitung in Padua (Padua Phasen TEIL 2, 03.10.2026): Phase 6
(Rewrite) und -- ab Task 9 -- Phase 7 (Stage Version) als Zustandsmaschine.

Phase 6, Birk: "zuerst das Ganze, dann Szene fuer Szene".

1. **Das Ganze.** Beim Eintritt wird die schon vorhandene Prosa aus Phase 5
   GEPRUEFT (``prueflauf.starte_geschichte``), nicht neu geschrieben. Danach
   steht ein Hinweis mit "Yes, save" / "No, change it again" / "Shorter".
   Rueckmeldung zum Ganzen ueberarbeitet die ganze Geschichte
   (``ueberarbeite`` ohne Nummer). "Yes, save" setzt
   ``arbeitsstand.gesamttext_fixiert_am``.
2. **Szene fuer Szene.** Danach je Szene ein Prueflauf mit Hinweis; "Yes,
   save" setzt ``szene.ueberarbeitung_bestaetigt_am`` und geht zur
   naechsten. Nach der letzten: EINE Abschlussnachricht und der
   automatische Sprung nach Phase 7 -- dieselbe ausdruecklich von Birk
   gewuenschte Ausnahme von "Datenstand ist nicht Absicht" wie am Ende von
   Phase 5 (``knoepfe.wirkung._wirkung_entwurf_szene_passt``): die Gruppe
   HAT gedrueckt.

Phase 7 (Stage Version, Task 9), ein Schrittweg ``weiter_7``:

1. **Formen** -- EINE Nachricht mit der ganzen Szenenliste und "Which form
   for each number?" (``sende_formwahl``); keine Knoepfe, kein Vorschlag.
   Die Antwort im Chat setzt der Erkenner (Task 10).
2. **Sprechweisen** -- ``sprechweise.starte`` (Schema-Aufruf nur fuer Figuren
   ohne Stil), EINE Nachricht, "Yes, save" setzt
   ``arbeitsstand.sprechweisen_fixiert_am``.
3. **Szene fuer Szene** -- ``szene.starte`` mit ``_AUFTRAG_BUEHNE`` (ueber den
   Prueflauf, endet im Hinweis); "Yes, save" setzt ``szene.fertig_am``.
4. **Schluss** -- ``starte_schluss``: Prueflauf uebers ganze Textbuch, dann
   die Stueckpruefung, dann "The script is complete". Nur vom Abnahmeweg,
   nie vom Eintritt.

Kein SQL (alles ueber ``repo``), kein Modellaufruf hier -- was ein Modell
braucht, laeuft in den Threads von ``prueflauf``/``szene``/
``kurzgeschichte`` (Zusage 2: die Funktionen werden aus Knopf-Handlern
gerufen). Alles ist an ``workshop.ueberarbeitung_aktiv()`` gebunden; ohne
den Schalter ruft niemand dieses Modul.
"""

from __future__ import annotations

import logging
import re
import threading

from interview_theater import phasen, repo, workshop

log = logging.getLogger(__name__)

#: Nach "Yes, save" auf dem Ganzen.
_TEXT_GESAMT_GESPEICHERT = (
    "Gespeichert. Jetzt gehen wir Szene fuer Szene: Szene 1 von {gesamt}."
)
#: Die EINE Abschlussnachricht von Phase 6.
_TEXT_6_FERTIG = (
    "Ueberarbeitung fertig: alle {gesamt} Szenen sind gespeichert. "
    "Weiter zur Buehnenfassung."
)
#: "Yes, save", waehrend noch ein Lauf geht -- oder der naechste Schritt
#: konnte nicht anlaufen (Fix-Runde 1). Nichts wird gespeichert.
_TEXT_LAEUFT_NOCH = (
    "Eine Ueberarbeitung laeuft noch -- ich zeige euch das Ergebnis, "
    "dann koennt ihr es speichern."
)
#: Eine Revisionsnotiz, waehrend ein Szenen-/Geschichtenlauf schon haelt (B3,
#: 07.10.2026, simulation/berichte/p57-2026-10-07.md): anders als
#: ``_TEXT_LAEUFT_NOCH`` eine ehrliche Zusage -- die Notiz ist vorgemerkt
#: (``merke_notiz_wenn_besetzt``) und laeuft automatisch, sobald die Sperre
#: frei wird (``nach_lauf_frei``), statt stillschweigend zu verfallen.
_TEXT_NOTIZ_WARTET = (
    "Eine Ueberarbeitung laeuft noch -- ich mache diese Aenderung direkt "
    "danach. Wenn ich mich nicht melde, schreibt es noch einmal."
)
#: Wiedereintritt in Phase 6, wenn schon alles abgenommen ist: kein
#: automatischer Sprung, nur das Angebot (Fix-Runde 1).
_TEXT_6_SCHON_FERTIG = (
    "Alle Szenen der Ueberarbeitung sind gespeichert. Sagt mir, was ihr "
    "aendern wollt, oder geht weiter zur Buehnenfassung."
)
#: Eine Rueckmeldung ohne erkennbares Ziel (Fix-Runde 1).
_TEXT_KEIN_ZIEL = (
    "Ich konnte nicht erkennen, welchen Text ihr aendern wollt -- tippt "
    "\"Nein, nochmal aendern\" unter dem Text, den ihr meint."
)
#: Toast fuer ein veraltetes "Yes, save" auf dem schon fixierten Ganzen.
_ANTWORT_SCHON_GESPEICHERT = "Schon gespeichert"
#: "Yes, save" (Knopf oder Chat), aber der Stand hat sich seit der Anzeige
#: geaendert -- ein Rewrite ist dazwischen fertig geworden (Birk-Entscheidung
#: 07.10.2026, simulation/berichte/p57-2026-10-07.md: `gesamttext_fixiert_am`
#: blieb NULL, weil die Gruppe nie wieder zum laengst veralteten Hinweis
#: zurueckfand). Die Bestaetigung gilt nur dem Text, den die Gruppe beim
#: Druck gesehen hat -- nie stillschweigend der neuen Fassung. Nichts wird
#: gespeichert.
_TEXT_NEUE_FASSUNG_BEREIT = (
    "Waehrend ihr das gelesen habt, ist eine neue Fassung fertig geworden -- "
    "schaut sie euch an und tippt dann noch einmal \"Yes, save\"."
)
#: "Yes, save" fuer eine Szene, die gerade nicht dran ist -- ein veralteter
#: Knopf (Abschlussreview, Fix 1). Nichts wird gespeichert.
_TEXT_NICHT_DRAN = (
    "Diese Szene ist gerade nicht dran -- gespeichert habe ich nichts."
)
#: Toast, wenn statt einer Abnahme die aktuelle Szene (neu) uebertragen wird
#: (Abschlussreview, Fix-Runde 2).
_ANTWORT_WIRD_UEBERTRAGEN = "Szene {nummer} wird neu uebertragen"

# --- Phase 7 (Stage Version), Task 9 --------------------------------------

#: 7.1 Formwahl: EINE Nachricht, Kopf, je Szene eine Zeile, die Frage.
_TEXT_FORMWAHL_KOPF = "Hier sind eure Szenen:"
_ZEILE_FORMWAHL = "{nummer}. {titel} -- {satz}"
_ZEILE_FORMWAHL_OHNE_SATZ = "{nummer}. {titel}"
_TEXT_FORMWAHL_FRAGE = (
    "Welche Form fuer welche Nummer? Zum Beispiel: 1 Chor, 2 Dialog, 3 Rap. "
    "Formen: {formen}."
)
#: Der Auftrag an den Szenenlauf (geht ueber den Prueflauf).
_AUFTRAG_BUEHNE = "SZENE {nummer}: uebertrage diese Szene in ihre Form."
#: 7.2 nach "Yes, save" auf den Sprechweisen.
_TEXT_SPRECHWEISEN_GESPEICHERT = (
    "Gespeichert. Jetzt Szene fuer Szene in die Buehnenfassung: Szene 1 von "
    "{gesamt}."
)
#: Die letzte Zeile der Phase -- NACH der Stueckpruefung.
_TEXT_TEXTBUCH_FERTIG = "Das Textbuch ist fertig. Lest es im Script-Tab."
#: Wiedereintritt in Phase 7, wenn alles fertig ist: kein neuer Pruefdurchgang
#: von selbst (der gehoert dem Abnahmeweg), nur der Verweis.
_TEXT_7_SCHON_FERTIG = (
    "Euer Textbuch ist fertig. Lest es im Script-Tab, oder sagt mir, was "
    "ihr aendern wollt."
)
#: Hoechstens so viele Zeichen je Satz in der Formwahl.
FORMWAHL_SATZ_MAX = 160

# --- Chat wirkt, wo Knoepfe wirken (Task 10) ------------------------------

#: Eine Zeile der Notiert-Meldung je gesetzter Form (``formen_setzen``).
_ZEILE_FORM_GESETZT = "Szene {nummer}: {form}"
#: Dieselbe Zeile, wenn die Szene schon uebertragen war und ihre Form
#: wechselt: der alte Buehnentext ist zurueckgenommen (Abschlussreview, Fix 4).
_ZEILE_FORM_NEU_UEBERTRAGEN = (
    "Szene {nummer}: {form} -- neue Form, die Szene wird neu uebertragen"
)
#: Nach einer Formwahl, die nicht alle Szenen trifft (Abschlussreview, Fix 4).
_TEXT_FORMEN_FEHLEN = "Noch ohne Form: Szene {nummern}. Welche Form sollen sie haben?"

PHASE_UEBERARBEITUNG = 6
PHASE_BUEHNE = 7


def aktiv() -> bool:
    """Laeuft die Ueberarbeitungs-Zustandsmaschine? Nur in Padua."""
    return workshop.ueberarbeitung_aktiv()


def _gesetzt(wert) -> bool:
    return bool((wert or "").strip())


def _stand(conn, chat_id: int, feld: str) -> bool:
    zeile = repo.hole_arbeitsstand(conn, chat_id)
    return bool(zeile is not None and feld in zeile.keys() and _gesetzt(zeile[feld]))


def _szenen(conn, chat_id: int) -> list:
    return sorted(
        (s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] is not None),
        key=lambda s: s["nummer"],
    )


def szenennummern(conn, chat_id: int) -> list[int]:
    """Die Szenennummern der Gruppe, aufsteigend, ohne ``None``."""
    return [s["nummer"] for s in _szenen(conn, chat_id)]


def gesamttext_fixiert(conn, chat_id: int) -> bool:
    return _stand(conn, chat_id, "gesamttext_fixiert_am")


def aktuelle_szene(conn, chat_id: int) -> int | None:
    """Die Szene, an der die Gruppe gerade arbeitet -- oder ``None``.

    Phase 6: die erste Szene ohne ``ueberarbeitung_bestaetigt_am``, aber erst,
    wenn der Gesamttext fixiert ist; vorher ist das Ganze das Objekt.
    Phase 7: die erste Szene ohne ``fertig_am``, sobald die Sprechweisen
    fixiert sind und jede Szene eine Form hat; sonst ``None``."""
    phase = phasen.aktuelle(conn, chat_id)
    szenen = _szenen(conn, chat_id)
    if phase == PHASE_UEBERARBEITUNG:
        if not gesamttext_fixiert(conn, chat_id):
            return None
        for s in szenen:
            if not _gesetzt(s["ueberarbeitung_bestaetigt_am"]):
                return s["nummer"]
        return None
    if phase == PHASE_BUEHNE:
        if not _stand(conn, chat_id, "sprechweisen_fixiert_am"):
            return None
        if not szenen or any(not _gesetzt(s["form"]) for s in szenen):
            return None
        for s in szenen:
            if not _gesetzt(s["fertig_am"]):
                return s["nummer"]
        return None
    return None


def _hat_prosa(conn, chat_id: int) -> bool:
    return any(_gesetzt(s["prosa"]) for s in _szenen(conn, chat_id))


def laeuft(chat_id: int) -> bool:
    """Laeuft fuer diese Gruppe gerade ein Szenen- oder Geschichtenlauf
    (samt Prueflauf, der unter denselben Sperren laeuft)? Nur gelesen."""
    from interview_theater import kurzgeschichte, szene

    return (szene._sperre_fuer(chat_id).locked()
            or kurzgeschichte._sperre_fuer(chat_id).locked())


# ---------------------------------------------------------------------------
# Der angezeigte Stand (Birk-Entscheidung 07.10.2026, siehe
# _TEXT_NEUE_FASSUNG_BEREIT oben): ``laeuft()`` faengt nur den Fall "ein
# Rewrite haelt genau jetzt". Ist er zwischen Anzeige und Klick schon FERTIG
# geworden (Chat-"Yes, save" rennt gegen das Ende eines Laufs), waere
# ``laeuft()`` beim Klick schon wieder False -- und die Bestaetigung naehme
# stillschweigend die neue, nie gezeigte Fassung ab. Deshalb merkt jede
# Anzeige (``knoepfe.zeige_geprueft_geschichte``/``zeige_geprueft_szene``)
# einen Fingerabdruck (``szene.geaendert_am``, von ``aktualisiere_szene`` bei
# jeder neuen Fassung neu gesetzt), und jede Bestaetigung vergleicht ihn
# gegen den aktuellen Stand. In-memory wie ``_gemerkt``: ein Prozessneustart
# verliert nur die Momentaufnahme (dann wird nicht blockiert, siehe
# ``_stand_hat_sich_geaendert``), nie Inhalt.
# ---------------------------------------------------------------------------

#: Fingerabdruck des zuletzt angezeigten Stands je (chat_id, Ziel) -- Ziel wie
#: bei ``_gemerkt``: die Szenennummer, oder ``None`` fuer die ganze Geschichte.
_angezeigter_stand: dict[int, dict[int | None, str]] = {}


def _stempel_gesamt(conn, chat_id: int) -> str:
    return "|".join(f"{s['nummer']}:{s['geaendert_am'] or ''}"
                    for s in _szenen(conn, chat_id))


def _stempel_szene(conn, chat_id: int, nummer: int) -> str:
    zeile = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
    return (zeile["geaendert_am"] or "") if zeile is not None else ""


def _stempel(conn, chat_id: int, nummer: int | None) -> str:
    return (_stempel_gesamt(conn, chat_id) if nummer is None
            else _stempel_szene(conn, chat_id, nummer))


def merke_angezeigten_stand(conn, chat_id: int, nummer: int | None) -> None:
    """Merkt den Stand, der GERADE gezeigt wird -- nur eine Bestaetigung auf
    GENAU diesem Stand (oder ein neuerer, erneut gemerkter) wirkt."""
    stempel = _stempel(conn, chat_id, nummer)
    with _schutz:
        _angezeigter_stand.setdefault(chat_id, {})[nummer] = stempel


def _stand_hat_sich_geaendert(conn, chat_id: int, nummer: int | None) -> bool:
    """True: der Stand hat sich seit der letzten Anzeige dieses Ziels
    geaendert -- eine Bestaetigung darauf waere stillschweigend eine andere
    Fassung. Nichts gemerkt (z. B. nach einem Prozessneustart): nicht
    blockieren -- dieselbe Fail-open-Haltung wie ``vorgemerkte_notizen``."""
    with _schutz:
        alter_stempel = _angezeigter_stand.get(chat_id, {}).get(nummer)
    if alter_stempel is None:
        return False
    return _stempel(conn, chat_id, nummer) != alter_stempel


# ---------------------------------------------------------------------------
# Der Merkplatz einer Revisionsnotiz waehrend eines laufenden Laufs (B3,
# 07.10.2026). Dasselbe Prinzip wie ``vorschlagssperre`` (Merkplatz statt
# Verwerfen, hoechstens eine Notiz je Ziel, newest wins), aber ein eigenes
# Register: ``vorschlagssperre`` koppelt bewusst NUR Schaerfung und
# Szenenfolge, nicht den Szenen-/Prosalauf (siehe dort, "Was diese Sperre
# NICHT ist").
# ---------------------------------------------------------------------------

#: Schuetzt ``_gemerkt`` UND serialisiert gegen ``nach_lauf_frei`` -- siehe
#: ``merke_notiz_wenn_besetzt``.
_schutz = threading.Lock()

#: Ein Merkplatz je (chat_id, Ziel) -- Ziel ist die Szenennummer oder
#: ``None`` fuer "die ganze Geschichte bzw. die aktuelle Szene", genau wie
#: ``ueberarbeite`` selbst es versteht. Eine zweite Notiz zum selben Ziel
#: ersetzt die erste (newest wins): was die Gruppe gerade zuletzt gesagt
#: hat, ist aktueller als der erste Zwischenruf.
_gemerkt: dict[int, dict[int | None, str]] = {}


def merke_notiz_wenn_besetzt(chat_id: int, nummer: int | None, notiz: str) -> bool:
    """Prueft erneut (unter ``_schutz``), ob ``laeuft`` noch gilt, und merkt
    die Notiz ATOMAR mit derselben Pruefung vor -- sonst koennte die Notiz
    genau zwischen "laeuft noch" und "merken" verloren gehen, waehrend
    ``nach_lauf_frei`` (das denselben ``_schutz`` nimmt) in diesem Fenster
    schon leert (derselbe Race-Fund wie bei ``vorschlagssperre.
    nimm_oder_merke``, 30.09.2026).

    True: vorgemerkt, ``nach_lauf_frei`` holt sie nach. False: die Sperre war
    beim erneuten Pruefen schon frei -- der Aufrufer soll die Notiz SELBST
    sofort ausfuehren (``ueberarbeite``), statt sie fuer immer liegen zu
    lassen."""
    from interview_theater import kurzgeschichte, szene

    with _schutz:
        if not (szene._sperre_fuer(chat_id).locked()
                or kurzgeschichte._sperre_fuer(chat_id).locked()):
            return False
        _gemerkt.setdefault(chat_id, {})[nummer] = notiz
        return True


def vorgemerkte_notizen(chat_id: int) -> dict[int | None, str]:
    """Was gerade vorgemerkt ist -- fuer Tests und das Log."""
    with _schutz:
        return dict(_gemerkt.get(chat_id, {}))


def nach_lauf_frei(conn, tg, klm, e, chat_id: int) -> None:
    """Nach der Freigabe von ``szene``/``kurzgeschichte`` (ihr ``finally``,
    NACH ``sperre.release()``): holt hoechstens EINE vorgemerkte Notiz nach.
    Steht noch eine zweite auf dem Merkplatz, holt der Lauf, den diese Notiz
    ihrerseits anstoesst, sie am Ende seinerseits nach -- derselbe Weg
    (``szene.starte``/``kurzgeschichte.starte`` ruft diese Funktion wieder).

    Kein Modellaufruf hier selbst; ``ueberarbeite`` geht ueber die
    bestehenden Threads. Ein Fehler reisst die Freigabe des Aufrufers nicht
    mit -- er steht schon hinter deren ``finally``."""
    with _schutz:
        d = _gemerkt.get(chat_id)
        if not d:
            return
        nummer = next(iter(d))
        notiz = d.pop(nummer)
        if not d:
            _gemerkt.pop(chat_id, None)
    log.info("Vorgemerkte Ueberarbeitungsnotiz nachgeholt, chat_id=%s, nummer=%s",
             chat_id, nummer)
    try:
        ueberarbeite(conn, tg, klm, e, chat_id, notiz, nummer)
    except Exception:
        log.exception(
            "Nachgeholte Ueberarbeitungsnotiz fehlgeschlagen, chat_id=%s", chat_id)


def vergiss(chat_id: int) -> None:
    """Raeumt den Merkplatz UND den angezeigten Stand dieser Gruppe ab --
    fuer Tests (beides Prozessspeicher je ``chat_id``, siehe
    ``_angezeigter_stand``)."""
    with _schutz:
        _gemerkt.pop(chat_id, None)
        _angezeigter_stand.pop(chat_id, None)


def weiter_6(conn, tg, klm, e, chat_id: int, *,
             aus_eintritt: bool = False) -> threading.Thread | None:
    """Der EINE Schrittweg von Phase 6: was als naechstes dran ist.

    Liefert den angestossenen Thread (oder ``None``) -- fuer Tests; die
    Aufrufer brauchen ihn nicht. Konnte ein Prueflauf nicht anlaufen (Sperre
    belegt), bekommt die Gruppe ``_TEXT_LAEUFT_NOCH`` statt Stille.

    ``aus_eintritt`` (Eintritt in Phase 6, USA-Antwort): ist schon alles
    abgenommen, gibt es KEINEN automatischen Sprung nach Phase 7 -- der
    gehoert allein dem Abnahmeweg (``bestaetige_szene_6``). Stattdessen eine
    Zeile mit dem Knopf "Weiter zu Phase 7"; die Phase setzt die Gruppe."""
    from interview_theater import knoepfe, prueflauf

    if not _hat_prosa(conn, chat_id):
        # Rueckfall: es gibt noch keine Geschichte -- erst schreiben.
        knoepfe.biete_kurzgeschichte(
            conn, tg, chat_id, knoepfe.T._TEXT_KURZGESCHICHTE_BEREIT)
        return None
    if not gesamttext_fixiert(conn, chat_id):
        faden = prueflauf.starte_geschichte(
            conn, tg, klm, e, chat_id,
            danach=lambda b: knoepfe.zeige_geprueft_geschichte(
                conn, tg, e, chat_id, b),
        )
        if faden is None:
            _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return faden
    nummer = aktuelle_szene(conn, chat_id)
    if nummer is not None:
        faden = prueflauf.starte_szene(
            conn, tg, klm, e, chat_id, nummer,
            danach=lambda b: knoepfe.zeige_geprueft_szene(
                conn, tg, e, chat_id, nummer, b),
        )
        if faden is None:
            _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return faden
    if aus_eintritt:
        knoepfe.biete_phase(conn, tg, chat_id, T._TEXT_6_SCHON_FERTIG,
                            PHASE_BUEHNE)
        return None
    schliesse_6_ab(conn, tg, klm, e, chat_id)
    return None


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    message_id = tg.sende(chat_id, text)
    repo.merke_bot_zeile(conn, chat_id, message_id, e, text)


def _nicht_dran(conn, tg, e, chat_id: int) -> str:
    """Ein "Yes, save" fuer eine Szene, die nicht ``aktuelle_szene`` ist
    (Abschlussreview, Fix 1): ein veralteter Knopf -- etwa der aus Phase 6,
    nachdem die Gruppe schon in Phase 7 ist. Nichts wird gespeichert, keine
    Zustandsaenderung; eine Zeile statt Stille."""
    _sende(conn, tg, e, chat_id, T._TEXT_NICHT_DRAN)
    return T._TEXT_NICHT_DRAN


def _uebertrage_neu_falls_noetig(conn, tg, klm, e, chat_id: int) -> str | None:
    """Phase 7: steht die aktuelle Szene ohne Buehnentext da, braucht sie
    keine Abnahme, sondern eine (neue) Uebertragung -- ``weiter_7`` startet
    sie (``szene.starte``, eigener Thread; kein Modellaufruf hier).

    Der Fall (Abschlussreview, Fix-Runde 2): Szene 2 bekam eine neue Form,
    WAEHREND Szene 3 uebertragen wurde; ``_wende_formen_an`` nahm Szene 2s
    Text zurueck, aber der Lauf war besetzt. Danach zeigte das "Yes, save
    (3)" nur "nicht dran", und ein "passt" im Chat fand nichts abzunehmen
    -- Szene 2 wurde nie neu uebertragen. Liefert die Antwortzeile (Toast),
    oder ``None``, wenn nichts zu uebertragen ist oder ein Lauf geht."""
    if not aktiv() or phasen.aktuelle(conn, chat_id) != PHASE_BUEHNE:
        return None
    nummer = aktuelle_szene(conn, chat_id)
    if nummer is None or laeuft(chat_id):
        return None
    zeile = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
    if zeile is None or _gesetzt(zeile["volltext"]):
        return None
    weiter_7(conn, tg, klm, e, chat_id)
    return T._ANTWORT_WIRD_UEBERTRAGEN.format(nummer=nummer)


def bestaetige_gesamt(conn, tg, klm, e, chat_id: int) -> str:
    """"Yes, save" auf dem Ganzen: fixieren, ansagen, erste Szene pruefen.

    Laeuft noch ein Lauf (z. B. die Ueberarbeitung des Ganzen), wird NICHTS
    gespeichert -- sonst naehme ein veralteter Knopf eine alte Fassung ab.
    Ist der Lauf schon FERTIG, aber die Fassung hat sich seit der letzten
    Anzeige geaendert (``_stand_hat_sich_geaendert``), ebenfalls nicht --
    die Bestaetigung gilt nur dem gezeigten Stand."""
    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    if _stand_hat_sich_geaendert(conn, chat_id, None):
        _sende(conn, tg, e, chat_id, T._TEXT_NEUE_FASSUNG_BEREIT)
        return T._TEXT_NEUE_FASSUNG_BEREIT
    repo.setze_arbeitsstand(conn, chat_id, "gesamttext_fixiert_am", repo._jetzt())
    text = T._TEXT_GESAMT_GESPEICHERT.format(
        gesamt=len(szenennummern(conn, chat_id)))
    _sende(conn, tg, e, chat_id, text)
    weiter_6(conn, tg, klm, e, chat_id)
    return text


def bestaetige_szene_6(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" auf einer Szene in Phase 6: abnehmen, weiter.

    Dieselbe Wache wie ``bestaetige_gesamt``: ein zwischenzeitlich fertig
    gewordener Rewrite dieser Szene (seit der letzten Anzeige) blockiert die
    Abnahme, statt sie still auf die neue Fassung zu uebertragen."""
    from interview_theater import knoepfe

    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    if nummer != aktuelle_szene(conn, chat_id):
        return _nicht_dran(conn, tg, e, chat_id)
    ziel = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
    if ziel is None:
        tg.sende(chat_id, knoepfe.T._TEXT_SZENE_UNBEKANNT)
        return knoepfe.T._TEXT_SZENE_UNBEKANNT
    if _stand_hat_sich_geaendert(conn, chat_id, nummer):
        _sende(conn, tg, e, chat_id, T._TEXT_NEUE_FASSUNG_BEREIT)
        return T._TEXT_NEUE_FASSUNG_BEREIT
    repo.setze_szene_ueberarbeitung_bestaetigt(conn, ziel["id"])
    weiter_6(conn, tg, klm, e, chat_id)
    return knoepfe.T._ANTWORT_SZENE_STEHT.format(nummer=nummer)


def schliesse_6_ab(conn, tg, klm, e, chat_id: int) -> None:
    """EINE Abschlussnachricht, dann automatisch Phase 7."""
    from interview_theater import knoepfe

    _sende(conn, tg, e, chat_id, T._TEXT_6_FERTIG.format(
        gesamt=len(szenennummern(conn, chat_id))))
    phasen.setze(conn, chat_id, PHASE_BUEHNE, "ueberarbeitung",
                 notiz="alle Szenen ueberarbeitet")
    knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, PHASE_BUEHNE)


def ueberarbeite(conn, tg, klm, e, chat_id: int, notiz: str,
                 nummer: int | None = None):
    """Der EINE Weg fuer inhaltliche Rueckmeldung (Knopf-Notiz, Erkenner).

    In Phase 6 vor dem Fixieren und ohne Nummer: die ganze Geschichte, mit
    der bisherigen als Vorlage. Sonst eine Szene (die genannte oder die
    aktuelle), mit ``szene.ueberarbeitungsauftrag`` -- in der Prosa-Phase
    traegt der Auftrag ``BISHER_MARKER``. Beide Laeufe gehen ueber den
    Prueflauf und enden wieder im Hinweis mit Knoepfen."""
    from interview_theater import kurzgeschichte, szene

    if (phasen.aktuelle(conn, chat_id) == PHASE_UEBERARBEITUNG
            and not gesamttext_fixiert(conn, chat_id) and nummer is None):
        return kurzgeschichte.starte(conn, tg, klm, e, chat_id, notiz, vorlage=True)
    n = nummer if nummer is not None else aktuelle_szene(conn, chat_id)
    if n is None:
        # Kein Ziel (z. B. alles abgenommen): die Notiz nicht verschlucken.
        _sende(conn, tg, e, chat_id, T._TEXT_KEIN_ZIEL)
        return None
    return szene.starte(
        conn, tg, klm, e, chat_id,
        szene.ueberarbeitungsauftrag(conn, chat_id, n, notiz),
    )


# ---------------------------------------------------------------------------
# Phase 7 (Stage Version), Task 9
# ---------------------------------------------------------------------------


def formen_offen(conn, chat_id: int) -> list[int]:
    """Die Szenennummern ohne bestaetigte ``form``."""
    return [s["nummer"] for s in _szenen(conn, chat_id) if not _gesetzt(s["form"])]


def _erster_satz(text: str) -> str:
    """Der erste Satz, auf ``FORMWAHL_SATZ_MAX`` Zeichen gekappt."""
    text = " ".join((text or "").split())
    if not text:
        return ""
    treffer = re.search(r"(?<=[.!?])\s", text)
    satz = text[:treffer.start()] if treffer else text
    if len(satz) > FORMWAHL_SATZ_MAX:
        schnitt = satz.rfind(" ", 0, FORMWAHL_SATZ_MAX - 1)
        satz = satz[:schnitt if schnitt > 0 else FORMWAHL_SATZ_MAX - 1].rstrip() + "…"
    return satz


def sende_formwahl(conn, tg, e, chat_id: int) -> None:
    """EINE Nachricht mit der ganzen Szenenliste -- je Szene Titel und ein
    Satz -- und der Frage nach der Form je Nummer. Keine Knoepfe und kein
    Vorschlag (Birk 7.1): die Antwort kommt im Chat und wird vom Erkenner
    gespeichert (``formen_setzen``, Task 10). Als Bot-Zeile gemerkt, damit
    der Erkenner sie als ``vorlauf`` sieht."""
    from interview_theater import szene

    zeilen = [T._TEXT_FORMWAHL_KOPF]
    for s in _szenen(conn, chat_id):
        titel = (s["titel"] or "").strip() or szene.T._SZENE_MIT_NUMMER.format(
            nummer=s["nummer"])
        satz = _erster_satz(s["zusammenfassung"] or s["was_passiert"] or "")
        if satz:
            zeilen.append(T._ZEILE_FORMWAHL.format(
                nummer=s["nummer"], titel=titel, satz=satz))
        else:
            zeilen.append(T._ZEILE_FORMWAHL_OHNE_SATZ.format(
                nummer=s["nummer"], titel=titel))
    zeilen.append("")
    zeilen.append(T._TEXT_FORMWAHL_FRAGE.format(
        formen=", ".join(workshop.form_anzeige())))
    _sende(conn, tg, e, chat_id, "\n".join(zeilen))


def sprechweisen_fixiert(conn, chat_id: int) -> bool:
    return _stand(conn, chat_id, "sprechweisen_fixiert_am")


def _fertigzeile(conn, e, chat_id: int, text: str) -> str:
    """``text`` und, in Telegram mit Basis-URL, der Link aufs Script. Im
    Web-Kanal (und ohne Basis-URL) sagt ``text`` schon alles -- der Tab-Satz
    von ``skript_verweis`` waere dort nur eine Wiederholung."""
    from interview_theater import knoepfe

    verweis = knoepfe.skript_verweis(conn, e, chat_id)
    if verweis and verweis != knoepfe.T._TEXT_SKRIPT_TAB:
        return f"{text}\n{verweis}"
    return text


def schluss_gelaufen(conn, chat_id: int) -> bool:
    """Hat die Schlusspruefung von Phase 7 schon einmal ihr Protokoll
    geschrieben (``prueflauf``-Zeile ``ziel='geschichte'``, ``phase=7``)?"""
    return any(
        z["ziel"] == "geschichte" and z["phase"] == PHASE_BUEHNE
        for z in repo.prueflaeufe(conn, chat_id)
    )


def weiter_7(conn, tg, klm, e, chat_id: int, *,
             aus_eintritt: bool = False) -> threading.Thread | None:
    """Der EINE Schrittweg von Phase 7: Formen, dann Sprechweisen, dann
    Szene fuer Szene, dann der Schluss.

    Liefert den angestossenen Thread (oder ``None``) -- fuer Tests. Konnte
    ein Lauf nicht anlaufen, bekommt die Gruppe ``_TEXT_LAEUFT_NOCH`` statt
    Stille -- ausser beim Szenenlauf: ``szene.starte`` sagt selbst, warum
    (besetzt, fehlende Felder, USA-Frage).

    ``aus_eintritt``: ist schon alles fertig UND die Schlusspruefung schon
    gelaufen (``schluss_gelaufen``), laeuft sie NICHT noch einmal --
    stattdessen eine Zeile mit dem Verweis. Lief sie nie, wird sie
    nachgeholt."""
    from interview_theater import knoepfe, prueflauf, sprechweise, szene

    if formen_offen(conn, chat_id):
        sende_formwahl(conn, tg, e, chat_id)
        return None
    if not sprechweisen_fixiert(conn, chat_id):
        faden = sprechweise.starte(conn, tg, klm, e, chat_id)
        if faden is None:
            _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return faden
    nummer = aktuelle_szene(conn, chat_id)
    if nummer is not None:
        zeile = next(s for s in _szenen(conn, chat_id) if s["nummer"] == nummer)
        if not _gesetzt(zeile["volltext"]):
            # Ueber den Prueflauf (``szene._lauf``), endet im Hinweis.
            return szene.starte(conn, tg, klm, e, chat_id,
                                T._AUFTRAG_BUEHNE.format(nummer=nummer))
        faden = prueflauf.starte_szene(
            conn, tg, klm, e, chat_id, nummer,
            danach=lambda b: knoepfe.zeige_geprueft_szene(
                conn, tg, e, chat_id, nummer, b),
        )
        if faden is None:
            _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return faden
    if aus_eintritt and schluss_gelaufen(conn, chat_id):
        _sende(conn, tg, e, chat_id,
               _fertigzeile(conn, e, chat_id, T._TEXT_7_SCHON_FERTIG))
        return None
    # Ohne Protokollzeile der Schlusspruefung (Neustart mitten im Thread,
    # Sperre belegt) wird sie hier nachgeholt -- auch beim Eintritt: das ist
    # kein Phasensprung, sondern eine Pruefung, die nie lief (Review Task 9).
    faden = starte_schluss(conn, tg, klm, e, chat_id)
    if faden is None:
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
    return faden


def bestaetige_sprechweisen(conn, tg, klm, e, chat_id: int) -> str:
    """"Yes, save" unter den Sprechweisen: fixieren, ansagen, weiter.

    Laeuft noch ein Lauf (Sprechweisen oder Szene), wird NICHTS
    gespeichert; ein veralteter Knopf nach dem Fixieren wirkt nicht."""
    from interview_theater import sprechweise

    if laeuft(chat_id) or sprechweise._sperre_fuer(chat_id).locked():
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    if sprechweisen_fixiert(conn, chat_id):
        return T._ANTWORT_SCHON_GESPEICHERT
    repo.setze_arbeitsstand(conn, chat_id, "sprechweisen_fixiert_am", repo._jetzt())
    text = T._TEXT_SPRECHWEISEN_GESPEICHERT.format(
        gesamt=len(szenennummern(conn, chat_id)))
    _sende(conn, tg, e, chat_id, text)
    weiter_7(conn, tg, klm, e, chat_id)
    return text


def bestaetige_szene_7(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" unter einer Buehnenszene: abnehmen (``fertig_am``),
    weiter -- zur naechsten Szene oder, nach der letzten, zum Schluss."""
    from interview_theater import knoepfe

    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    if nummer != aktuelle_szene(conn, chat_id):
        neu = _uebertrage_neu_falls_noetig(conn, tg, klm, e, chat_id)
        if neu is not None:
            return neu
        return _nicht_dran(conn, tg, e, chat_id)
    ziel = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
    if ziel is None:
        tg.sende(chat_id, knoepfe.T._TEXT_SZENE_UNBEKANNT)
        return knoepfe.T._TEXT_SZENE_UNBEKANNT
    repo.setze_szene_fertig(conn, ziel["id"], True)
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        knoepfe.T._JOURNAL_SZENE_ABGENOMMEN.format(
            nummer=nummer, titel=ziel["titel"] or "").strip(),
        quelle="knopf",
    )
    weiter_7(conn, tg, klm, e, chat_id)
    return knoepfe.T._ANTWORT_SZENE_STEHT.format(nummer=nummer)


def _schluss(conn, tg, klm, e, chat_id: int, sperre: threading.Lock) -> None:
    """Thread-Rumpf von ``starte_schluss``: Pruefung uebers ganze Textbuch
    unter der Szenensperre, dann -- nach der Freigabe -- die Berichtszeilen,
    die Stueckpruefung und ganz zuletzt die Fertig-Zeile."""
    from interview_theater import prueflauf, stueckpruefung

    bericht = None
    try:
        bericht = prueflauf.pruefe_geschichte(
            conn, tg, klm, e, chat_id, fragen=prueflauf.FRAGEN_GESCHICHTE)
    except Exception:
        log.exception("Schlusspruefung gescheitert, chat_id=%s", chat_id)
    finally:
        sperre.release()
    try:
        zeilen = list(getattr(bericht, "zeilen", None) or [])[:prueflauf.ZEILEN_MAX]
        if zeilen:
            _sende(conn, tg, e, chat_id, "\n".join(zeilen))
    except Exception:
        log.exception("Berichtszeilen nicht zustellbar, chat_id=%s", chat_id)

    gesendet: list[bool] = []

    def fertig() -> None:
        if gesendet:
            return
        gesendet.append(True)
        _sende(conn, tg, e, chat_id,
               _fertigzeile(conn, e, chat_id, T._TEXT_TEXTBUCH_FERTIG))

    faden = None
    try:
        faden = stueckpruefung.starte(conn, tg, klm, e, chat_id, nachbereitung=fertig)
    except Exception:
        log.exception("Stueckpruefung nicht gestartet, chat_id=%s", chat_id)
    if faden is None:
        # Ohne Stueckpruefungs-Thread (kein Modell, Fehler beim Start) laeuft
        # die Nachbereitung nie -- die Zeile kommt trotzdem, genau einmal.
        fertig()


def starte_schluss(conn, tg, klm, e, chat_id: int) -> threading.Thread | None:
    """Der Schluss von Phase 7 im eigenen Thread: ``prueflauf.
    pruefe_geschichte`` (Phase 7 -> Schreiber je Szene auf ``volltext``)
    unter der Szenensperre, ohne Warten genommen; ``None``, wenn sie belegt
    ist. Danach die Stueckpruefung (eigener Thread, zeigt Befunde, nicht den
    Text) und ueber ihre ``nachbereitung`` die Zeile "The script is
    complete" -- so steht sie sicher NACH der Stueckpruefung."""
    from interview_theater import szene

    sperre = szene._sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        return None
    faden = threading.Thread(
        target=_schluss, args=(conn, tg, klm, e, chat_id, sperre), daemon=True)
    try:
        faden.start()
    except BaseException:
        sperre.release()
        raise
    return faden


# ---------------------------------------------------------------------------
# Chat wirkt, wo Knoepfe wirken (Task 10): die Erkenner-Arten fassung_abnehmen
# und formen_setzen. Kein Modellaufruf, kein SQL -- dieselben Wege wie die
# Knoepfe.
# ---------------------------------------------------------------------------

PHASE_ENTWURF = 5


def nimm_ab(conn, tg, klm, e, chat_id: int) -> str | None:
    """"Yes, save" aus dem Chat (Erkenner-Art ``fassung_abnehmen``): dieselbe
    Funktion wie der passende Knopf in der aktuellen Phase -- oder ``None``,
    wenn gerade nichts auf eine Abnahme wartet (dann schreibt und schickt der
    Erkenner nichts fuer diese Art).

    Phase 5: die Uebersicht (``entwurf.fixiere_uebersicht``), sonst der
    erste offene Prosa-Entwurf (``entwurf.bestaetige_szene``). Phase 6: das
    Ganze (``bestaetige_gesamt``), sonst die aktuelle Szene. Phase 7: nicht,
    solange Formen offen sind; dann die Sprechweisen, sobald jede Figur eine
    hat; sonst die aktuelle Buehnenszene.

    **Die Leiste der abgenommenen Nachricht verfaellt** (Abschlussreview,
    Fix 1): ein Knopfdruck nimmt seine Tastatur ab (``knoepfe.behandle``),
    der Chat-Weg tat das nicht -- und ein liegengebliebenes "Yes, save" oder
    "Kuerzer" unter einer schon abgenommenen Fassung wirkte spaeter noch.
    Gelesen wird die Leiste der passenden Art VOR der Wirkung, abgenommen
    werden genau diese Nachrichten NACH der Wirkung (``_mit_leiste_ab``) --
    und nur, wenn wirklich abgenommen wurde."""
    from interview_theater import entwurf, knoepfe

    phase = phasen.aktuelle(conn, chat_id)
    if phase == PHASE_ENTWURF:
        if (_stand(conn, chat_id, "geschichte_uebersicht")
                and not _stand(conn, chat_id, "geschichte_uebersicht_fixiert_am")):
            return _mit_leiste_ab(
                conn, tg, chat_id, knoepfe.ART_UEBERSICHT_PASST,
                lambda: entwurf.fixiere_uebersicht(conn, tg, klm, e, chat_id))
        nummer = entwurf.erste_offene_szene(conn, chat_id)
        zeile = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
        if zeile is not None and _gesetzt(zeile["prosa"]):
            return _mit_leiste_ab(
                conn, tg, chat_id, knoepfe.ART_SZENE_PASST,
                lambda: entwurf.bestaetige_szene(conn, tg, klm, e, chat_id, nummer))
        return None
    if phase == PHASE_UEBERARBEITUNG:
        if not gesamttext_fixiert(conn, chat_id):
            if _hat_prosa(conn, chat_id):
                return _mit_leiste_ab(
                    conn, tg, chat_id, knoepfe.ART_GESCHICHTE_PASST,
                    lambda: bestaetige_gesamt(conn, tg, klm, e, chat_id))
            return None
        nummer = aktuelle_szene(conn, chat_id)
        zeile = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
        if zeile is not None and _gesetzt(zeile["prosa"]):
            return _mit_leiste_ab(
                conn, tg, chat_id, knoepfe.ART_SZENE_PASST,
                lambda: bestaetige_szene_6(conn, tg, klm, e, chat_id, nummer))
        return None
    if phase == PHASE_BUEHNE:
        if formen_offen(conn, chat_id):
            return None
        if not sprechweisen_fixiert(conn, chat_id):
            figuren = repo.figuren(conn, chat_id)
            if figuren and all(_gesetzt(f["sprachstil"]) for f in figuren):
                return _mit_leiste_ab(
                    conn, tg, chat_id, knoepfe.ART_SPRECHWEISEN_PASST,
                    lambda: bestaetige_sprechweisen(conn, tg, klm, e, chat_id))
            return None
        nummer = aktuelle_szene(conn, chat_id)
        zeile = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
        if zeile is not None and _gesetzt(zeile["volltext"]):
            return _mit_leiste_ab(
                conn, tg, chat_id, knoepfe.ART_SZENE_PASST,
                lambda: bestaetige_szene_7(conn, tg, klm, e, chat_id, nummer))
        # Fix-Runde 2: die aktuelle Szene wartet auf ihre (neue)
        # Uebertragung, nicht auf eine Abnahme.
        return _uebertrage_neu_falls_noetig(conn, tg, klm, e, chat_id)
    return None


def _ohne_wirkung() -> set[str]:
    """Die Antworten der Abnahmewege, hinter denen NICHTS gespeichert wurde."""
    from interview_theater import knoepfe

    return {T._TEXT_LAEUFT_NOCH, T._TEXT_NICHT_DRAN, T._ANTWORT_SCHON_GESPEICHERT,
            knoepfe.T._TEXT_SZENE_UNBEKANNT}


def _mit_leiste_ab(conn, tg, chat_id: int, art: str, abnahme) -> str | None:
    """Fuehrt ``abnahme`` aus und laesst danach die Leisten der Art ``art``
    verfallen, die VOR der Abnahme offen standen -- dieselbe Wirkung wie
    ``knoepfe.behandle`` nach einem Knopfdruck, nur ohne gedrueckte Nachricht
    (``knoepfe.basis._nimm_leisten_ab``: Knoepfe als benutzt gestempelt,
    Tastatur weg, ein Undo-Knopf bleibt allein stehen). Eine Leiste, die
    erst waehrend der Abnahme kommt (der naechste Schritt), bleibt stehen."""
    from interview_theater.knoepfe import basis

    alte = repo.offene_knoepfe(conn, chat_id, art)
    ergebnis = abnahme()
    if ergebnis is not None and ergebnis not in _ohne_wirkung():
        basis._nimm_leisten_ab(conn, tg, chat_id, alte)
    return ergebnis


#: Ein Paar "Nummer Form" aus dem ``wert`` von ``formen_setzen``: "1: chorus",
#: "2 dialogue", "scene 3 - rap". Ein fuehrendes "scene"/"Szene" ist erlaubt.
_FORM_PAAR = re.compile(
    r"^\s*(?:scene|szene)?\s*(\d{1,2})\s*[:.\-=]?\s*(.+?)\s*$", re.IGNORECASE)
_FORM_TRENNER = re.compile(r"[|,;\n]|\band\b|\bund\b", re.IGNORECASE)


def form_aus_text(text: str | None) -> str | None:
    """Der Datenbankwert einer Form (``szene.FORMEN``) aus einem freien Wort
    ("chorus", "a song", "Monolog") -- oder ``None``. Anders als
    ``szene.formdatei`` OHNE Rueckfall: eine unbekannte Angabe ("puppetry")
    setzt nichts, statt still Dialog zu werden. Geprueft wie dort: die
    Rueckfall-Form zuletzt (ihre Stichwoerter sind die allgemeinsten).

    Die Wortmenge und der Vergleich kommen aus ``workshop.form_treffer`` --
    geteilt mit ``szene.formdatei`` (A1, 06.10.2026)."""
    text = " ".join((text or "").lower().split())
    if not text:
        return None
    namen = workshop.formen()
    rueckfall = workshop.form_vorgabe()
    reihenfolge = [n for n in namen if n != rueckfall] + [n for n in namen if n == rueckfall]
    for name in reihenfolge:
        if workshop.form_treffer(name, text):
            return name
    return None


def _wende_formen_an(conn, chat_id: int, wert: str) -> list[str]:
    """Der Schreibpfad von ``formen_setzen``: ``szene.form`` je genannter
    Nummer, nur fuer bestehende Szenen und nur mit einer bekannten Form.
    Liefert je wirklich geaenderter Szene eine Zeile fuer die
    Notiert-Meldung.

    Geschrieben wird ``form`` und NICHT ``form_vorschlag``: die Gruppe hat
    gewaehlt (docs/agents/was-bewusst-fehlt.md, "Eine Menuezeile ist keine Geschichte" -- "die
    Regel haelt den Vorschlag eines Modells aus dem Feld heraus, nicht die
    Wahl der Gruppe"). Kein Richter-Weg schreibt hier
    (``repo.GESCHUETZTE_SZENENFELDER`` bleibt fuer die Pruefung tabu)."""
    szenen = {s["nummer"]: s for s in _szenen(conn, chat_id)}
    anzeige = dict(zip(workshop.formen(), workshop.form_anzeige()))
    zeilen: list[str] = []
    for teil in _FORM_TRENNER.split(wert or ""):
        treffer = _FORM_PAAR.match(teil or "")
        if not treffer:
            continue
        zeile = szenen.get(int(treffer.group(1)))
        form = form_aus_text(treffer.group(2))
        if zeile is None or form is None or zeile["form"] == form:
            continue
        repo.setze_szenenfeld(conn, zeile["id"], "form", form)
        vorlage = T._ZEILE_FORM_GESETZT
        if _gesetzt(zeile["form"]) and _gesetzt(zeile["volltext"]):
            # Abschlussreview, Fix 4: die Szene war in ihrer alten Form schon
            # uebertragen. Ohne das stuende "Notiert: Szene 2: Lied" ueber
            # einem Dialog (Flow-Audit B2). Der Buehnentext und die Abnahme
            # werden zurueckgenommen -- ``aktuelle_szene``/``weiter_7``
            # uebertragen sie neu. Kein Modellaufruf hier; die alte Fassung
            # bleibt in ``szenenfassung`` stehen.
            repo.nimm_buehnentext_zurueck(conn, zeile["id"])
            vorlage = T._ZEILE_FORM_NEU_UEBERTRAGEN
        zeilen.append(vorlage.format(
            nummer=zeile["nummer"], form=anzeige.get(form, form)))
    return zeilen


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

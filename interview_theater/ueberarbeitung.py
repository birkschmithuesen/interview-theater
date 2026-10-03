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


def bestaetige_gesamt(conn, tg, klm, e, chat_id: int) -> str:
    """"Yes, save" auf dem Ganzen: fixieren, ansagen, erste Szene pruefen.

    Laeuft noch ein Lauf (z. B. die Ueberarbeitung des Ganzen), wird NICHTS
    gespeichert -- sonst naehme ein veralteter Knopf eine alte Fassung ab."""
    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    repo.setze_arbeitsstand(conn, chat_id, "gesamttext_fixiert_am", repo._jetzt())
    text = T._TEXT_GESAMT_GESPEICHERT.format(
        gesamt=len(szenennummern(conn, chat_id)))
    _sende(conn, tg, e, chat_id, text)
    weiter_6(conn, tg, klm, e, chat_id)
    return text


def bestaetige_szene_6(conn, tg, klm, e, chat_id: int, nummer: int) -> str:
    """"Yes, save" auf einer Szene in Phase 6: abnehmen, weiter."""
    from interview_theater import knoepfe

    if laeuft(chat_id):
        _sende(conn, tg, e, chat_id, T._TEXT_LAEUFT_NOCH)
        return T._TEXT_LAEUFT_NOCH
    ziel = next((s for s in _szenen(conn, chat_id) if s["nummer"] == nummer), None)
    if ziel is None:
        tg.sende(chat_id, knoepfe.T._TEXT_SZENE_UNBEKANNT)
        return knoepfe.T._TEXT_SZENE_UNBEKANNT
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


def weiter_7(conn, tg, klm, e, chat_id: int, *,
             aus_eintritt: bool = False) -> threading.Thread | None:
    """Der EINE Schrittweg von Phase 7: Formen, dann Sprechweisen, dann
    Szene fuer Szene, dann der Schluss.

    Liefert den angestossenen Thread (oder ``None``) -- fuer Tests. Konnte
    ein Lauf nicht anlaufen, bekommt die Gruppe ``_TEXT_LAEUFT_NOCH`` statt
    Stille -- ausser beim Szenenlauf: ``szene.starte`` sagt selbst, warum
    (besetzt, fehlende Felder, USA-Frage).

    ``aus_eintritt``: ist schon alles fertig, laeuft die Schlusspruefung
    NICHT noch einmal von selbst -- sie gehoert dem Abnahmeweg
    (``bestaetige_szene_7``). Stattdessen eine Zeile mit dem Verweis."""
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
    if aus_eintritt:
        _sende(conn, tg, e, chat_id,
               _fertigzeile(conn, e, chat_id, T._TEXT_7_SCHON_FERTIG))
        return None
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


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

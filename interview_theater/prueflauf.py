"""Der Prueflauf vor jeder Anzeige (Padua Phasen TEIL 2, 03.10.2026).

Bevor die Gruppe in Padua einen Text sieht -- eine Szene als Geschichte, die
ganze Geschichte oder eine Szene als Buehnentext --, laeuft hier eine
Teilmenge der Richterfragen ueber genau diesen Text, und was die Fragen
finden, wird ueberarbeitet. Erst danach kommt der Sprachpass (``nachpass``),
und erst danach zeigt der Aufrufer, was steht.

**Birks Entscheidungen, wie sie hier gebaut sind:**

* *Hoechstens zwei Ueberarbeitungsrunden* (``schleife.RUNDEN_MAX = 2``) --
  der Prueflauf ruft ``schleife.schliesse`` und baut keine eigene Schleife.
* *Faellt ein Score, bricht der Lauf ab, und die bessere Fassung bleibt*
  (``behalte_bessere=True``). Die Gruppe bekommt dazu EINE Zeile.
* *Verliert eine Ueberarbeitung ein geprueftes Interviewzitat, wird sie
  verworfen* (``sprachpass.verlorene`` -- dieselbe Pruefung wie im Nachpass,
  ``zitat.pruefe`` darunter, keine zweite Normalisierung).
* *Hoechstens drei Zeilen dazu, was die Pruefung geaendert hat* -- kein
  Volltext, kein Befundbericht.

**Die Sperre haelt der Aufrufer.** ``pruefe_szene`` und ``pruefe_geschichte``
sind synchron und laufen im schon laufenden Thread eines Schreibwegs
(``szene._lauf``, ``kurzgeschichte._lauf``) unter dessen Sperre: in den
Prosa-Phasen die der Kurzgeschichte, im Feinschliff die der Szene. Deshalb
nehmen die Schreiber hier (``_schreibe_szenen``, ``_schreibe_geschichte``)
**keine** Sperre -- anders als ``schleife._schreibe_je_szene``, das sie
selbst nimmt und den Text zeigt. ``starte_szene`` / ``starte_geschichte``
sind die beiden Wege fuer einen Aufrufer ohne Thread: Sperre ohne Warten,
eigener Thread, danach ``danach(bericht)``.

**Er zeigt nie etwas.** Jeder Schreiblauf hier geht mit ``zeigen=False``;
die Anzeige samt Knoepfen baut der Aufrufer aus dem ``Bericht``. Ohne den
Profilschalter ``[prueflauf] aktiv`` (nur Padua) ruft niemand dieses Modul.
SQL steht hier keines -- alles geht ueber ``repo``.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from interview_theater import repo, workshop

log = logging.getLogger(__name__)

#: Die Fragen ueber die ganze Geschichte (Phase 6, Rewrite): Kausalkette,
#: Tschechow, Fokus, Stueckvorgaben.
FRAGEN_GESCHICHTE = ("a2", "a6", "a9", "a11")
#: Die Fragen an eine einzelne Szene als Geschichte: Wendung, Materialtreue.
FRAGEN_PROSASZENE = ("b1", "a10")
#: Die Fragen an eine Szene als Buehnentext: Materialtreue (ab Phase 7 mit
#: den Formregeln, ``fanout.A10_FORM_AB_PHASE``) und Stimme.
FRAGEN_BUEHNENSZENE = ("a10", "c1")

#: Die ``art`` der Ueberarbeitungslaeufe in der Tabelle ``aufruf`` -- wie
#: ``szene_nachpass`` getrennt zaehlbar.
ART_UEBERARBEITUNG = "prueflauf_ueberarbeitung"

GRUND_OHNE_TEXT = "ohne_text"
GRUND_OHNE_PRUEFUNG = "ohne_pruefung"
VERWORFEN_ZITAT = "zitat"
VERWORFEN_VERSCHLECHTERUNG = "verschlechterung"

VORFALL_OHNE_RICHTER = "prueflauf_ohne_richter"
VORFALL_FEHLGESCHLAGEN = "prueflauf_fehlgeschlagen"
#: Klasse 8b/9 der P7-Audit-Karte (``kartentreue.py``): ein Hakenpunkt der
#: Karte wurde woertlich widersprochen, bzw. ein OBBLIGATORIO-Stichwort fehlt
#: auch nach dem einen automatischen Nachschrieb.
VORFALL_KARTE_WIDERSPROCHEN = "karte_widersprochen"
VORFALL_OBBLIGATORIO_FEHLT = "obbligatorio_fehlt"

#: Hoechstens so viele Zeilen gehen an die Gruppe (Birk).
ZEILEN_MAX = 3
#: Hoechstens so viele Zeichen je Auftragszeile.
ZEICHEN_MAX = 100

_PRUEFUNG_NAMEN = {
    "b1": "Wendung", "a2": "Kausalkette", "a6": "Tschechow", "a9": "Fokus",
    "a10": "Materialtreue", "a11": "Stueckvorgaben", "c1": "Stimme",
}
_ZEILE_AUFTRAG = "Pruefung ({pruefung}): {text}"
_ZEILE_SPRACHPASS = "Sprachpass: Laenge und Sprachmuster nachgezogen."
_ZEILE_VERSCHLECHTERT = "Die Ueberarbeitung war schwaecher -- die bessere Fassung bleibt."
_ZEILE_ZITAT_VERWORFEN = "Eine Ueberarbeitung hat ein Interviewzitat verloren -- verworfen."
_ZEILE_PARAMETER = "Szene {nummer}: die Planung ({feld}) folgt jetzt dem Text."
#: Die Journalzeile einer Parameterkorrektur -- sie geht in den Prompt jedes
#: weiteren Laufs, deshalb ueber ``T``.
_JOURNAL_PARAMETER = "Szene {nummer}: {feld} folgt jetzt dem Text: {wert}"


def aktiv() -> bool:
    """Laeuft der Prueflauf in diesem Workshop? Nur in Padua."""
    return workshop.prueflauf_aktiv()


@dataclass
class Bericht:
    """Was ein Prueflauf dem Aufrufer zurueckgibt -- die Zeilen fuer die
    Gruppe (hoechstens drei) und die Zahlen der Protokollzeile."""

    zeilen: list[str] = field(default_factory=list)
    runden: int = 0
    ueberarbeitungen: int = 0
    auftraege_je_runde: list[int] = field(default_factory=list)
    verworfen: str | None = None
    grund: str = ""
    dauer_ms: int = 0


# ---------------------------------------------------------------------------
# Kleine Helfer
# ---------------------------------------------------------------------------


def _name(schluessel: str) -> str:
    return T._PRUEFUNG_NAMEN.get(schluessel, schluessel)


def _kurz(text: str, laenge: int = ZEICHEN_MAX) -> str:
    """Schneidet am letzten Leerzeichen vor ``laenge`` Zeichen und haengt
    "…" an; kuerzere Texte bleiben, wie sie sind."""
    text = " ".join((text or "").split())
    if len(text) <= laenge:
        return text
    schnitt = text.rfind(" ", 0, laenge)
    if schnitt <= 0:
        schnitt = laenge
    return text[:schnitt].rstrip() + "…"


def _feld(conn, chat_id: int) -> str:
    from interview_theater import szene

    return "prosa" if szene.schreibt_prosa(conn, chat_id) else "volltext"


def _zeile_der_szene(conn, chat_id: int, nummer: int):
    return next((s for s in repo.hole_szenen(conn, chat_id)
                 if s["nummer"] == nummer), None)


def _text(zeile, feld: str) -> str:
    return ((zeile[feld] if zeile is not None else None) or "").strip()


def _stueck(conn, chat_id: int, feld: str) -> str:
    """Der Text aller Szenen am Stueck -- fuer die Zitatwache der Geschichte."""
    return "\n\n".join(
        _text(s, feld) for s in sorted(
            repo.hole_szenen(conn, chat_id), key=lambda s: s["nummer"] or 0)
    )


def _vorfall(conn, chat_id: int, e, art: str, text: str) -> None:
    try:
        repo.merke_vorfall(conn, chat_id, getattr(e, "bot_name", None), art, text)
    except Exception:
        log.exception("Vorfall %s nicht schreibbar, chat_id=%s", art, chat_id)


def _fehler(conn, chat_id: int, e, schritt: str) -> None:
    """Aus einem ``except``-Block: Traceback ins Log, ein Vorfall fuers
    Dashboard -- und weiter. Ein Prueflauf endet IMMER mit Protokollzeile und
    ``Bericht``; die Gruppe sieht ihren Text auch, wenn ein Schritt reisst."""
    log.exception("Prueflauf: %s gescheitert, chat_id=%s", schritt, chat_id)
    _vorfall(conn, chat_id, e, VORFALL_FEHLGESCHLAGEN, f"Prueflauf: {schritt} gescheitert")


def _stelle_wieder_her(conn, chat_id: int, e, stand) -> None:
    from interview_theater.dramaturgie import schleife

    try:
        schleife.stelle_wieder_her(conn, chat_id, stand)
    except Exception:
        _fehler(conn, chat_id, e, "Wiederherstellen")


def _merke_erstentwurf(conn, chat_id: int, zeile, text: str) -> None:
    """Schritt 3: die Fassung VOR der Pruefung ist die Erstfassung ("Show
    first draft"). Steht sie noch nicht als letzte Fassung in
    ``szenenfassung``, wird sie angehaengt -- nur anhaengen, nie aendern."""
    sid = zeile["id"]
    letzte = repo.letzte_szenenfassung(conn, sid)
    if letzte is None or (letzte["volltext"] or "").strip() != text:
        repo.haenge_szenenfassung_an(conn, chat_id, sid, text,
                                     zeile["zusammenfassung"], None)
        letzte = repo.letzte_szenenfassung(conn, sid)
    if letzte is not None:
        repo.setze_szene_erstentwurf(conn, sid, letzte["nummer"])


def _schliesse(conn, tg, klm, e, chat_id: int, zeilen: list[str], stand, **kwargs):
    """``schleife.schliesse`` mit der Fehlerhaltung des Prueflaufs: was auch
    reisst, die Gruppe sieht ihren Text trotzdem -- ohne Pruefung.

    **Und dann den Text von VOR der Pruefung** (Review Task 6, Fix-Runde 1):
    reisst die Schleife mittendrin (Tagesdeckel, 5xx in Runde 2), kann eine
    Ueberarbeitung schon geschrieben sein, die nie neu bewertet wurde. Sie zu
    zeigen hiesse, ungeprueften Text als geprueft auszugeben -- deshalb geht
    jede Ausnahme zurueck auf ``stand``. Ohne Aenderung ist das ein No-Op."""
    from interview_theater import kosten
    from interview_theater.dramaturgie import fanout, schleife

    try:
        richter = fanout.waehle_richter(e, conn, chat_id)
        return schleife.schliesse(
            conn, tg, klm, e, chat_id, richter=richter, mechanik=False,
            behalte_bessere=True, **kwargs,
        )
    except fanout.RichterFehler as fehler:
        zeilen.append(str(fehler))
        _vorfall(conn, chat_id, e, VORFALL_OHNE_RICHTER, str(fehler))
    except kosten.KostendeckelErreicht:
        try:
            kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id)
        except Exception:
            log.exception("Pausenmeldung gescheitert, chat_id=%s", chat_id)
    except Exception:
        _fehler(conn, chat_id, e, "Pruefschleife")
    _stelle_wieder_her(conn, chat_id, e, stand)
    return None


def _massgebliche_runde(erg, zitat_verworfen: bool):
    """Die Runde, deren Pruefung den Text betrifft, der jetzt steht.

    Nach einer verworfenen Ueberarbeitung (Zitat) steht wieder der Text der
    ersten Pruefung; nach einer Verschlechterung der Text der vorletzten.
    Eine Parameterkorrektur aus der Pruefung eines verworfenen Textes liesse
    die Planung einem Text folgen, den es nicht mehr gibt."""
    if not erg or not erg.runden:
        return None
    if zitat_verworfen:
        return erg.runden[0]
    if erg.wiederhergestellt and len(erg.runden) > 1:
        return erg.runden[-2]
    return erg.runden[-1]


def _parameterkorrektur(conn, chat_id: int, runde, nummer: int, sid: int) -> list[str]:
    """Schritt 7: A10 in beiden Richtungen. Sagt der Richter, dass der TEXT
    recht hat und die Planung veraltet ist (``richtung=parameter``), folgt die
    Planung dem Text -- mit Journalzeile und einer Zeile an die Gruppe."""
    from interview_theater.dramaturgie import fanout

    zeilen: list[str] = []
    if runde is None:
        return zeilen
    for befund in repo.dramaturgie_befunde(conn, chat_id, runde=runde.nummer):
        if befund["pruefung"] != "a10" or befund["richtung"] != "parameter":
            continue
        if befund["szene"] != nummer:
            continue
        korrektur = fanout.parameterkorrektur(befund)
        if korrektur is None:
            continue
        feld, wert = korrektur
        # Nie ein geschuetztes Feld (Birk 7.1): die Form waehlt die Gruppe,
        # den Stil auch -- ein Richter, der ``form: Monolog`` vorschlaegt,
        # setzt sie nicht. Text-Spalten sind ohnehin keine Planung.
        if feld not in repo.SZENENFELDER or feld in repo.GESCHUETZTE_SZENENFELDER:
            continue
        repo.setze_szenenfeld(conn, sid, feld, wert)
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            T._JOURNAL_PARAMETER.format(nummer=nummer, feld=feld, wert=wert),
            quelle="prueflauf",
        )
        zeilen.append(T._ZEILE_PARAMETER.format(nummer=nummer, feld=feld))
    return zeilen


def _auftragszeilen(erg, verworfen: str | None) -> list[str]:
    """Schritt 11: je Auftrag einer Runde, die wirklich ueberarbeitet hat,
    eine Zeile. Was verworfen wurde, hat nichts geaendert und bekommt keine:
    nach der Zitatwache steht wieder der Text vor der Pruefung, nach einer
    Verschlechterung der vor der letzten Ueberarbeitung."""
    zeilen: list[str] = []
    if not erg or verworfen == VERWORFEN_ZITAT:
        return zeilen
    runden = [r for r in erg.runden if r.ueberarbeitet]
    if verworfen == VERWORFEN_VERSCHLECHTERUNG:
        runden = runden[:-1]
    for runde in runden:
        for a in runde.auftraege or []:
            zeilen.append(T._ZEILE_AUFTRAG.format(
                pruefung=_name(a["pruefung"]), text=_kurz(a["anweisung"])))
    return zeilen


def _protokolliere(conn, chat_id: int, *, ziel: str, nummer, fragen, erg,
                   verworfen, zeilen: list[str], t0: float) -> Bericht:
    """Schritt 12: eine Zeile je Lauf in ``prueflauf`` -- die Messgrundlage
    fuer ``RUNDEN_MAX`` -- und derselbe Stand als ``Bericht``."""
    from interview_theater import phasen

    runden = len(erg.runden) if erg else 0
    ueberarbeitungen = sum(1 for r in erg.runden if r.ueberarbeitet) if erg else 0
    je_runde = [len(r.auftraege or []) for r in erg.runden] if erg else []
    zweite = bool(erg and len(erg.runden) > 1 and erg.runden[1].auftraege)
    grund = erg.grund if erg else GRUND_OHNE_PRUEFUNG
    dauer_ms = int((time.monotonic() - t0) * 1000)
    try:
        repo.lege_prueflauf_an(
            conn, chat_id, phase=phasen.aktuelle(conn, chat_id), ziel=ziel,
            szene_nummer=nummer, fragen=",".join(fragen), runden=runden,
            ueberarbeitungen=ueberarbeitungen,
            auftraege_je_runde=",".join(str(n) for n in je_runde),
            zweite_runde_mit_auftraegen=zweite, grund=grund,
            verworfen=verworfen, dauer_ms=dauer_ms,
        )
    except Exception:
        log.exception("Prueflauf-Protokoll nicht schreibbar, chat_id=%s", chat_id)
    log.info(
        "Prueflauf chat_id=%s ziel=%s szene=%s fragen=%s runden=%s "
        "ueberarbeitungen=%s auftraege=%s zweite_mit_auftraegen=%s grund=%s "
        "verworfen=%s dauer_ms=%s",
        chat_id, ziel, nummer, ",".join(fragen), runden, ueberarbeitungen,
        je_runde, zweite, grund, verworfen, dauer_ms,
    )
    return Bericht(zeilen=zeilen[:ZEILEN_MAX], runden=runden,
                   ueberarbeitungen=ueberarbeitungen, auftraege_je_runde=je_runde,
                   verworfen=verworfen, grund=grund, dauer_ms=dauer_ms)


# ---------------------------------------------------------------------------
# Die Schreiber fuer ``schleife`` -- ohne Sperre, ohne Anzeige
# ---------------------------------------------------------------------------


def _schreibe_szenen(conn, tg, klm, e, chat_id: int, auftraege) -> list[int]:
    """Ein Ueberarbeitungslauf je Szene, alle Auftraege dieser Szene in einer
    Notiz. **Keine Sperre** -- die haelt der Aufrufer des Prueflaufs -- und
    ``zeigen=False``. Die Sperre aus ``szene.sperrtext`` gilt wie in
    ``schleife._schreibe_je_szene``."""
    from interview_theater import szene

    je_szene: dict[int, list[str]] = {}
    for a in auftraege:
        if a.get("szene") is not None:
            je_szene.setdefault(int(a["szene"]), []).append(a["anweisung"])
    geschrieben: list[int] = []
    for nummer, notizen in sorted(je_szene.items()):
        auftrag = szene.ueberarbeitungsauftrag(conn, chat_id, nummer, " ".join(notizen))
        ziel = szene.ziel_fuer(conn, chat_id, auftrag)
        fehlt = szene.sperrtext(conn, ziel)
        if fehlt:
            log.info("Prueflauf ueberspringt Szene %s, chat_id=%s: %s",
                     nummer, chat_id, fehlt)
            continue
        szene.schreibe(conn, tg, klm, e, chat_id, auftrag,
                       art=ART_UEBERARBEITUNG, zeigen=False)
        geschrieben.append(nummer)
    return geschrieben


def _schreibe_geschichte(conn, tg, klm, e, chat_id: int, auftraege) -> list[int]:
    """Prosa-Phasen: EIN Lauf ueber die ganze Geschichte mit allen Auftraegen
    als einer Regie-Notiz, mit der bestehenden Geschichte als Vorlage. Keine
    Sperre (die Kurzgeschichtensperre haelt der Aufrufer), nichts gezeigt."""
    from interview_theater import kurzgeschichte
    from interview_theater.dramaturgie import schleife

    kurzgeschichte.schreibe(
        conn, tg, klm, e, chat_id, schleife._regie_fuer_die_geschichte(auftraege),
        vorlage=True, art=ART_UEBERARBEITUNG, zeigen=False,
    )
    return sorted(s["nummer"] for s in repo.hole_szenen(conn, chat_id)
                  if s["nummer"] is not None and (s["prosa"] or "").strip())


def _kartentreue(conn, tg, klm, e, chat_id: int, nummer: int, feld: str) -> list[str]:
    """Klassen 8b/9 (P7-Audit-Karte, Birk 08.10.2026): nach dem Nachpass die
    fertige Szene gegen ihre Karte -- nur fuer den Buehnentext (``feld ==
    "volltext"``) und nur, wenn ueberhaupt eine Karte existiert (sonst reines
    No-Op, z. B. Dortmund oder ohne das Profil ``[karten] aktiv``).

    Ein woertlich widersprochener Hakenpunkt geht nur als Vorfall ins Log
    (Klasse 8b -- kein automatischer Eingriff, das ist Sache des Richters).
    Ein fehlendes OBBLIGATORIO-Stichwort bekommt GENAU EINEN automatischen
    Nachschrieb mit der Luecke als Notiz (Klasse 9); fehlt es danach immer
    noch, bleibt ein Vorfall."""
    if feld != "volltext":
        return []
    from interview_theater import kartentreue, szene, szenenkarte

    zeile = _zeile_der_szene(conn, chat_id, nummer)
    karte = szenenkarte.karte_von(zeile) if zeile is not None else None
    if karte is None:
        return []
    text = _text(zeile, feld)
    widersprueche = kartentreue.widersprueche(karte, text)
    if widersprueche:
        _vorfall(conn, chat_id, e, VORFALL_KARTE_WIDERSPROCHEN,
                 f"Szene {nummer}: " + " | ".join(widersprueche))

    fehlend = kartentreue.fehlende_stichworte(karte, text)
    if not fehlend:
        return []
    try:
        auftrag = szene.ueberarbeitungsauftrag(
            conn, chat_id, nummer,
            "Missing mandatory point(s) from the scene card -- the script "
            "must literally include: " + "; ".join(fehlend) + ".",
        )
        ziel = szene.ziel_fuer(conn, chat_id, auftrag)
        if szene.sperrtext(conn, ziel) is None:
            szene.schreibe(conn, tg, klm, e, chat_id, auftrag,
                           art=ART_UEBERARBEITUNG, zeigen=False)
    except Exception:
        _fehler(conn, chat_id, e, "Kartentreue-Nachschrieb")
    neuer_text = _text(_zeile_der_szene(conn, chat_id, nummer), feld)
    fehlend_danach = kartentreue.fehlende_stichworte(karte, neuer_text)
    if fehlend_danach:
        _vorfall(conn, chat_id, e, VORFALL_OBBLIGATORIO_FEHLT,
                 f"Szene {nummer}: " + "; ".join(fehlend_danach))
    return []


# ---------------------------------------------------------------------------
# Die beiden Prueflaeufe
# ---------------------------------------------------------------------------


def pruefe_szene(conn, tg, klm, e, chat_id: int, nummer: int) -> Bericht:
    """Prueft den AKTUELLEN Text einer Szene, ueberarbeitet hoechstens
    zweimal, prueft die Zitate, laesst den Nachpass laufen und protokolliert.
    Synchron; **der Aufrufer haelt ``szene._sperre_fuer(chat_id)``**. Zeigt
    nichts."""
    from interview_theater import nachpass, sprachpass
    from interview_theater.dramaturgie import schleife

    t0 = time.monotonic()
    feld = _feld(conn, chat_id)   # dieselbe Weiche wie ``szene.schreibt_prosa``
    zeile = _zeile_der_szene(conn, chat_id, nummer)
    text = _text(zeile, feld)
    if not text:
        return Bericht(grund=GRUND_OHNE_TEXT,
                       dauer_ms=int((time.monotonic() - t0) * 1000))
    sid = zeile["id"]

    fragen = FRAGEN_PROSASZENE if feld == "prosa" else FRAGEN_BUEHNENSZENE
    zeilen: list[str] = []
    erg = None
    verworfen = None
    # Jeder Schritt in seinem eigenen ``try`` (Fix-Runde 1): was auch reisst,
    # am Ende stehen Protokollzeile und ``Bericht``.
    try:
        _merke_erstentwurf(conn, chat_id, zeile, text)
    except Exception:
        _fehler(conn, chat_id, e, "Erstfassung")
    zitate: list[str] = []
    stand = None
    try:
        zitate = sprachpass.gepruefte_zitate(conn, chat_id)
        stand = schleife.schnappschuss(conn, chat_id)
    except Exception:
        _fehler(conn, chat_id, e, "Schnappschuss")
    # Ohne Schnappschuss kein Rueckweg -- dann auch keine Ueberarbeitung.
    if stand is not None:
        erg = _schliesse(conn, tg, klm, e, chat_id, zeilen, stand, fragen=fragen,
                         szenen=(nummer,), schreiber=_schreibe_szenen)

    # Erst steht fest, welcher Text bleibt (Zitatwache, Verschlechterung),
    # dann folgt die Planung DIESEM Text -- siehe ``_massgebliche_runde``.
    try:
        hinweise: list[str] = []
        neu = _text(_zeile_der_szene(conn, chat_id, nummer), feld)
        if stand is not None and sprachpass.verlorene(text, neu, zitate):
            _stelle_wieder_her(conn, chat_id, e, stand)
            verworfen = VERWORFEN_ZITAT
            hinweise.append(T._ZEILE_ZITAT_VERWORFEN)
        elif erg and erg.wiederhergestellt:
            verworfen = VERWORFEN_VERSCHLECHTERUNG
            hinweise.append(T._ZEILE_VERSCHLECHTERT)
        zeilen.extend(_parameterkorrektur(
            conn, chat_id, _massgebliche_runde(erg, verworfen == VERWORFEN_ZITAT),
            nummer, sid))
        zeilen.extend(hinweise)
    except Exception:
        _fehler(conn, chat_id, e, "Zitatwache/Parameter")

    try:
        vor_nachpass = _text(_zeile_der_szene(conn, chat_id, nummer), feld)
        try:
            nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer, zeigen=False)
        except Exception:
            log.exception("Nachpass im Prueflauf gescheitert, chat_id=%s, Szene %s",
                          chat_id, nummer)
            nachpass._vorfall(conn, chat_id, e, nachpass.VORFALL_FEHLER,
                              f"Szene {nummer}: Nachpass gescheitert")
        if _text(_zeile_der_szene(conn, chat_id, nummer), feld) != vor_nachpass:
            zeilen.append(T._ZEILE_SPRACHPASS)
    except Exception:
        _fehler(conn, chat_id, e, "Nachpass")

    try:
        _kartentreue(conn, tg, klm, e, chat_id, nummer, feld)
    except Exception:
        _fehler(conn, chat_id, e, "Kartentreue")

    try:
        zeilen.extend(_auftragszeilen(erg, verworfen))
    except Exception:
        _fehler(conn, chat_id, e, "Zeilen")
    return _protokolliere(conn, chat_id, ziel="szene", nummer=nummer,
                          fragen=fragen, erg=erg, verworfen=verworfen,
                          zeilen=zeilen, t0=t0)


def pruefe_geschichte(conn, tg, klm, e, chat_id: int, *,
                      fragen=FRAGEN_GESCHICHTE) -> Bericht:
    """Prueft ALLE Szenen zusammen. Synchron; **der Aufrufer haelt die
    passende Sperre** -- die der Kurzgeschichte in den Prosa-Phasen, die der
    Szene im Feinschliff. In den Prosa-Phasen laeuft am Ende
    ``nachpass.nach_geschichte``; im Feinschliff keiner fuer das ganze Stueck
    (jede Szene hatte ihren eigenen). Zeigt nichts."""
    from interview_theater import nachpass, sprachpass, szene
    from interview_theater.dramaturgie import schleife

    t0 = time.monotonic()
    prosa = szene.schreibt_prosa(conn, chat_id)
    feld = _feld(conn, chat_id)
    fragen = tuple(fragen)
    zeilen: list[str] = []
    erg = None
    verworfen = None
    vorher = ""
    zitate: list[str] = []
    stand = None
    try:
        for zeile in repo.hole_szenen(conn, chat_id):
            text = _text(zeile, feld)
            if text:
                _merke_erstentwurf(conn, chat_id, zeile, text)
    except Exception:
        _fehler(conn, chat_id, e, "Erstfassung")
    try:
        vorher = _stueck(conn, chat_id, feld)
        zitate = sprachpass.gepruefte_zitate(conn, chat_id)
        stand = schleife.schnappschuss(conn, chat_id)
    except Exception:
        _fehler(conn, chat_id, e, "Schnappschuss")

    if stand is not None and vorher.strip():
        erg = _schliesse(
            conn, tg, klm, e, chat_id, zeilen, stand, fragen=fragen, szenen=None,
            schreiber=_schreibe_geschichte if prosa else _schreibe_szenen,
        )

    try:
        if stand is not None and sprachpass.verlorene(
                vorher, _stueck(conn, chat_id, feld), zitate):
            _stelle_wieder_her(conn, chat_id, e, stand)
            verworfen = VERWORFEN_ZITAT
            zeilen.append(T._ZEILE_ZITAT_VERWORFEN)
        elif erg and erg.wiederhergestellt:
            verworfen = VERWORFEN_VERSCHLECHTERUNG
            zeilen.append(T._ZEILE_VERSCHLECHTERT)
    except Exception:
        _fehler(conn, chat_id, e, "Zitatwache")

    if prosa:
        try:
            vor_nachpass = _stueck(conn, chat_id, feld)
            try:
                nachpass.nach_geschichte(conn, tg, klm, e, chat_id)
            except Exception:
                log.exception("Prosa-Nachpass im Prueflauf gescheitert, chat_id=%s",
                              chat_id)
                nachpass._vorfall(conn, chat_id, e, nachpass.VORFALL_FEHLER,
                                  "Prosa-Nachpass gescheitert")
            if _stueck(conn, chat_id, feld) != vor_nachpass:
                zeilen.append(T._ZEILE_SPRACHPASS)
        except Exception:
            _fehler(conn, chat_id, e, "Nachpass")

    try:
        zeilen.extend(_auftragszeilen(erg, verworfen))
    except Exception:
        _fehler(conn, chat_id, e, "Zeilen")
    return _protokolliere(conn, chat_id, ziel="geschichte", nummer=None,
                          fragen=fragen, erg=erg, verworfen=verworfen,
                          zeilen=zeilen, t0=t0)


# ---------------------------------------------------------------------------
# Die Thread-Wege
# ---------------------------------------------------------------------------


def _starte(sperre: threading.Lock, lauf, danach) -> threading.Thread | None:
    """Sperre ohne Warten, eigener Thread, ``lauf()`` und danach
    ``danach(bericht)`` -- **nach** der Freigabe der Sperre, damit ``danach``
    selbst wieder einen Lauf anstossen darf (``szene.starte`` nimmt dieselbe
    Sperre ohne Warten und fiele sonst auf "besetzt").

    **Folge:** zwischen Freigabe und ``danach`` kann ein anderer Lauf dieser
    Gruppe beginnen und den Text aendern. ``danach`` (die Anzeige, Task 7)
    zeigt deshalb den aktuellen Stand der Datenbank, nicht einen im
    ``Bericht`` mitgefuehrten Text -- der ``Bericht`` traegt bewusst keinen."""
    if not sperre.acquire(blocking=False):
        return None

    def _rumpf() -> None:
        bericht = None
        try:
            bericht = lauf()
        except Exception:
            log.exception("Prueflauf-Thread gescheitert")
            bericht = Bericht(grund=GRUND_OHNE_PRUEFUNG)
        finally:
            sperre.release()
        try:
            danach(bericht)
        except Exception:
            log.exception("Anzeige nach dem Prueflauf gescheitert")

    faden = threading.Thread(target=_rumpf, daemon=True)
    try:
        faden.start()
    except Exception:
        sperre.release()
        raise
    return faden


def starte_szene(conn, tg, klm, e, chat_id: int, nummer: int,
                 danach) -> threading.Thread | None:
    """``pruefe_szene`` im eigenen Thread unter der Szenensperre; ``None``,
    wenn gerade ein Szenenlauf dieser Gruppe laeuft."""
    from interview_theater import szene

    return _starte(
        szene._sperre_fuer(chat_id),
        lambda: pruefe_szene(conn, tg, klm, e, chat_id, nummer),
        danach,
    )


def starte_geschichte(conn, tg, klm, e, chat_id: int,
                      danach) -> threading.Thread | None:
    """``pruefe_geschichte`` im eigenen Thread -- unter der Sperre der
    Kurzgeschichte in den Prosa-Phasen, unter der der Szene im Feinschliff;
    ``None``, wenn sie belegt ist."""
    from interview_theater import kurzgeschichte, szene

    sperre = (kurzgeschichte._sperre_fuer(chat_id)
              if szene.schreibt_prosa(conn, chat_id)
              else szene._sperre_fuer(chat_id))
    return _starte(
        sperre,
        lambda: pruefe_geschichte(conn, tg, klm, e, chat_id),
        danach,
    )


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

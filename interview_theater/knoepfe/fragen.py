"""Phase 2: der Fragenvorschlag, der Ueberblick mit Richtungsfrage, die
Fragen einzeln durchgehen, und der Leitfaden.

Padua, 02.10.2026 (zweiter Umbau nach dem vom 06.09.2026): der Bot schlaegt
fuenf Fragen je Begriff vor und prueft sie **im selben Modellzug** auf
sensible Themen (``VORSCHLAG FRAGENAUSWAHL:`` + optional
``VORSCHLAG FRAGEN WEICH:``). Darunter steht ein Ueberblick mit einer
deterministischen Richtungsfrage ("Gehen die Fragen in die richtige
Richtung? Wollen wir sie einzeln durchgehen?"); "Ja" fuehrt **Frage fuer
Frage** durch die Liste (Annehmen / Verwerfen / Schaerfen), "Andere
Richtung" fragt zuerst nach der Richtung und stoesst dann einen neuen
Vorschlag an. Eine freie Nachricht waehrend eine Frage die aktuelle ist,
zaehlt immer als Schaerfungswunsch fuer genau diese Frage -- ohne
Knopfdruck und ohne Erkenner-Lauf (``nimm_offene_frage_text``).

Die Nummernwahl aus dem ersten Umbau (``lies_fragennummern``) und ihre
Knoepfe (``ART_FRAGE_WAHL``, ``ART_FRAGEN_UEBERNEHMEN``, ``ART_FRAGEN_EIGENE``)
sind damit Geschichte. Ihre Handler bleiben in ``wirkung.py`` stehen, damit
ein Druck aus einer schon verschickten alten Nachricht nicht ins Leere
laeuft -- angeboten werden sie nicht mehr.

Padua Phase 1+2 Karte, Aufgabe 13 (03.10.2026, KORREKTUR-PHASE2-KEIN-KNOPF.md):
``uebernimm_eigene``/``versuche_gegenueberstellung`` fuer den A/B-Vergleich
eigene-vs-KI-Fragen -- KEIN "Fertig"-Knopf, der Code prueft nach jedem
Speichern eigener Fragen (``VORSCHLAG EIGENE FRAGEN:``), ob jeder Begriff
genug hat, und startet dann selbst die Gegenueberstellung mit den isoliert
im Hintergrund erzeugten KI-Fragen (``fragen_ki.py``, Aufgabe 12). Nur unter
``workshop.fragen_ab_aktiv()`` kommt der Marker ueberhaupt vor (er steht nur
im Padua-Profil-Prompt), die klassische Fuenf-je-Begriff-Vorschlagsrunde
bleibt dadurch unangetastet.
"""

import re
import threading

from interview_theater import anweisungen, erkenner, leitfaden, repo
from interview_theater import begriffe as begriffe_modul

from interview_theater.knoepfe.texte import (
    ART_FRAGE_ANNEHMEN, ART_FRAGE_SCHAERFEN, ART_FRAGE_VERWERFEN,
    ART_FRAGEN_ANDERE, ART_FRAGEN_EINZELN, ART_FRAGEN_WEICH_LASSEN,
    ART_FRAGEN_WEICH_UEBERNEHMEN, ART_LEITFADEN, T,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _nimm_alte_leiste_ab, _sende_knoepfe,
    _starte_auftrag, sende_notiert_nur_undo,
)

#: Mindestzahl eigener Fragen je Begriff, ab der die Gegenueberstellung
#: automatisch startet (KORREKTUR-PHASE2-KEIN-KNOPF.md: "Sobald fuer JEDEN
#: Begriff >= 3 eigene Fragen gespeichert sind"). Reine Code-Konstante, keine
#: Nutzertext-Konstante -- deshalb hier und nicht in ``knoepfe/texte.py``.
MINDESTANZAHL_EIGENE_FRAGEN = 3


# --- Die vorgeschlagene Liste und ihr Zustand ------------------------------


def _auswahlfragen(conn, chat_id: int) -> list[str]:
    """Die zuletzt vorgeschlagenen Fragen, eine je Zeile ("Begriff: Frage")."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_auswahl"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    from interview_theater import vorschlag

    return vorschlag.zeilen(roh)


def _setze_frage_zeile(conn, chat_id: int, nummer: int, neuer_text: str) -> None:
    """Ersetzt genau eine Zeile der vorgeschlagenen Liste -- fuer "Schaerfen",
    das nie die ganze Liste neu schreibt."""
    zeilen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(zeilen):
        return
    zeilen[nummer - 1] = neuer_text
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", "\n".join(zeilen))


def _weich_dict(conn, chat_id: int) -> dict[int, str]:
    """``arbeitsstand.fragen_weich`` als ``{Nummer: Text}`` -- derselbe Leser
    wie im Leitfaden (``leitfaden.einleitungen``), weil es dasselbe
    Zeilenformat ist ("<Nummer> — <Text>")."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_weich"] if stand else "") or ""
    except (IndexError, KeyError):
        return {}
    return leitfaden.einleitungen(roh)


def _setze_weich(conn, chat_id: int, zuordnung: dict[int, str]) -> None:
    if not zuordnung:
        repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", None)
        return
    zeilen = [f"{n} — {t}" for n, t in sorted(zuordnung.items())]
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "\n".join(zeilen))


def _decisions(conn, chat_id: int) -> list[str]:
    """Der Entscheidungsstand, eine Position je Zeile aus ``fragen_auswahl``
    -- "ja" / "nein" / "" (noch offen). Kuerzer als die Fragenliste heisst:
    der Rest ist offen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_entschieden"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    if not roh:
        return []
    return roh.split(",")


def _setze_entscheidung(conn, chat_id: int, nummer: int, wert: str) -> None:
    entschieden = _decisions(conn, chat_id)
    while len(entschieden) < nummer:
        entschieden.append("")
    entschieden[nummer - 1] = wert
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", ",".join(entschieden))


def _naechste_offene(conn, chat_id: int, gesamt: int) -> int | None:
    """Die erste Frage ohne Entscheidung, oder None, wenn alle entschieden
    sind."""
    entschieden = _decisions(conn, chat_id)
    for nummer in range(1, gesamt + 1):
        wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
        if not wert:
            return nummer
    return None


def _aktuelle_offene_nummer(conn, chat_id: int) -> int | None:
    """Die Frage, die gerade vorgelegt ist UND noch unentschieden ist --
    genau die Bedingung, unter der eine freie Nachricht als Schaerfungswunsch
    gilt (``nimm_offene_frage_text``). Entschieden heisst: die naechste
    Frage ist schon unterwegs, eine Nachricht dazwischen gehoert nicht mehr
    hierher."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_aktuell"] if stand else "") or ""
    except (IndexError, KeyError):
        return None
    if not roh.strip().isdigit():
        return None
    nummer = int(roh)
    entschieden = _decisions(conn, chat_id)
    wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
    return nummer if not wert else None


def einzeln_aktiv(conn, chat_id: int) -> bool:
    """True, solange die Stufe "Fragen einzeln durchgehen" laeuft --
    ``fragen_aktuell`` traegt eine Fragennummer (Fund 02.10.2026, Padua-Live,
    web_post 73/74: aufnahme 70 lief waehrend genau dieser Stufe und
    ueberschrieb ``arbeitsstand.fragen`` mit der einen gerade geschaerften
    Zeile).

    ``fragen_aktuell`` bleibt gesetzt vom ersten ``starte_durchgehen`` bis
    zur letzten Entscheidung -- auch waehrend einer Schaerfung (Knopfdruck,
    freier Aenderungswunsch, die Modellantwort darauf): genau das Fenster, in
    dem der Erkenner nicht parallel ``fragen`` schreiben darf
    (``erkenner._wende_arbeitsstand_an``) und keine zweite, generische
    Speicherleiste fuer ``fragen`` haengen darf (``erkenner._sende_meldung``)
    -- die Leiste unter der gerade vorgelegten Frage ist die einzige."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_aktuell"] if stand else "") or ""
    except (IndexError, KeyError):
        return False
    return roh.strip().isdigit()


# --- Der Ueberblick ---------------------------------------------------------


def fragenliste(conn, chat_id: int) -> str:
    """Die vorgeschlagenen Fragen ausgeschrieben und nummeriert, eine je
    Zeile, nach Begriffen gruppiert -- unveraendert seit dem 06.09.2026."""
    zeilen: list[str] = []
    letzter_begriff = None
    for nummer, frage in enumerate(_auswahlfragen(conn, chat_id), start=1):
        begriff, trenner, rest = frage.partition(":")
        if trenner and 0 < len(begriff.strip()) <= 30 and rest.strip():
            if begriff.strip() != letzter_begriff:
                letzter_begriff = begriff.strip()
                zeilen.append(("\n" if zeilen else "") + f"{letzter_begriff}")
            zeilen.append(f"{nummer}. {rest.strip()}")
        else:
            zeilen.append(f"{nummer}. {frage}")
    return "\n".join(zeilen)


def _reset_fragenrunde(conn, chat_id: int) -> None:
    """Setzt den Entscheidungsstand einer frischen Fragenrunde zurueck --
    dieselben drei Felder, die ``biete_fragenauswahl`` beim allerersten
    Vorschlag loescht und ``versuche_gegenueberstellung`` beim Reveal der
    Gegenueberstellung (Aufgabe 13): eine Entscheidung zu einer inzwischen
    ersetzten Frage waere bedeutungslos."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)


def biete_fragenauswahl(conn, tg, chat_id: int, wert: str,
                        weich_wert: str | None = None,
                        text: str | None = None) -> int:
    """Legt einen frischen Vorschlag ab und zeigt den Ueberblick mit der
    Richtungsfrage (02.10.2026).

    ``wert`` ist der Inhalt von ``VORSCHLAG FRAGENAUSWAHL:``, ``weich_wert``
    der von ``VORSCHLAG FRAGEN WEICH:`` aus demselben Modellzug (oder None,
    wenn keine Frage sensibel war). Eine neue Runde ersetzt die vorige
    vollstaendig -- Entscheidungsstand und laufende Frage werden
    zurueckgesetzt, eine Entscheidung zu einer inzwischen ersetzten Frage
    waere bedeutungslos."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", wert)
    _setze_weich(
        conn, chat_id, leitfaden.einleitungen(weich_wert) if weich_wert else {},
    )
    _reset_fragenrunde(conn, chat_id)

    vorspann = (text or "").strip()
    nachricht = "\n\n".join(
        teil for teil in (vorspann, fragenliste(conn, chat_id),
                          T._TEXT_FRAGEN_RICHTUNG_FRAGE)
        if teil
    )
    leiste = [
        (T._TEXT_FRAGEN_EINZELN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_EINZELN, None))),
        (T._TEXT_FRAGEN_ANDERE_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_ANDERE, None))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, nachricht, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def frage_fuer_andere_richtung(conn, chat_id: int, richtung: str = "") -> str:
    """Die fertige ``ANWEISUNG_FRAGEN_ANDERE`` -- ein Ort fuer beide Aufrufer
    ("Andere Richtung" mit gesagter Richtung, "keine Frage angenommen" ohne)."""
    alte = _auswahlfragen(conn, chat_id)
    richtung_satz = (
        T._TEXT_FRAGEN_RICHTUNG_SATZ.format(richtung=richtung.strip())
        if richtung.strip() else ""
    )
    return T.ANWEISUNG_FRAGEN_ANDERE.format(
        alte="\n".join(f"- {f}" for f in alte), richtung_satz=richtung_satz,
    )


# --- Eigene Fragen vs. KI (Padua Phase 1+2 Karte, Aufgabe 13, 03.10.2026) ---
#
# KORREKTUR 10:25 (Birk, KORREKTUR-PHASE2-KEIN-KNOPF.md): KEIN "Fertig"-
# Knopf. Sobald JEDER Begriff >= MINDESTANZAHL_EIGENE_FRAGEN eigene Fragen
# hat (reine Code-Pruefung, kein Modellaufruf), startet die
# Gegenueberstellung automatisch; bis dahin eine knappe Stand-Zeile. Will
# die Gruppe frueher weiter, erkennt das ``_fruehzeitig_fertig`` an einem
# woertlichen Satz, den das Padua-Profil-Prompt das Modell sagen laesst --
# keine neue, bezahlte Erkenner-Art.


def _begriffe_der_gruppe(conn, chat_id: int) -> list[str]:
    """``arbeitsstand.begriffe`` zerlegt -- derselbe Leser wie
    ``fragen_ki._nutzertext``, nur ueber die Datenbank statt als
    durchgereichter Parameter."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["begriffe"] if stand else "") or ""
    except (IndexError, KeyError):
        roh = ""
    return begriffe_modul.zerlege(roh)


def _zeilen_je_begriff(begriffe: list[str], zeilen: list[str]) -> dict[str, list[str]]:
    """Gruppiert ``Begriff: Frage``-Zeilen nach den Begriffen der Gruppe --
    case-insensitiver Abgleich wie ``fragenliste()``. Eine Zeile ohne
    passenden Begriff faellt heraus: kein Begriff wird erfunden, keiner
    stillschweigend einem falschen zugeschlagen. Die Rueckgabe normalisiert
    die Gross-/Kleinschreibung des Begriffs auf die Schreibweise der
    Gruppe."""
    je_begriff: dict[str, list[str]] = {b: [] for b in begriffe}
    nachschlag = {b.lower(): b for b in begriffe}
    for zeile in zeilen:
        kopf, trenner, rest = zeile.partition(":")
        if not trenner or not rest.strip():
            continue
        begriff = nachschlag.get(kopf.strip().lower())
        if begriff is None:
            continue
        je_begriff.setdefault(begriff, []).append(f"{begriff}: {rest.strip()}")
    return je_begriff


def _herkunft_liste(conn, chat_id: int) -> list[str]:
    """``arbeitsstand.fragen_herkunft`` als Liste, index-ausgerichtet auf
    ``fragen_auswahl`` -- derselbe Aufbau wie ``_decisions``
    (``fragen_entschieden``). Leer, solange keine Gegenueberstellung lief
    (die klassische Fuenf-je-Begriff-Runde kennt das Feld nicht)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_herkunft"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    if not roh:
        return []
    return roh.split(",")


def _bearbeitet_liste(conn, chat_id: int) -> list[str]:
    """``arbeitsstand.fragen_bearbeitet`` als Liste -- derselbe Aufbau wie
    ``_decisions``/``_herkunft_liste``."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_bearbeitet"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    if not roh:
        return []
    return roh.split(",")


def _markiere_bearbeitet_falls_ki(conn, chat_id: int, nummer: int) -> None:
    """Eine per "Schaerfen" geaenderte KI-Frage wird in
    ``fragen_bearbeitet`` markiert (Aufgabe 13, Punkt 9) -- eine eigene
    Frage NICHT: ihr Edit-Flag bleibt unberuehrt, nur die Herkunft
    entscheidet. Ohne Herkunftsdaten fuer diese Runde (klassischer Ablauf)
    passiert nichts."""
    herkunft = _herkunft_liste(conn, chat_id)
    if nummer > len(herkunft) or herkunft[nummer - 1] != "ki":
        return
    bearbeitet = _bearbeitet_liste(conn, chat_id)
    while len(bearbeitet) < nummer:
        bearbeitet.append("")
    bearbeitet[nummer - 1] = "1"
    repo.setze_arbeitsstand(conn, chat_id, "fragen_bearbeitet", ",".join(bearbeitet))


def _platt(text: str) -> str:
    """Kleinschreibung, Whitespace zu einem Leerzeichen -- fuer den
    case-/whitespace-unabhaengigen Satzvergleich in ``_fruehzeitig_fertig``."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _fruehzeitig_fertig(text: str | None) -> bool:
    """Erkennt den Wunsch der Gruppe, frueher zur Gegenueberstellung zu
    wechseln, bevor jeder Begriff ``MINDESTANZAHL_EIGENE_FRAGEN`` eigene
    Fragen hat (KORREKTUR-PHASE2-KEIN-KNOPF.md: "Will die Gruppe frueher
    weiter (spricht/schreibt es), erkennt das der Erkenner/Chat und startet
    die Gegenueberstellung trotzdem").

    KEIN Modellaufruf und KEINE neue Erkenner-Art hier: das Padua-Profil-
    Prompt (``workshop/padua-2026/prompts/phasen/2.md``) laesst das
    Gespraechsmodell in genau diesem Fall den Satz
    ``T._SATZ_EIGENE_FRAGEN_FRUEHER_FERTIG`` woertlich in seinen Fliesstext
    schreiben -- hier wird nur case-/whitespace-unabhaengig danach
    gesucht."""
    if not text or not text.strip():
        return False
    return _platt(T._SATZ_EIGENE_FRAGEN_FRUEHER_FERTIG) in _platt(text)


#: Schuetzt die Pruefung-dann-Schreiben-Folge in
#: ``versuche_gegenueberstellung`` atomar. Ohne diesen Lock koennten der
#: isolierte KI-Hintergrundlauf (``fragen_ki.starte``) und der
#: Haupt-Gespraechszug (``uebernimm_eigene``) in einer echten Race beide den
#: noch leeren ``fragen_auswahl``-Stand sehen und zweimal offenbaren --
#: genau der Fall, den die Karte als Test verlangt ("Gegenueberstellung
#: laeuft genau einmal"). Ein einziger, globaler Lock statt eines Registers
#: je ``chat_id`` (wie ``fragen_ki._LAEUFT``): der Reveal laeuft genau
#: einmal je Gruppe und ist leichtgewichtig, ein Register waere hier
#: Mehraufwand ohne Nutzen.
_GEGENUEBERSTELLUNG_LOCK = threading.Lock()


def versuche_gegenueberstellung(conn, tg, chat_id: int) -> int | None:
    """Der Gelenkpunkt zwischen den eigenen Fragen der Gruppe
    (``fragen_eigene_vorschlag``) und dem isolierten KI-Lauf
    (``fragen_ki.fragen_ki_vorschlag``, Aufgabe 12) -- Aufgabe 13,
    KORREKTUR-PHASE2-KEIN-KNOPF.md. Reveal nur, wenn BEIDE Seiten stehen;
    wer zuletzt fertig wird, loest ihn aus, indem er genau diese Funktion
    ruft (``fragen_ki.starte`` von der einen Seite, ``uebernimm_eigene`` von
    der anderen).

    Liefert ``None``, wenn (noch) nichts zu offenbaren ist oder der Reveal
    schon gelaufen ist (``fragen_auswahl`` ist dann bereits nicht-leer) --
    danach ist diese Funktion fuer diese Runde ein dauerhaftes No-Op."""
    with _GEGENUEBERSTELLUNG_LOCK:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        if stand is None:
            return None
        try:
            bereits = (stand["fragen_auswahl"] or "").strip()
        except (IndexError, KeyError):
            bereits = ""
        if bereits:
            return None

        try:
            eigene_roh = (stand["fragen_eigene_vorschlag"] or "").strip()
            ki_roh = (stand["fragen_ki_vorschlag"] or "").strip()
            begriffe_feld = (stand["begriffe"] or "") if stand else ""
        except (IndexError, KeyError):
            return None
        if not eigene_roh or not ki_roh:
            return None

        from interview_theater import vorschlag

        begriffe = begriffe_modul.zerlege(begriffe_feld)
        eigene_je_begriff = _zeilen_je_begriff(begriffe, vorschlag.zeilen(eigene_roh))
        ki_je_begriff = _zeilen_je_begriff(begriffe, vorschlag.zeilen(ki_roh))

        zeilen: list[str] = []
        herkunft: list[str] = []
        for begriff in begriffe:
            for zeile in eigene_je_begriff.get(begriff, []):
                zeilen.append(zeile)
                herkunft.append("eigen")
            for zeile in ki_je_begriff.get(begriff, []):
                zeilen.append(zeile)
                herkunft.append("ki")

        repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", "\n".join(zeilen))
        repo.setze_arbeitsstand(conn, chat_id, "fragen_herkunft", ",".join(herkunft))
        _reset_fragenrunde(conn, chat_id)

        # Die EINE kurze Ueberleitungszeile (Korrektur-Wortlaut), danach der
        # bestehende Weg -- ``fragenliste``/``starte_durchgehen`` werden
        # WIEDERVERWENDET, nicht nachgebaut ("explicit reuse the flow"
        # instruction der Karte).
        message_id = tg.sende(chat_id, T._TEXT_GEGENUEBERSTELLUNG_BEREIT)
        starte_durchgehen(conn, tg, chat_id)
        return message_id


def uebernimm_eigene(conn, tg, chat_id: int, wert: str, text: str | None = None) -> int:
    """``VORSCHLAG EIGENE FRAGEN:`` -- die vollstaendige, kumulative eigene
    Fragenliste der Gruppe (Aufgabe 13, KORREKTUR-PHASE2-KEIN-KNOPF.md).
    Ueberschreibt ``fragen_eigene_vorschlag`` bei jedem Aufruf vollstaendig
    -- der Block IST die ganze Liste, kein Zuwachs.

    Danach die Code-Pruefung ohne Modellaufruf: hat jeder Begriff
    mindestens ``MINDESTANZAHL_EIGENE_FRAGEN`` eigene Fragen (oder hat die
    Gruppe explizit frueher Schluss gesagt, ``_fruehzeitig_fertig``), startet
    automatisch die Gegenueberstellung mit den KI-Fragen
    (``versuche_gegenueberstellung``). Sonst eine knappe Stand-Zeile, kein
    Draengen. Kein Modellaufruf hier selbst (Zusage 2)."""
    from interview_theater import vorschlag

    zeilen = vorschlag.zeilen(wert)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_eigene_vorschlag", "\n".join(zeilen))

    begriffe = _begriffe_der_gruppe(conn, chat_id)
    je_begriff = _zeilen_je_begriff(begriffe, zeilen)
    fehlend = [
        b for b in begriffe
        if len(je_begriff.get(b, [])) < MINDESTANZAHL_EIGENE_FRAGEN
    ]
    bereit = not fehlend or _fruehzeitig_fertig(text)

    if not bereit:
        stand_zeile = ", ".join(
            T._TEXT_FRAGEN_EIGENE_OFFEN_ZEILE.format(
                begriff=b, anzahl=len(je_begriff.get(b, [])),
                ziel=MINDESTANZAHL_EIGENE_FRAGEN,
            )
            for b in fehlend
        )
        return tg.sende(
            chat_id, T._TEXT_FRAGEN_EIGENE_OFFEN.format(begriffe=stand_zeile),
        )

    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        schon = bool(stand["fragen_eigene_erstellt_am"]) if stand else False
    except (IndexError, KeyError):
        schon = False
    if not schon:
        repo.setze_arbeitsstand(conn, chat_id, "fragen_eigene_erstellt_am", repo._jetzt())

    ergebnis = versuche_gegenueberstellung(conn, tg, chat_id)
    if ergebnis is not None:
        return ergebnis
    return tg.sende(chat_id, T._TEXT_FRAGEN_EIGENE_WARTET_AUF_KI)


# --- Frage fuer Frage --------------------------------------------------------


def _zeige_frage(conn, tg, chat_id: int, nummer: int) -> int:
    """Legt eine Frage als die aktuelle fest und zeigt sie -- Kopf, Frage,
    darunter Annehmen / Verwerfen / Schaerfen.

    Zeigt die weiche Fassung NICHT mehr pro Frage (Birk, Padua-Live
    02.10.2026: "Warum kommt bei Frage 5/25 ein Vorschlag, es softer zu
    formulieren? Mach die softere Formulierung nicht direkt bei der Frage,
    sondern als Angebot am Ende von allen Fragen.") -- die weiche Fassung
    bleibt in ``arbeitsstand.fragen_weich`` gespeichert und wird erst nach
    der letzten Entscheidung angeboten (``_biete_weiche_fassungen_an``,
    aufgerufen aus ``_schliesse_fragen_ab``).

    Kein Modellaufruf: die Darstellung ist immer deterministisch, auch nach
    einer Ueberarbeitung.

    Haengt seit Aufgabe 13 eine Herkunfts-Kennzeichnung an (" (eure)"/
    " (KI)"), wenn ``arbeitsstand.fragen_herkunft`` fuer diese Runde Daten
    traegt -- reiner Text, kein HTML/``data-*`` (``sichere_html``s feste
    Allowlist). Ohne Herkunftsdaten (jeder Ablauf vor Aufgabe 13, und die
    klassische Fuenf-je-Begriff-Runde, solange ``fragen_ab_aktiv()`` aus
    ist) bleibt die Darstellung BYTE-IDENTISCH zu vorher."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", str(nummer))
    fragen = _auswahlfragen(conn, chat_id)
    gesamt = len(fragen)
    zeile = fragen[nummer - 1]
    begriff, trenner, rest = zeile.partition(":")
    if trenner and rest.strip():
        kopf = T._TEXT_FRAGE_KOPF.format(
            nummer=nummer, gesamt=gesamt, begriff=begriff.strip(),
        )
        frage_text = rest.strip()
    else:
        kopf = T._TEXT_FRAGE_KOPF_OHNE_BEGRIFF.format(nummer=nummer, gesamt=gesamt)
        frage_text = zeile

    herkunft = _herkunft_liste(conn, chat_id)
    if herkunft and nummer <= len(herkunft):
        if herkunft[nummer - 1] == "eigen":
            frage_text += T._TEXT_HERKUNFT_EIGEN
        elif herkunft[nummer - 1] == "ki":
            frage_text += T._TEXT_HERKUNFT_KI

    text = f"{kopf}\n\n{frage_text}"

    leiste = [
        (T._TEXT_FRAGE_ANNEHMEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_ANNEHMEN, str(nummer)))),
        (T._TEXT_FRAGE_VERWERFEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_VERWERFEN, str(nummer)))),
        (T._TEXT_FRAGE_SCHAERFEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGE_SCHAERFEN, str(nummer)))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def starte_durchgehen(conn, tg, chat_id: int) -> bool:
    """"Ja, einzeln durchgehen" -- zeigt Frage 1. Liefert False, wenn es
    nichts zu zeigen gibt (eine ueberholte Nachricht)."""
    if not _auswahlfragen(conn, chat_id):
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
    _zeige_frage(conn, tg, chat_id, 1)
    return True


def frage_warten_auf_richtung(conn, tg, chat_id: int) -> None:
    """"Andere Richtung" -- fragt deterministisch nach der Richtung; die
    naechste freie Nachricht loest den neuen Vorschlag aus
    (``nimm_offene_frage_text``)."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", "richtung")
    tg.sende(chat_id, T._TEXT_FRAGEN_RICHTUNG_GEFRAGT)


def entscheide(conn, tg, klm, e, chat_id: int, nummer: int, wert: str) -> str:
    """Annehmen ("ja") oder Verwerfen ("nein") fuer eine Frage -- zeigt die
    naechste offene Frage, oder schliesst ab, wenn keine mehr offen ist.

    Liefert die sichtbare Quittung (Web-Toast/Telegram
    ``answerCallbackQuery``) -- seit dem Fund 02.10.2026 (Birk) die
    tatsaechliche Entscheidung (``✓ Angenommen``/``✗ Verworfen``) statt des
    vorher immer gleichen, nichtssagenden ``T._TEXT_FRAGE_ENTSCHIEDEN``
    ("Notiert")."""
    fragen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(fragen):
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return T._TEXT_FRAGEN_KEINE_AUSWAHL
    _setze_entscheidung(conn, chat_id, nummer, wert)
    quittung = T._TEXT_FRAGE_ANGENOMMEN if wert == "ja" else T._TEXT_FRAGE_VERWORFEN
    naechste = _naechste_offene(conn, chat_id, len(fragen))
    if naechste is None:
        _schliesse_fragen_ab(conn, tg, klm, e, chat_id)
        return quittung
    _zeige_frage(conn, tg, chat_id, naechste)
    return quittung


def frage_waehlt_schaerfen(conn, tg, chat_id: int, nummer: int) -> str:
    """"Schaerfen" -- fragt deterministisch, was sich aendern soll. Die
    Antwort kommt als normale Nachricht und wird ueber
    ``nimm_offene_frage_text`` abgefangen, weil ``fragen_aktuell`` hier
    defensiv (erneut) auf diese Frage gesetzt wird -- derselbe Schutz wie
    eine aus Versehen verschobene Reihenfolge."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", str(nummer))
    tg.sende(chat_id, T._TEXT_FRAGE_WAS_AENDERN)
    return T._TEXT_FRAGE_WAS_AENDERN


def _starte_schaerfung(conn, tg, klm, e, chat_id: int, nummer: int, wunsch: str) -> None:
    fragen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(fragen):
        return
    frage = fragen[nummer - 1]
    weich = _weich_dict(conn, chat_id).get(nummer, "")
    sensibel_hinweis = (
        T._TEXT_FRAGE_SCHAERFEN_SENSIBEL_HINWEIS.format(weich=weich) if weich else ""
    )
    anweisung = T.ANWEISUNG_FRAGE_SCHAERFEN.format(
        nummer=nummer, frage=frage, wunsch=wunsch, sensibel_hinweis=sensibel_hinweis,
    )
    _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)


def uebernimm_schaerfung(conn, tg, chat_id: int, frage_block: str,
                         weich_block: str | None) -> int:
    """Die Antwort auf eine Schaerfung: ersetzt genau die aktuelle Frage
    (Text und, falls vorhanden, ihre weiche Fassung) und zeigt sie wieder --
    erst Annehmen oder Verwerfen bringt die naechste.

    Liefert die ``message_id`` der neu gezeigten (oder der Fehler-)Nachricht,
    NICHT den Quittungstext (Fund 02.10.2026, Padua-Live: ``basis.
    sende_mit_speicherleiste`` reicht genau diesen Rueckgabewert als
    ``message_id`` an ``repo.merke_nachricht`` weiter -- ein Text statt einer
    Zahl landete dort in der Spalte ``message_id``, SQLite sortiert TEXT ueber
    jedem INTEGER, und ``erkenner.erkenne`` (``max(n[\"message_id\"] ...)``)
    stolperte seitdem bei JEDEM Lauf dieser Gruppe ueber einen TypeError --
    der Erkenner blieb fuer die Gruppe fuer immer stumm)."""
    from interview_theater import vorschlag

    nummer = _aktuelle_offene_nummer(conn, chat_id)
    if nummer is None:
        return tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
    zeilen = vorschlag.zeilen(frage_block)
    neue_frage = zeilen[0] if zeilen else frage_block.strip()
    if neue_frage:
        _setze_frage_zeile(conn, chat_id, nummer, neue_frage)
        # Aufgabe 13, Punkt 9: eine editierte KI-Frage wird markiert, eine
        # eigene Frage nicht -- ``_markiere_bearbeitet_falls_ki`` ist selbst
        # das No-Op ohne Herkunftsdaten (klassischer Ablauf).
        _markiere_bearbeitet_falls_ki(conn, chat_id, nummer)
    weich = _weich_dict(conn, chat_id)
    neue_weich = leitfaden.einleitungen(weich_block).get(nummer) if weich_block else None
    if neue_weich:
        weich[nummer] = neue_weich
    else:
        weich.pop(nummer, None)
    _setze_weich(conn, chat_id, weich)
    return _zeige_frage(conn, tg, chat_id, nummer)


def nimm_offene_frage_text(conn, tg, klm, e, chat_id: int, text: str) -> bool:
    """Die deterministische Weiche fuer eine freie Nachricht in Phase 2
    (aufgerufen aus ``ablauf._war_die_erwartete_antwort`` wie zuvor
    ``nimm_fragennummern``). Liefert True, wenn die Nachricht hier verarbeitet
    wurde -- dann geht sie NICHT zusaetzlich in den Gespraechszug.

    Zwei Faelle, beide ohne Erkenner-Lauf (kein Modellaufruf nur zum
    Klassifizieren):

    1. Nach "Andere Richtung" wartet ``fragen_warte_auf == 'richtung'`` --
       die Nachricht ist die gewuenschte Richtung.
    2. Steht eine Frage aktuell und unentschieden da, ist die Nachricht ihr
       Schaerfungswunsch -- mit oder ohne vorherigen Druck auf "Schaerfen"."""
    text = (text or "").strip()
    if not text:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return False
    try:
        warte = (stand["fragen_warte_auf"] or "").strip()
    except (IndexError, KeyError):
        warte = ""
    if warte == "richtung":
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
        anweisung = frage_fuer_andere_richtung(conn, chat_id, richtung=text)
        _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)
        return True

    nummer = _aktuelle_offene_nummer(conn, chat_id)
    if nummer is not None:
        _starte_schaerfung(conn, tg, klm, e, chat_id, nummer, text)
        return True
    return False


def _schliesse_fragen_ab(conn, tg, klm, e, chat_id: int) -> str:
    """Alle Fragen sind entschieden: aus den angenommenen wird
    ``arbeitsstand.fragen``, ihre weichen Fassungen wandern auf die neue
    Nummerierung um -- und die Kette geht weiter zur Eroeffnung. Ohne eine
    einzige Annahme gibt es keine Frageliste; stattdessen sagt der Bot das
    und schlaegt neue Fragen vor.

    Hat mindestens eine angenommene Frage eine weiche Fassung, kommt VOR der
    Eroeffnung noch ein eigenes Angebot (``_biete_weiche_fassungen_an``,
    Birk 02.10.2026) -- die Eroeffnung startet dann erst, wenn die Gruppe
    das Angebot beantwortet hat (``fragen_weich_angebot`` in
    ``_WEICH_ANGEBOT_WIRKUNGEN``).

    Baut seit Aufgabe 13 ``fragen_herkunft_final`` im selben Durchgang wie
    ``angenommen`` -- Laenge und Indexreihenfolge identisch zu ``fragen``
    (Task 14 haengt genau daran). Ohne Herkunftsdaten fuer diese Runde
    (klassischer Ablauf) ist jeder Eintrag ein leerer String."""
    fragen = _auswahlfragen(conn, chat_id)
    entschieden = _decisions(conn, chat_id)
    weich = _weich_dict(conn, chat_id)
    herkunft = _herkunft_liste(conn, chat_id)

    angenommen: list[str] = []
    herkunft_final: list[str] = []
    neue_weich: dict[int, str] = {}
    for i, frage in enumerate(fragen, start=1):
        if i <= len(entschieden) and entschieden[i - 1] == "ja":
            angenommen.append(frage)
            herkunft_final.append(herkunft[i - 1] if i <= len(herkunft) else "")
            if i in weich:
                neue_weich[len(angenommen)] = weich[i]

    if not angenommen:
        repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_ANGENOMMEN)
        anweisung = frage_fuer_andere_richtung(conn, chat_id)
        _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)
        return T._TEXT_FRAGEN_KEINE_ANGENOMMEN

    wert = "\n".join(angenommen)

    def _schreibe():
        repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
        repo.setze_arbeitsstand(conn, chat_id, "fragen", wert)
        repo.setze_arbeitsstand(
            conn, chat_id, "fragen_herkunft_final", ",".join(herkunft_final),
        )
        if neue_weich:
            _setze_weich(conn, chat_id, neue_weich)
        else:
            # Leerer String, nicht NULL: "keine der Fragen ist sensibel" ist
            # ein Ergebnis der Pruefung, kein fehlender Wert
            # (``phasen._feld_geprueft``) -- sonst haelt die leere Pruefung
            # Phase 3 fuer immer zurueck.
            repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")

    text = (
        T._TEXT_FRAGEN_ABGESCHLOSSEN.format(anzahl=len(angenommen)) + "\n"
        + "\n".join(f"{n}. {f}" for n, f in enumerate(angenommen, start=1))
    )
    # Derselbe Undo-Knopf wie unter "Ja, speichern" (UX-Knoepfe-Karte,
    # Abschnitt 2): ein Druck macht die Fragen wieder zum offenen, einzeln
    # entschiedenen Zustand -- nicht nur leer.
    lauf_id = erkenner.lauf_fuer_knopf(conn, e, chat_id, text, _schreibe)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_FRAGEN.format(wert=wert),
        quelle="knopf",
    )
    if lauf_id is None:
        tg.sende(chat_id, text, system=True)
    else:
        sende_notiert_nur_undo(conn, tg, chat_id, text, lauf_id)
    if neue_weich:
        _biete_weiche_fassungen_an(conn, tg, angenommen, neue_weich, chat_id)
    else:
        starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_QUITTUNG


def _biete_weiche_fassungen_an(
    conn, tg, angenommen: list[str], neue_weich: dict[int, str], chat_id: int,
) -> int:
    """Das Angebot nach der letzten Entscheidung, EINMAL fuer alle sensiblen
    Fragen zusammen (Birk, Padua-Live 02.10.2026): listet jede angenommene
    Frage mit weicher Fassung auf, mit den zwei Knoepfen "Weiche Fassungen
    uebernehmen" / "Wie sie sind lassen". Erst die Antwort darauf setzt die
    Kette zur Eroeffnung fort (``_wirkung_fragen_weich_*`` in wirkung.py)."""
    zeilen = [
        T._TEXT_FRAGEN_WEICH_ZEILE.format(
            nummer=n, frage=angenommen[n - 1], weich=weich,
        )
        for n, weich in sorted(neue_weich.items())
    ]
    text = T._TEXT_FRAGEN_WEICH_ANGEBOT + "\n\n" + "\n\n".join(zeilen)
    leiste = [
        (T._TEXT_FRAGEN_WEICH_UEBERNEHMEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_WEICH_UEBERNEHMEN, None))),
        (T._TEXT_FRAGEN_WEICH_LASSEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_WEICH_LASSEN, None))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id,
    )
    return message_id


def frage_weich_uebernehmen(conn, tg, klm, e, chat_id: int) -> str:
    """"Weiche Fassungen uebernehmen" -- ``fragen_weich`` bleibt stehen (der
    Leitfaden nutzt es bereits, siehe ``leitfaden.py``); nur die Kette geht
    jetzt weiter."""
    starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_WEICH_UEBERNOMMEN


def frage_weich_lassen(conn, tg, klm, e, chat_id: int) -> str:
    """"Wie sie sind lassen" -- die Fragen bleiben in der Originalformulierung,
    ``fragen_weich`` wird geleert, damit der Leitfaden keine weichen
    Fassungen mehr zeigt, die die Gruppe explizit abgelehnt hat."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_weich", "")
    starte_eroeffnung(conn, tg, klm, e, chat_id)
    return T._TEXT_FRAGEN_WEICH_BEHALTEN


# --- Eroeffnung und Abschluss (unveraendert seit dem 06.09.2026) ----------


def starte_eroeffnung(conn, tg, klm, e, chat_id: int) -> bool:
    """Der Schritt nach den Fragen: Eroeffnungs- und Abschlusstext. Laeuft
    automatisch, sobald die Frageliste steht -- wieder ein Auftragszug im
    eigenen Thread, wieder die Grundleiste darunter."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    fragen = (stand["fragen"] if stand else "") or ""
    return _starte_auftrag(
        conn, tg, klm, e, chat_id,
        anweisungen.fuelle(T.ANWEISUNG_EROEFFNUNG).format(fragen=fragen),
        arbeitszeile=T.TEXT_ARBEIT_EROEFFNUNG, arbeitsart="eroeffnung",
    )


def _speichere_eroeffnung(conn, tg, chat_id: int, wert: str, e=None, klm=None) -> str:
    """Zerlegt den Block ``VORSCHLAG EROEFFNUNG:`` in Eroeffnung und
    Abschluss und legt beides ab. Unveraendert seit dem 06.09.2026."""
    import re

    eroeffnung: list[str] = []
    abschluss: list[str] = []
    ziel = eroeffnung
    for zeile in (wert or "").splitlines():
        roh = zeile.strip()
        if not roh:
            continue
        ohne = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", roh)
        kopf, sep, rest = ohne.partition(":")
        if sep and kopf.strip().lower().startswith(("abschluss", "closing")):
            ziel = abschluss
            if rest.strip():
                ziel.append(rest.strip())
            continue
        if sep and kopf.strip().lower().startswith(("eroeffnung", "opening")):
            ziel = eroeffnung
            if rest.strip():
                ziel.append(rest.strip())
            continue
        ziel.append(ohne)
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung", "\n".join(eroeffnung).strip() or None
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", "\n".join(abschluss).strip() or None
    )
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_EROEFFNUNG_FESTGELEGT,
        quelle="knopf",
    )
    leitfaden.sende_einmal(conn, tg, chat_id, e=e)
    from interview_theater.knoepfe.stationen import (
        biete_phase_proaktiv, uebergang_nach_speichern,
    )

    if not uebergang_nach_speichern(conn, tg, klm, e, chat_id):
        biete_phase_proaktiv(conn, tg, chat_id)
    return T._TEXT_EROEFFNUNG_QUITTUNG


def _leitfaden_knopf(conn, chat_id: int) -> tuple[str, str] | None:
    """"Leitfaden zeigen", sobald es einen gibt -- sonst None."""
    if not leitfaden.steht(conn, chat_id):
        return None
    return (
        T._TEXT_LEITFADEN_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_LEITFADEN, None)),
    )

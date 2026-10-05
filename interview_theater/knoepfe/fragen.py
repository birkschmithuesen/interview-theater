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

from interview_theater import anweisungen, erkenner, fragen_auswertung, leitfaden, repo, workshop
from interview_theater import begriffe as begriffe_modul

from interview_theater.knoepfe.texte import (
    ART_FRAGE_ANNEHMEN, ART_FRAGE_SCHAERFEN, ART_FRAGE_VERWERFEN,
    ART_FRAGEN_ANDERE, ART_FRAGEN_EINZELN, ART_FRAGEN_JA_VORSCHLAGEN,
    ART_FRAGEN_NOCH_EIGENE, ART_FRAGEN_VORSCHLAGEN, ART_FRAGEN_WEICH_LASSEN,
    ART_FRAGEN_WEICH_UEBERNEHMEN, ART_LEITFADEN, T,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _merke_botnachricht, _nimm_alte_leiste_ab, _sende_knoepfe,
    _starte_auftrag, sende_notiert_nur_undo,
)

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
    if not workshop.fragen_weich_aktiv():
        return {}
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_weich"] if stand else "") or ""
    except (IndexError, KeyError):
        return {}
    return leitfaden.einleitungen(roh)


def _setze_weich(conn, chat_id: int, zuordnung: dict[int, str]) -> None:
    # Abgeschaltet (Padua): nichts speichern, auch wenn ein Modell den Block
    # doch liefert -- sonst taucht er spaeter im Leitfaden wieder auf.
    if not workshop.fragen_weich_aktiv():
        zuordnung = {}
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
    sind. "schaerfen" (in der Sortierliste des CoThinkers markiert, Padua
    05.10.2026) ist noch keine Entscheidung."""
    entschieden = _decisions(conn, chat_id)
    for nummer in range(1, gesamt + 1):
        wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
        if _ist_offen(wert):
            return nummer
    return None


def _ist_offen(wert: str) -> bool:
    """Offen ist eine Position ohne Wert oder mit "schaerfen" -- nur "ja"
    und "nein" sind entschieden."""
    return not wert or wert == "schaerfen"


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
    return nummer if _ist_offen(wert) else None


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
    ersetzten Frage waere bedeutungslos.

    Loescht seit dem Abschluss-Review des Phase-1+2-Umbaus auch
    ``fragen_herkunft``/``fragen_bearbeitet``: ohne das ueberlebt die
    Herkunftskennzeichnung einer Gegenueberstellung eine spaetere frische
    KLASSISCHE Fragenrunde -- Szenario "Andere Richtung" nach einer
    Gegenueberstellung, in der JEDE Frage verworfen wurde
    (``_schliesse_fragen_ab`` ruft dann ``frage_fuer_andere_richtung`` ->
    ``_starte_auftrag``, der naechste Vorschlag laeuft ueber
    ``biete_fragenauswahl``, NICHT ueber ``uebernimm_eigene``/
    ``versuche_gegenueberstellung``). Ohne diese Zeile zeigte
    ``_zeige_frage`` die alten, index-falschen " (eure)"/" (KI)"-Marken auf
    voellig unabhaengigen neuen Fragen, und ``_schliesse_fragen_ab`` haette
    ``fragen_herkunft_final`` aus Indizes gebaut, die nicht mehr zu
    denselben Fragen gehoeren -- das korrumpiert Aufgabe 14s Auswertung.
    ``versuche_gegenueberstellung`` ruft diese Funktion deshalb VOR dem
    Setzen des frischen ``fragen_herkunft`` fuer ihre eigene Runde auf, nicht
    danach."""
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_herkunft", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_bearbeitet", None)


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
    return _ohne_weich_auftrag(T.ANWEISUNG_FRAGEN_ANDERE.format(
        alte="\n".join(f"- {f}" for f in alte), richtung_satz=richtung_satz,
    ))


def _ohne_weich_auftrag(anweisung: str) -> str:
    """Nimmt den Auftrag zur weichen Fassung (``_ANWEISUNG_FRAGEN_SENSIBEL``)
    aus einer fertigen Anweisung, wenn das Profil ihn abschaltet
    (``workshop.fragen_weich_aktiv``). Der Baustein haengt in beiden
    Anweisungen am Ende, ohne Platzhalter -- ein reines Herausschneiden."""
    if workshop.fragen_weich_aktiv():
        return anweisung
    return anweisung.replace(T._ANWEISUNG_FRAGEN_SENSIBEL, "").rstrip() + "\n"


# --- Eigene Fragen vs. KI (Padua Phase 1+2 Karte, Aufgabe 13, 03.10.2026) ---
#
# KORREKTUR 10:25 (Birk, KORREKTUR-PHASE2-KEIN-KNOPF.md): KEIN "Fertig"-
# Knopf. Seit dem Live-Test 05.10.2026 (Birk: "Anzahl entscheidet die
# Gruppe") auch keine Mindestzahl je Begriff mehr: die Gegenueberstellung
# startet, wenn die Gruppe sagt, dass sie fertig ist -- ``_fruehzeitig_fertig``
# erkennt das an einem woertlichen Satz, den das Padua-Profil-Prompt das
# Modell sagen laesst (keine neue, bezahlte Erkenner-Art). Was je Begriff
# schon steht, zeigt der CoThinker (``roadmap.fragenuebersicht``), nicht der
# Chat.


#: Feedbackloop P1-2, P2-H2 (05.10.2026): was ein Modell um den Begriff herum
#: schreibt, ohne dass es zum Begriff gehoert -- Markdown-Hervorhebung und
#: Anfuehrungszeichen aller Art.
_KOPF_ZIERDE = re.compile(r"[*_`\"'“”‘’«»„‚]")
#: Trenner zwischen Begriff und Frage, in dieser Reihenfolge versucht: der
#: verlangte Doppelpunkt, dann die Gedankenstriche, die Modelle stattdessen
#: setzen (nur mit Leerzeichen drumherum -- "Self-image" bleibt ein Wort).
_TRENNER = (":", " – ", " — ", " -- ", " - ")
_ARTIKEL = ("the ", "a ", "an ")
#: Ein Begriffskopf ist kurz; alles Laengere ist ein Satz, in dem zufaellig
#: ein Doppelpunkt steht.
_KOPF_MAX = 60


def _kopf_max(begriffe: list[str]) -> int:
    """``_KOPF_MAX``, aber nie kuerzer als der laengste Begriff der Gruppe
    (Live G2, 05.10.2026: ein Begriff mit 78 Zeichen fand nie seine
    Fragen)."""
    return max([_KOPF_MAX] + [len(b) + 10 for b in begriffe])


def _kopfform(text: str) -> str:
    """Ein Begriffskopf in Vergleichsform: ohne Zierde, klein, Whitespace
    zu einem Leerzeichen, ohne Satzzeichen am Rand und ohne fuehrenden
    englischen Artikel."""
    roh = _platt(_KOPF_ZIERDE.sub("", text or "")).strip(" .,;:!?-–—")
    for artikel in _ARTIKEL:
        if roh.startswith(artikel):
            roh = roh[len(artikel):]
            break
    return roh


def _gleich(a: str, b: str) -> bool:
    """Gleich bis auf ein Plural-s ("robot"/"robots", "box"/"boxes")."""
    return a == b or a + "s" == b or b + "s" == a or a + "es" == b or b + "es" == a


def _finde_begriff(kopf: str, begriffe: list[str]) -> str | None:
    """Der Begriff der Gruppe, den ``kopf`` meint -- oder None. Erst
    Gleichheit (bis auf Zierde, Gross-/Kleinschreibung, Artikel, Plural-s),
    dann ein Begriff mit angehaengter Klammer ("Home (term 3)"); bei
    mehreren Treffern gewinnt der laengste Begriff. Kein Enthalten-Abgleich
    im Satz: "Tell me about home" ist eine Frage, kein Kopf."""
    if not kopf.strip() or len(kopf) > _kopf_max(begriffe):
        return None
    form = _kopfform(kopf)
    if not form:
        return None
    # Genaue Gleichheit vor Plural: bei "robot" UND "robots" gehoert
    # "Robot:" zu "robot".
    treffer = ([b for b in begriffe if form == _kopfform(b)]
               or [b for b in begriffe if _gleich(form, _kopfform(b))])
    if not treffer:
        ohne_klammer = _kopfform(re.sub(r"\s*[(\[].*$", "", form))
        if ohne_klammer and ohne_klammer != form:
            treffer = ([b for b in begriffe if ohne_klammer == _kopfform(b)]
                       or [b for b in begriffe if _gleich(ohne_klammer, _kopfform(b))])
    if not treffer:
        return None
    return max(treffer, key=len)


def _teile_zeile(zeile: str, begriffe: list[str]) -> tuple[str | None, str]:
    """(Begriff, Frage) einer Zeile -- der erste Trenner, dessen Kopf ein
    Begriff ist, gewinnt. Ohne passenden Kopf ``(None, zeile)``.

    Padua G3 (05.10.2026): ein Begriff, der selbst einen Doppelpunkt traegt
    ("EVENTO: dall'esterno all'interno"), scheiterte am ersten Trenner -- der
    Kopf "EVENTO" ist kein Begriff. Deshalb zuerst jedes Vorkommen jedes
    Trenners pruefen, der laengste Kopf, der ein Begriff ist, gewinnt."""
    treffer: tuple[int, str, str] | None = None
    for trenner in _TRENNER:
        pos = zeile.find(trenner)
        while 0 < pos <= _kopf_max(begriffe):
            begriff = _finde_begriff(zeile[:pos], begriffe)
            if begriff is not None and (treffer is None or pos > treffer[0]):
                treffer = (pos, begriff, zeile[pos + len(trenner):])
            pos = zeile.find(trenner, pos + 1)
    if treffer is None:
        return None, zeile
    _, begriff, rest = treffer
    # "**Home:** Frage" laesst die schliessenden Sternchen im Rest.
    return begriff, re.sub(r"^[\s*_]+", "", rest).strip()


def _ist_fortsetzung(zeile: str, vorige: str) -> bool:
    """Eine umbrochene Frage (das Beispiel im Prompt ist selbst umbrochen):
    die vorige Zeile endet nicht mit einem Satzzeichen UND diese beginnt
    klein -- eine Aufzaehlung unpunktierter Fragen bleibt getrennt."""
    return bool(zeile) and zeile[0].islower() and vorige.rstrip()[-1:] not in ".?!…"


def _hat_fremden_kopf(zeile: str) -> bool:
    """Die Zeile traegt selbst einen kurzen Kopf ("Family: ...") -- einen
    Begriff, den die Gruppe nicht hat. Sie gehoert dann nicht unter die
    vorige Ueberschrift."""
    kopf, trenner, rest = zeile.partition(":")
    kopf = kopf.strip()
    return bool(trenner and rest.strip() and kopf and len(kopf) <= 30
                and len(kopf.split()) <= 4)


def _ordne_zeilen(begriffe: list[str], zeilen: list[str]
                  ) -> tuple[dict[str, list[str]], list[str]]:
    """Ordnet Fragezeilen den Begriffen der Gruppe zu -- tolerant gegenueber
    echter Modellausgabe (Feedbackloop P1-2, P2-H2: der exakte Praefix
    "<Begriff>: " liess KI-Fragen aus dem A/B-Vergleich fallen).

    Erkannt werden ``Begriff: Frage`` mit Zierde (fett, Anfuehrungszeichen),
    anderer Schreibung, Artikel, Plural-s oder Gedankenstrich statt
    Doppelpunkt; eine Zwischenueberschrift (Zeile nur mit dem Begriff), unter
    der die Fragen ohne Kopf folgen; eine umbrochene Frage als Fortsetzung der
    vorigen. Liefert ``(je_begriff, rest)``: ``rest`` sind die Zeilen ohne
    erkennbaren Begriff -- kein Begriff wird erfunden, keine Frage einem
    falschen zugeschlagen, aber auch keine weggeworfen."""
    je_begriff: dict[str, list[str]] = {b: [] for b in begriffe}
    rest: list[str] = []
    aktuell: str | None = None
    letzte: list[str] | None = None  # die Liste, in der die vorige Frage steht
    for zeile in zeilen:
        zeile = zeile.strip()
        if not zeile:
            continue
        begriff, frage = _teile_zeile(zeile, begriffe)
        if begriff is None and _finde_begriff(zeile, begriffe) is not None:
            begriff, frage = _finde_begriff(zeile, begriffe), ""
        if begriff is not None:
            if frage:
                je_begriff[begriff].append(f"{begriff}: {frage}")
                letzte = je_begriff[begriff]
                # Nur eine Zwischenueberschrift nimmt kopflose Zeilen auf;
                # nach "Begriff: Frage" gehoert eine kopflose Zeile niemandem.
                aktuell = None
            else:
                aktuell = begriff  # Zwischenueberschrift
                letzte = None
            continue
        if letzte and _ist_fortsetzung(zeile, letzte[-1]):
            letzte[-1] = f"{letzte[-1]} {zeile}"
        elif aktuell is not None and not _hat_fremden_kopf(zeile):
            je_begriff[aktuell].append(f"{aktuell}: {zeile}")
            letzte = je_begriff[aktuell]
        else:
            rest.append(zeile)
            letzte = rest
    return je_begriff, rest


def _zeilen_je_begriff(begriffe: list[str], zeilen: list[str]) -> dict[str, list[str]]:
    """Die Zeilen je Begriff aus ``_ordne_zeilen``, in der Schreibweise der
    Gruppe -- ohne die Zeilen, die keinem Begriff zuzuordnen sind."""
    return _ordne_zeilen(begriffe, zeilen)[0]


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
    """Erkennt, dass die Gruppe mit ihren eigenen Fragen fertig ist und zur
    Gegenueberstellung will (KORREKTUR-PHASE2-KEIN-KNOPF.md; seit dem
    05.10.2026 der einzige Ausloeser -- es gibt keine Mindestzahl je Begriff
    mehr, die Anzahl entscheidet die Gruppe).

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
            eigene_fertig = bool(stand["fragen_eigene_erstellt_am"])
        except (IndexError, KeyError):
            return None
        # Die eigene Seite steht erst, wenn die Gruppe fertig gesagt hat
        # (``uebernimm_eigene`` setzt dann ``fragen_eigene_erstellt_am``) --
        # nicht schon mit der ersten eigenen Frage. Sonst offenbarte ein
        # spaet fertiger KI-Lauf mitten ins Sammeln hinein (05.10.2026: seit
        # es keine Mindestzahl mehr gibt, ist "fertig" allein ihre Ansage).
        # Ohne eine einzige eigene Frage geht es nur, wenn die Gruppe das
        # ausdruecklich will ("Yes, suggest some", ``ja_vorschlagen``) -- dann
        # stehen allein die KI-Fragen da.
        if not ki_roh or not eigene_fertig:
            return None
        # Live Padua 05.10.2026 (G3): ein KI-Vorschlag zu inzwischen
        # verworfenen Begriffen wird nicht offenbart -- der Aufrufer
        # (``_eigene_fertig``) stoesst dann einen neuen Lauf an.
        from interview_theater import fragen_ki, vorschlag as _v

        if not fragen_ki.passt_zu_begriffen(begriffe_feld, _v.zeilen(ki_roh)):
            return None

        from interview_theater import vorschlag

        begriffe = begriffe_modul.zerlege(begriffe_feld)
        eigene_je_begriff, eigene_rest = _ordne_zeilen(begriffe, vorschlag.zeilen(eigene_roh))
        ki_je_begriff, ki_rest = _ordne_zeilen(begriffe, vorschlag.zeilen(ki_roh))

        zeilen: list[str] = []
        herkunft: list[str] = []
        for begriff in begriffe:
            for zeile in eigene_je_begriff.get(begriff, []):
                zeilen.append(zeile)
                herkunft.append("eigen")
            for zeile in ki_je_begriff.get(begriff, []):
                zeilen.append(zeile)
                herkunft.append("ki")
        # P2-H2: was keinem Begriff zuzuordnen ist, steht am Ende, so wie es
        # kam -- verloren geht keine Frage.
        for zeile in eigene_rest:
            zeilen.append(zeile)
            herkunft.append("eigen")
        for zeile in ki_rest:
            zeilen.append(zeile)
            herkunft.append("ki")
        if not zeilen:
            # Nichts zu vergleichen: nicht offenbaren. Eine leere
            # ``fragen_auswahl`` liefe in "I don't know this selection any
            # more" -- und bei jedem weiteren Versuch wieder.
            return None

        repo.setze_arbeitsstand(conn, chat_id, "fragen_auswahl", "\n".join(zeilen))
        # Reset VOR dem Setzen von fragen_herkunft: seit dem Abschluss-Review
        # loescht _reset_fragenrunde das Feld mit -- in umgekehrter
        # Reihenfolge wuerde es die Herkunft fuer diese Runde sofort wieder
        # wegwerfen, die gerade erst gebaut wurde.
        _reset_fragenrunde(conn, chat_id)
        repo.setze_arbeitsstand(conn, chat_id, "fragen_herkunft", ",".join(herkunft))

        # R-3: "Suggest questions" (an der Wartezeile) und "We have more /
        # Yes, suggest some" haben ab hier nichts mehr zu tun.
        _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_VORSCHLAGEN)
        _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_JA_VORSCHLAGEN)

        # Die EINE kurze Ueberleitungszeile (Korrektur-Wortlaut), danach der
        # bestehende Weg -- ``fragenliste``/``starte_durchgehen`` werden
        # WIEDERVERWENDET, nicht nachgebaut ("explicit reuse the flow"
        # instruction der Karte).
        bereit = T._TEXT_GEGENUEBERSTELLUNG_BEREIT
        if workshop.diskussion_aktiv():
            bereit += "\n\n" + T._TEXT_FRAGEN_COTHINKER_HINWEIS
        message_id = tg.sende(chat_id, bereit)
        starte_durchgehen(conn, tg, chat_id, hinweis=False)
        return message_id


#: Fund P2-H6 (Birk, 05.10.2026 13:25): die beiden Marker, mit denen das
#: Padua-Phase-2-Prompt (``workshop/padua-2026/prompts/phasen/2.md``) eine
#: ausdrueckliche Aenderung bzw. Loeschung einer BESTEHENDEN eigenen Frage
#: kennzeichnet -- jede Zeile ohne einen dieser Marker ist eine NEUE Frage,
#: die angehaengt wird, nie ein Ersatz fuer eine bestehende.
_EIGENE_AENDERN = re.compile(r"^change\s*:\s*", re.IGNORECASE)
_EIGENE_LOESCHEN = re.compile(r"^delete\s*:\s*", re.IGNORECASE)
_EIGENE_AENDERN_PFEIL = re.compile(r"\s*(?:->|→)\s*")


def _mische_eigene_fragen(bestehend: list[str], neue_zeilen: list[str]) -> list[str]:
    """Haengt ``neue_zeilen`` additiv an ``bestehend`` an (Fund P2-H6): eine
    bestehende Zeile bleibt zeichengleich stehen, ausser eine Zeile aus
    ``neue_zeilen`` markiert ausdruecklich ``CHANGE: <alter Fragetext> ->
    <Begriff>: <neuer Fragetext>`` oder ``DELETE: <alter Fragetext>`` --
    der alte Fragetext wird case-/whitespace-unabhaengig gegen den
    Fragetext jeder bestehenden Zeile geprueft (``_fragetext``, derselbe
    Vergleich wie bei einer Schaerfung). Eine Zeile ohne passenden Treffer
    (Tippfehler im Marker, falsch zitierter alter Text) aendert nichts --
    raten ist hier so verboten wie beim Vorschlagsmarker selbst
    (``vorschlag.py``). Eine neue Zeile, deren Fragetext schon vorkommt,
    wird nicht doppelt angehaengt."""
    ergebnis = list(bestehend)
    for zeile in neue_zeilen:
        zeile = zeile.strip()
        if not zeile:
            continue
        loeschen = _EIGENE_LOESCHEN.match(zeile)
        if loeschen:
            ziel = _platt(zeile[loeschen.end():])
            ergebnis = [z for z in ergebnis if _fragetext(z) != ziel]
            continue
        aendern = _EIGENE_AENDERN.match(zeile)
        if aendern:
            rest = zeile[aendern.end():]
            pfeil = _EIGENE_AENDERN_PFEIL.search(rest)
            if not pfeil:
                continue
            ziel = _platt(rest[:pfeil.start()])
            neue_fassung = rest[pfeil.end():].strip()
            if not neue_fassung:
                continue
            for i, z in enumerate(ergebnis):
                if _fragetext(z) == ziel:
                    ergebnis[i] = neue_fassung
                    break
            continue
        if not any(_fragetext(z) == _fragetext(zeile) for z in ergebnis):
            ergebnis.append(zeile)
    return ergebnis


def uebernimm_eigene(conn, tg, chat_id: int, wert: str, text: str | None = None) -> int:
    """``VORSCHLAG EIGENE FRAGEN:`` -- Zuwachs zur eigenen Fragenliste der
    Gruppe (Aufgabe 13, KORREKTUR-PHASE2-KEIN-KNOPF.md; additive Semantik
    seit Fund P2-H6, Birk 05.10.2026 13:25).

    Der Block traegt NICHT mehr die ganze kumulative Liste (das Modell gab
    sie beim Nacherzaehlen irgendwann unvollstaendig zurueck -- ein von der
    Gruppe entfernter Begriff kam so zurueck, zwei eigene Fragen
    verschwanden spurlos). Stattdessen haengt der CODE neue Zeilen an
    ``fragen_eigene_vorschlag`` an (``_mische_eigene_fragen``); eine
    bestehende Frage behaelt den exakten Wortlaut der Gruppe, es sei denn,
    eine Zeile traegt ausdruecklich ``CHANGE: ... -> Begriff: ...`` oder
    ``DELETE: ...`` (passend zum Padua-Prompt,
    ``workshop/padua-2026/prompts/phasen/2.md``).

    Hat die Gruppe gesagt, dass sie fertig ist (``_fruehzeitig_fertig``),
    startet die Gegenueberstellung mit den KI-Fragen
    (``versuche_gegenueberstellung``). Sonst geht die eigene Antwort des
    Modells (``text``, ohne den Block) in den Chat -- seit dem Live-Test
    05.10.2026 statt der Stand-Zeile "Still missing: Begriff (x/3)", die sich
    nach jeder Bestaetigung wiederholte und eine Soll-Zahl nannte, die es
    nicht geben soll (Birk: die Anzahl entscheidet die Gruppe). Was je
    Begriff steht, zeigt der CoThinker. Ohne Antworttext ein kurzer Verweis
    dorthin. Kein Modellaufruf hier selbst (Zusage 2)."""
    from interview_theater import vorschlag

    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        bestehend_roh = (stand["fragen_eigene_vorschlag"] or "") if stand else ""
    except (IndexError, KeyError):
        bestehend_roh = ""
    bestehend = vorschlag.zeilen(bestehend_roh) if bestehend_roh else []
    neue_zeilen = vorschlag.zeilen(wert)
    zeilen = _mische_eigene_fragen(bestehend, neue_zeilen)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_eigene_vorschlag", "\n".join(zeilen))

    if _fruehzeitig_fertig(text) and not _genug_eigene(conn, chat_id):
        return sende_mit_vorschlagen(conn, tg, chat_id, T._TEXT_FRAGEN_EIGENE_ZU_WENIG)
    if not _fruehzeitig_fertig(text):
        antwort = (text or "").strip()
        return sende_mit_vorschlagen(
            conn, tg, chat_id, antwort or T._TEXT_FRAGEN_EIGENE_IM_COTHINKER,
        )
    return _eigene_fertig(conn, tg, chat_id)


def _eigene_fertig(conn, tg, chat_id: int, klm=None, e=None) -> int:
    """Die Gruppe ist mit ihren eigenen Fragen fertig: einmal den Zeitpunkt
    merken, dann die Gegenueberstellung -- oder, solange die KI-Fragen noch
    im Hintergrund entstehen, eine Zeile; ``fragen_ki.starte`` offenbart
    nach seinem Lauf von selbst. Gemeinsamer Weg von "Own questions done."
    (``uebernimm_eigene``) und dem Knopf "Yes, suggest some"
    (``ja_vorschlagen``).

    Feedbackloop P1-2, R-3/P2-H2b: ist der Lauf beim Eintritt gescheitert
    (kein ``fragen_ki_vorschlag``, keiner laeuft), stoesst ``fragen_ki.starte``
    ihn hier neu an -- im eigenen Thread, kein Modellaufruf in diesem Weg
    (Zusage 2), nie doppelt (``fragen_ki.versuche_start``). Ohne ``klm``
    (der Chatweg) geht das nicht; deshalb traegt die Wartezeile den Knopf
    "Suggest questions": scheitert auch dieser Lauf, fuehrt er ueber "Yes,
    suggest some" zurueck hierher. Die Zeile geht VOR dem Start raus, damit
    ein schneller Lauf ihre Leiste beim Offenbaren schon vorfindet und
    abnimmt."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_VORSCHLAGEN)
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
    message_id = sende_mit_vorschlagen(conn, tg, chat_id, T._TEXT_FRAGEN_EIGENE_WARTET_AUF_KI)
    if klm is not None:
        from interview_theater import fragen_ki

        fragen_ki.starte(conn, tg, klm, e, chat_id)
    return message_id


# --- "Suggest questions" (Birk, 05.10.2026) -----------------------------------
#
# Der Knopf, mit dem die Gruppe die KI-Fragen anfordert. Er erzeugt nichts
# sofort, sondern fragt zuerst, ob die Gruppe selbst noch Fragen hat
# (Birk: "Proaktive Aufforderung zum Selberdenken"). Freitext ist
# gleichwertig: "we're done" im Chat laeuft ueber den Satz
# ``_SATZ_EIGENE_FRAGEN_FRUEHER_FERTIG`` (``uebernimm_eigene``). Kein
# Modellaufruf in diesen Wegen (Zusage 2) -- die KI-Fragen entstehen beim
# Eintritt in Phase 2 im Hintergrund (``fragen_ki.starte``).


def vorschlagen_leiste(conn, chat_id: int) -> list[tuple[str, str]]:
    """Der eine Knopf "Suggest questions"."""
    return [(
        T._TEXT_FRAGEN_VORSCHLAGEN_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_VORSCHLAGEN, None)),
    )]


def sende_mit_vorschlagen(conn, tg, chat_id: int, text: str,
                          undo_behalten: bool = False) -> int:
    """``text`` mit dem Knopf "Suggest questions" darunter -- die vorige
    Leiste dieser Art kommt vorher ab, damit immer nur einer bedienbar ist.

    ``undo_behalten`` (der Eintritt in Phase 2): direkt davor steht meist die
    📌-Zeile der gerade automatisch gespeicherten Begriffe mit ihrem
    Undo-Knopf. ``_sende_knoepfe`` liesse ihn verfallen
    (``_kollabiere_letzten_einsamen_undo``) -- hier bleibt er stehen: er ist
    der einzige Weg, die Begriffe zurueckzunehmen, und "Suggest questions"
    ist kein zweiter Speicherweg, der mit ihm konkurriert.

    Unter ``workshop.fragen_eigene_min`` eigenen Fragen geht ``text`` ohne
    den Knopf raus (Padua, Birk 05.10.2026 14:05)."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_VORSCHLAGEN)
    if not _genug_eigene(conn, chat_id):
        message_id = tg.sende(chat_id, text)
        _merke_botnachricht(conn, chat_id, message_id, text)
        return message_id
    leiste = vorschlagen_leiste(conn, chat_id)
    if undo_behalten:
        message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
        _merke_botnachricht(conn, chat_id, message_id, text)
    else:
        message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id,
    )
    return message_id


def _genug_eigene(conn, chat_id: int) -> bool:
    """Ob die Gruppe mindestens ``workshop.fragen_eigene_min`` eigene Fragen
    hat (Zeilen in ``fragen_eigene_vorschlag``); Vorgabe 0 = immer."""
    from interview_theater import vorschlag

    mindestens = workshop.fragen_eigene_min()
    if mindestens <= 0:
        return True
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_eigene_vorschlag"] or "") if stand else ""
    except (IndexError, KeyError):
        roh = ""
    return len(vorschlag.zeilen(roh) if roh else []) >= mindestens


def _hat_eigene_fragen(conn, chat_id: int) -> bool:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["fragen_eigene_vorschlag"] or "") if stand else ""
        bestaetigt = (stand["fragen"] or "") if stand else ""
    except (IndexError, KeyError):
        return False
    return bool(roh.strip() or bestaetigt.strip())


def frage_nach_eigenen(conn, tg, chat_id: int) -> int:
    """Druck auf "Suggest questions": die Rueckfrage zum Selberdenken mit
    "We have more" / "Yes, suggest some". Ohne eine einzige eigene Frage die
    deutlichere Fassung -- eigene Fragen zuerst. Unter
    ``workshop.fragen_eigene_min`` (ein alter Knopf) nur eine Zeile."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_VORSCHLAGEN)
    if not _genug_eigene(conn, chat_id):
        return tg.sende(chat_id, T._TEXT_FRAGEN_EIGENE_ZU_WENIG)
    text = (T._TEXT_FRAGEN_SELBST_RUECKFRAGE if _hat_eigene_fragen(conn, chat_id)
            else T._TEXT_FRAGEN_SELBST_RUECKFRAGE_LEER)
    leiste = [
        (T._TEXT_FRAGEN_NOCH_EIGENE_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_NOCH_EIGENE, None))),
        (T._TEXT_FRAGEN_JA_VORSCHLAGEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FRAGEN_JA_VORSCHLAGEN, None))),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id,
    )
    return message_id


def noch_eigene(conn, tg, chat_id: int) -> int:
    """"We have more": einladen, nichts erzeugen. Die naechste Nachricht der
    Gruppe laeuft durch den normalen Gespraechszug (``VORSCHLAG EIGENE
    FRAGEN:``), der den Knopf wieder anbietet."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_JA_VORSCHLAGEN)
    return tg.sende(chat_id, T._TEXT_FRAGEN_NOCH_EIGENE)


def ja_vorschlagen(conn, tg, chat_id: int, klm=None, e=None) -> int:
    """"Yes, suggest some": derselbe Weg wie "Own questions done." -- mit
    ``klm``/``e``, damit ein gescheiterter KI-Lauf nachgeholt werden kann
    (``_eigene_fertig``)."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGEN_NOCH_EIGENE)
    if not _genug_eigene(conn, chat_id):
        return tg.sende(chat_id, T._TEXT_FRAGEN_EIGENE_ZU_WENIG)
    return _eigene_fertig(conn, tg, chat_id, klm=klm, e=e)


# --- Frage fuer Frage --------------------------------------------------------


def _begriffe_mit_doppelpunkt(conn, chat_id: int) -> list[str]:
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = (stand["begriffe"] if stand else "") or ""
    except (IndexError, KeyError):
        return []
    return [b for b in begriffe_modul.zerlege(roh) if ":" in b]


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
    # G3 Padua 05.10.2026: ein Begriff, der selbst einen Doppelpunkt traegt,
    # stand zerrissen auf der Karte. Nur dann der Begriffsabgleich -- sonst
    # bleibt die Karte byte-gleich.
    lang, lang_rest = _teile_zeile(zeile, _begriffe_mit_doppelpunkt(conn, chat_id))
    if lang is not None and lang_rest:
        begriff, trenner, rest = lang, ":", lang_rest
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

    # P2-H3 (Feedbackloop P1-2): nur die neueste Fragekarte ist bedienbar --
    # nach einer Schaerfung stand sonst die alte Karte mit lebendem
    # "Accept" darueber ("Which Accept belongs to the newest question?").
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGE_ANNEHMEN)
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


def starte_durchgehen(conn, tg, chat_id: int, hinweis: bool = True) -> bool:
    """"Ja, einzeln durchgehen" -- zeigt Frage 1. Liefert False, wenn es
    nichts zu zeigen gibt (eine ueberholte Nachricht).

    Padua (05.10.2026): vorher ein Satz, dass sich alle Fragen auch auf
    einmal im CoThinker sortieren lassen -- ``hinweis=False``, wenn der
    Aufrufer ihn schon in seiner eigenen Nachricht traegt
    (``versuche_gegenueberstellung``)."""
    if not _auswahlfragen(conn, chat_id):
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", None)
    repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
    if hinweis and workshop.diskussion_aktiv():
        tg.sende(chat_id, T._TEXT_FRAGEN_COTHINKER_HINWEIS)
    _zeige_frage(conn, tg, chat_id, 1)
    return True


def sortierung_abschliessen(conn, tg, klm, e, chat_id: int) -> None:
    """"Fertig sortiert" aus der Sortierliste im CoThinker (versteckter
    Befehl ``/sortiert``, Padua 05.10.2026): was die Gruppe nicht angetippt
    hat, gilt als behalten ("" -> "ja"); "ja"/"nein"/"schaerfen" bleiben.
    Steht noch eine Frage auf "schaerfen", kommt ihre Karte mit der
    Rueckfrage, was sich aendern soll -- der Rest laeuft ueber den
    bestehenden Kartenweg (``nimm_offene_frage_text`` -> Schaerfung ->
    Annehmen). Sonst schliesst die Runde sofort ab. Kein Modellaufruf."""
    fragen = _auswahlfragen(conn, chat_id)
    if not fragen:
        tg.sende(chat_id, T._TEXT_FRAGEN_KEINE_AUSWAHL)
        return
    entschieden = _decisions(conn, chat_id)
    neu = []
    for nummer in range(1, len(fragen) + 1):
        wert = entschieden[nummer - 1] if nummer <= len(entschieden) else ""
        neu.append(wert if wert in ("ja", "nein", "schaerfen") else "ja")
    repo.setze_arbeitsstand(conn, chat_id, "fragen_entschieden", ",".join(neu))
    # Review 05.10.2026: die gerade offene Chat-Karte verliert ihre Knoepfe --
    # ein spaeterer Druck darauf startete sonst den Durchgang neu.
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FRAGE_ANNEHMEN)
    if "schaerfen" in neu:
        _zeige_naechste(conn, tg, chat_id, neu.index("schaerfen") + 1)
        return
    _schliesse_fragen_ab(conn, tg, klm, e, chat_id)


def _zeige_naechste(conn, tg, chat_id: int, nummer: int) -> None:
    """Zeigt die naechste offene Karte. Steht sie auf "schaerfen" (in der
    Sortierliste mit ✎ markiert), folgt die Rueckfrage, was sich aendern
    soll -- fuer JEDE ✎-Karte, nicht nur die erste (Review 05.10.2026); in
    Padua wartet die naechste Nachricht dann auf den Wunsch."""
    _zeige_frage(conn, tg, chat_id, nummer)
    entschieden = _decisions(conn, chat_id)
    if nummer <= len(entschieden) and entschieden[nummer - 1] == "schaerfen":
        if workshop.diskussion_aktiv():
            repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", "schaerfen")
        tg.sende(chat_id, T._TEXT_FRAGE_WAS_AENDERN)


def _ist_aktuelle_karte(conn, chat_id: int, nummer: int) -> bool:
    """True, wenn ``nummer`` die gerade vorgelegte Karte ist. Ein Druck auf
    eine ueberholte Karte (nach "Fertig sortiert" oder nach Abschluss der
    Runde) aendert nichts (Review 05.10.2026)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        roh = ((stand["fragen_aktuell"] if stand else "") or "").strip()
    except (IndexError, KeyError):
        return False
    return roh.isdigit() and int(roh) == nummer


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
    if not _ist_aktuelle_karte(conn, chat_id, nummer):
        return T._TEXT_FRAGEN_KEINE_AUSWAHL
    _setze_entscheidung(conn, chat_id, nummer, wert)
    _vergiss_schaerfen_warten(conn, chat_id)
    quittung = T._TEXT_FRAGE_ANGENOMMEN if wert == "ja" else T._TEXT_FRAGE_VERWORFEN
    naechste = _naechste_offene(conn, chat_id, len(fragen))
    if naechste is None:
        _schliesse_fragen_ab(conn, tg, klm, e, chat_id)
        return quittung
    _zeige_naechste(conn, tg, chat_id, naechste)
    return quittung


def frage_waehlt_schaerfen(conn, tg, chat_id: int, nummer: int) -> str:
    """"Schaerfen" -- fragt deterministisch, was sich aendern soll. Die
    Antwort kommt als normale Nachricht und wird ueber
    ``nimm_offene_frage_text`` abgefangen, weil ``fragen_aktuell`` hier
    defensiv (erneut) auf diese Frage gesetzt wird -- derselbe Schutz wie
    eine aus Versehen verschobene Reihenfolge.

    Ein Druck auf eine ueberholte Karte (Runde abgeschlossen, andere Karte
    vorgelegt) aendert nichts (Review 05.10.2026)."""
    if not _ist_aktuelle_karte(conn, chat_id, nummer):
        return T._TEXT_FRAGEN_KEINE_AUSWAHL
    repo.setze_arbeitsstand(conn, chat_id, "fragen_aktuell", str(nummer))
    if workshop.diskussion_aktiv():
        # Padua: die naechste Nachricht ist der Wunsch -- auch als Frage
        # formuliert ("Could you make it shorter?").
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", "schaerfen")
    tg.sende(chat_id, T._TEXT_FRAGE_WAS_AENDERN)
    # P2-N1 (Feedbackloop P1-2): die Rueckfrage steht schon als Blase da --
    # dieselbe Zeile noch einmal als Knopf-Quittung stand doppelt.
    return ""


def _starte_schaerfung(conn, tg, klm, e, chat_id: int, nummer: int, wunsch: str) -> None:
    fragen = _auswahlfragen(conn, chat_id)
    if nummer < 1 or nummer > len(fragen):
        return
    frage = fragen[nummer - 1]
    weich = _weich_dict(conn, chat_id).get(nummer, "")
    sensibel_hinweis = (
        T._TEXT_FRAGE_SCHAERFEN_SENSIBEL_HINWEIS.format(weich=weich) if weich else ""
    )
    anweisung = _ohne_weich_auftrag(T.ANWEISUNG_FRAGE_SCHAERFEN.format(
        nummer=nummer, frage=frage, wunsch=wunsch, sensibel_hinweis=sensibel_hinweis,
    ))
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
    alte = _auswahlfragen(conn, chat_id)
    if (neue_frage and nummer <= len(alte) and not weich_block
            and _fragetext(neue_frage) == _fragetext(alte[nummer - 1])):
        # P2-H3 (Feedbackloop P1-2): jede freie Nachricht zu einer offenen
        # Frage ist ein Schaerfungswunsch -- auch "Does Accept save it?".
        # Kommt die Frage unveraendert zurueck, stand dieselbe Karte bis zu
        # dreimal untereinander. Die Karte darueber bleibt die bedienbare.
        _warte_weiter_auf_wunsch(conn, chat_id)
        return tg.sende(chat_id, T._TEXT_FRAGE_WAS_AENDERN)
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
    message_id = _zeige_frage(conn, tg, chat_id, nummer)
    _warte_weiter_auf_wunsch(conn, chat_id)
    return message_id


def _warte_weiter_auf_wunsch(conn, chat_id: int) -> None:
    """Padua (Review 05.10.2026): nach einer Schaerfung steht dieselbe Karte
    wieder da, die Gruppe formuliert sie offensichtlich noch um -- auch ein
    als Frage formulierter Nachwunsch ("Could it be shorter?") gilt ihr."""
    if workshop.diskussion_aktiv():
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", "schaerfen")


def _fragetext(zeile: str) -> str:
    """Der Fragetext einer ``Begriff: Frage``-Zeile in Vergleichsform."""
    _, trenner, rest = zeile.partition(":")
    return _platt(rest if trenner and rest.strip() else zeile)


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
    padua = workshop.diskussion_aktiv()
    if padua and ZEIG_ALLE.match(text) and _auswahlfragen(conn, chat_id):
        tg.sende(chat_id, uebersicht_text(conn, chat_id))
        return True
    if warte == "richtung":
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
        anweisung = frage_fuer_andere_richtung(conn, chat_id, richtung=text)
        _starte_auftrag(conn, tg, klm, e, chat_id, anweisung)
        return True

    nummer = _aktuelle_offene_nummer(conn, chat_id)
    if nummer is not None:
        if padua and warte != "schaerfen" and text.rstrip().endswith("?"):
            # Padua 05.10.2026: "Can we see all questions?" ist kein
            # Aenderungswunsch an der offenen Karte -- ohne vorherigen Druck
            # auf "Schaerfen" geht eine Frage ins normale Gespraech.
            return False
        if warte == "schaerfen":
            repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)
        _starte_schaerfung(conn, tg, klm, e, chat_id, nummer, text)
        return True
    return False


def _vergiss_schaerfen_warten(conn, chat_id: int) -> None:
    """Nach Annehmen/Verwerfen wartet keine Karte mehr auf einen Wunsch --
    nur "schaerfen" wird geraeumt, "richtung" bleibt unberuehrt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    try:
        warte = (stand["fragen_warte_auf"] or "") if stand else ""
    except (IndexError, KeyError):
        return
    if warte == "schaerfen":
        repo.setze_arbeitsstand(conn, chat_id, "fragen_warte_auf", None)


#: Padua 05.10.2026: der Wunsch, alle Fragen zu sehen -- wortwoertlich, kein
#: Erkenner-Lauf (die Bruecke ~/.hermes/.../padua-fragen-uebersicht.py lief
#: bis dahin als Cron).
ZEIG_ALLE = re.compile(
    r"^\s*(show all|show all questions|mostra tutte|mostra tutte le domande"
    r"|zeig alle|zeig alle fragen)\s*[.!]?\s*$",
    re.I,
)

_MARKE = {"ja": "✓", "nein": "✗", "schaerfen": "✎", "": "·"}


def uebersicht_text(conn, chat_id: int) -> str:
    """Alle Fragen der laufenden Auswahl auf einen Blick, je Begriff, mit
    Zustand (✓ ✗ ✎ ·) und Herkunft, darunter der Zaehler und der Hinweis
    auf die Sortierliste im CoThinker. Aus ``auswahl.fragen_liste`` --
    dieselbe Gruppierung wie im CoThinker."""
    from interview_theater import auswahl

    liste = auswahl.fragen_liste(repo.hole_arbeitsstand(conn, chat_id))
    zeilen: list[str] = []
    for gruppe in liste["gruppen"]:
        if zeilen:
            zeilen.append("")
        if gruppe["titel"]:
            zeilen.append(f"— {gruppe['titel']} —")
        for eintrag in gruppe["eintraege"]:
            herkunft = {"eigen": T._TEXT_HERKUNFT_EIGEN,
                        "ki": T._TEXT_HERKUNFT_KI}.get(eintrag["herkunft"], "")
            zeilen.append(f"{eintrag['nummer']}. {_MARKE[eintrag['zustand']]} "
                          f"{eintrag['text']}{herkunft}")
    zeilen += ["", T._TEXT_AUSWAHL_ZAEHLER.format(**liste["zaehler"]),
               T._TEXT_FRAGEN_COTHINKER_HINWEIS]
    return "\n".join(zeilen)


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
    (klassischer Ablauf) ist jeder Eintrag ein leerer String.

    Seit Aufgabe 14 haengt die Abschlussnachricht die Auswertung
    eigene-vs-KI an -- aber NUR, wenn der A/B-Vergleich fuer diese Runde
    tatsaechlich lief (mindestens ein nicht-leerer Eintrag in
    ``herkunft_final``). Ohne das bleibt der Text byte-identisch zu vor
    Aufgabe 14 (``test_klassischer_abschlusstext_bleibt_byte_identisch``)."""
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

    # Aufgabe 14: die Auswertungszeile(n), gebaut aus denselben Werten, die
    # ``_schreibe`` gleich speichert -- kein zweites Lesen aus der DB, keine
    # Race mit dem Schreiben. Gegated auf "der A/B-Vergleich lief ueberhaupt"
    # (mindestens ein nicht-leerer Herkunftseintrag): ohne das bleibt der
    # klassische Ablauf byte-identisch.
    auswertung_anhang = ""
    if any(herkunft_final):
        ergebnis = fragen_auswertung.aus_daten(wert, ",".join(herkunft_final))
        gesamt = ergebnis["gesamt"]
        zeilen_je_begriff = "\n".join(
            T._TEXT_FRAGEN_AUSWERTUNG_ZEILE.format(
                begriff=begriff, eigen=zahlen["eigen"], ki=zahlen["ki"],
            )
            for begriff, zahlen in ergebnis["je_begriff"].items()
        )
        auswertung_anhang = "\n\n" + T._TEXT_FRAGEN_AUSWERTUNG.format(
            ki=gesamt["ki"], eigen=gesamt["eigen"],
        )
        if zeilen_je_begriff:
            auswertung_anhang += "\n" + zeilen_je_begriff

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
        + auswertung_anhang
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


def _teile_eroeffnung(wert: str) -> tuple[str, str]:
    """Zerlegt den Block ``VORSCHLAG EROEFFNUNG:`` in (Eroeffnung, Abschluss)
    -- herausgezogen aus ``_speichere_eroeffnung`` (Padua P1-2), damit der
    Autosave-Weg (``schreibe_eroeffnung_automatisch``) dieselbe Zerlegung
    liest statt einer zweiten Fassung."""
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
    return "\n".join(eroeffnung).strip(), "\n".join(abschluss).strip()


def _speichere_eroeffnung(conn, tg, chat_id: int, wert: str, e=None, klm=None) -> str:
    """Zerlegt den Block ``VORSCHLAG EROEFFNUNG:`` in Eroeffnung und
    Abschluss und legt beides ab. Unveraendert seit dem 06.09.2026."""
    eroeffnung, abschluss = _teile_eroeffnung(wert)
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_eroeffnung", eroeffnung or None
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "interview_abschluss", abschluss or None
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


def schreibe_eroeffnung_automatisch(
    conn, tg, chat_id: int, wert: str, klm=None, e=None,
) -> int:
    """Padua Phase 2 Autosave (siehe ``workshop.autosave_phase1_2_aktiv``,
    aufgerufen aus ``knoepfe.basis._autospeichere``): schreibt Eroeffnung und
    Abschluss sofort, meldet mit einer 📌-Zeile und EINEM Undo-Knopf statt
    der Ja/Nein-Rueckfrage.

    Derselbe Weg danach wie ``_speichere_eroeffnung``: Journal, Leitfaden
    einmal zeigen, dann der automatische Phasensprung
    (``uebergang_nach_speichern``) -- genau wie am Knopfdruck "Ja,
    speichern", nur ohne den Druck. Bleibt der Sprung aus (Materiallage noch
    nicht so weit), kommt stattdessen die stille Phasenfrage
    (``biete_phase_proaktiv``) -- sonst staende die 📌-Zeile eine Nachricht
    lang allein, bevor sofort eine zweite, gleich gewichtete Leiste folgt und
    ihre Undo-Quittung wegkollabiert."""
    eroeffnung, abschluss = _teile_eroeffnung(wert)

    def _schreibe():
        repo.setze_arbeitsstand(
            conn, chat_id, "interview_eroeffnung", eroeffnung or None,
        )
        repo.setze_arbeitsstand(
            conn, chat_id, "interview_abschluss", abschluss or None,
        )
        repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)

    titel = erkenner.T._FELD_BESCHRIFTUNG["eroeffnung"]
    text = erkenner.T._ZEILE_FESTGELEGT.format(titel=titel, text=wert)
    lauf_id = erkenner.lauf_fuer_knopf(conn, e, chat_id, text, _schreibe)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T._JOURNAL_EROEFFNUNG_FESTGELEGT,
        quelle="knopf",
    )
    if lauf_id is None:
        message_id = tg.sende(chat_id, text, system=True)
    else:
        message_id = sende_notiert_nur_undo(conn, tg, chat_id, text, lauf_id)
    leitfaden.sende_einmal(conn, tg, chat_id, e=e)
    from interview_theater.knoepfe.stationen import (
        biete_phase_proaktiv, uebergang_nach_speichern,
    )

    if not uebergang_nach_speichern(conn, tg, klm, e, chat_id):
        biete_phase_proaktiv(conn, tg, chat_id)
    return message_id


def _leitfaden_knopf(conn, chat_id: int) -> tuple[str, str] | None:
    """"Leitfaden zeigen", sobald es einen gibt -- sonst None."""
    if not leitfaden.steht(conn, chat_id):
        return None
    return (
        T._TEXT_LEITFADEN_KNOPF,
        _daten(repo.lege_knopf_an(conn, chat_id, ART_LEITFADEN, None)),
    )

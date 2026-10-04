"""Das Fehlstellen-Register: was der Gruppe noch fehlt, als Arbeitsliste
(06.09.2026).

**Warum es das gibt.** ``/stand`` und die Gruppenseite zeigen, was **gefuellt**
ist. Was *fehlt*, musste die Gruppe sich bisher selbst zusammenreimen -- aus
sieben Bloecken mit "noch offen"-Zeilen. Dieses Modul dreht die Anzeige um: es
sagt in ganzen Saetzen, was als naechstes dranwaere.

**Reine Leseabfrage, kein Modellaufruf** -- wie ``phasen.voraussetzungen``,
und aus derselben Quelle: geprueft wird genau das, woran der Code an anderer
Stelle schon haengt (``phasen.voraussetzungen``, ``szene.PFLICHTFELDER``,
``knoepfe.ebene2_erlaubt``, ``aufnahme.unausgewertete_interviews``). Eine
zweite, frei erfundene Wunschliste waere ein zweiter Stand -- und der erste,
der auseinanderlaeuft.

**Der Bot schlaegt vor, er handelt nicht.** Nichts hier loest etwas aus, und
nichts hier schickt von selbst eine Nachricht: die Liste erscheint an genau
zwei bestehenden Orten (``befehle._befehl_stand`` und die Gruppenseite) und
nur, **wenn es Fehlstellen gibt**. Eine Zeile "nichts fehlt" waere Laerm.

**Ein Zusammenbau, zwei Aufrufer** -- dasselbe Muster wie
``leitfaden.aus_feldern``: ``aus_daten`` ist rein und kennt nur Dicts,
``register`` holt sie ueber ``repo`` (Bot), ``web_daten.fehlstellen`` ueber
die read-only geoeffnete Verbindung (Web). Der Webserver darf ``repo`` nicht
anfassen, und beide Seiten sollen trotzdem dieselbe Liste zeigen.

**Die Reihenfolge ist die Arbeitsreihenfolge, nicht die Phasennummer**
(``sortiere``): oben steht, was in der Phase dranwaere, in der die Gruppe
gerade steht; darunter der Rueckstand aus frueheren Phasen (er blockiert);
ganz unten, was spaeter kommt. ``HOECHSTENS`` (8) deckelt die Liste -- eine
Arbeitsliste, die man scrollen muss, ist keine.
"""

from interview_theater import phasen

#: Wie viele Zeilen hoechstens ausgespielt werden. Acht, weil das die Zahl
#: ist, die auf einem Handy unter ``/stand`` noch als Liste lesbar ist -- und
#: weil eine Gruppe mit mehr als acht offenen Punkten ohnehin nicht bei Punkt
#: neun anfaengt.
HOECHSTENS = 8

#: Die Ueberschrift ueber dem Abschnitt -- wortgleich im Chat und im Web,
#: damit niemand zwei Namen fuer dieselbe Liste lernen muss.
UEBERSCHRIFT = "Was noch fehlt"

#: Ab dieser Phase sind Quell-Interview und Sprachprofil einer Figur eine
#: Fehlstelle und nicht bloss ein leeres Feld -- die Ebene-2-Arbeit laeuft
#: erst ab der Schaerfung (``knoepfe.ebene2_erlaubt``). In Phase 4 erfindet
#: die Gruppe frei; dort danach zu fragen waere genau die Ruecklenkung aufs
#: Material, die der Umbau vom 05.09.2026 vermeidet.
PHASE_SPRACHPROFIL = 5

#: Die Saetze des Registers (Karte A1: vorher Literale in den Funktionen,
#: zeichengleich). Je Satz ein Eintrag in sprachen/en/texte.toml.
_SATZ_BEGRIFFE = "Die Begriffsliste aus dem Plenum steht noch nicht."
_SATZ_FRAGEN = "Es sind noch keine Interviewfragen ausgewaehlt."
_SATZ_FRAGEN_UNGEPRUEFT = "Die Fragen sind noch nicht auf heikle Stellen geprueft."
_SATZ_EROEFFNUNG = "Im Leitfaden fehlt die Eroeffnung - womit ihr das Gespraech anfangt."
_SATZ_ABSCHLUSS = "Im Leitfaden fehlt der Abschluss - womit ihr das Gespraech beendet."
_SATZ_KEIN_INTERVIEW = "Noch kein Interview ist ausgewertet."
_SATZ_INTERVIEW_OFFEN = "{name} ist aufgenommen, aber noch nicht ausgewertet."
_SATZ_SETTING = "Das Setting steht noch nicht - Ort, Zeit, Anlass."
_SATZ_GESCHICHTE = "Die Geschichte steht noch nicht - was passiert, wie es ausgeht."
_SATZ_FIGUREN_OFFEN = "Die Figurenliste ist noch nicht abgenommen."
_SATZ_KEINE_FIGUREN = "Es gibt noch keine Figuren."
_SATZ_FIGUR_OHNE_BESCHREIBUNG = "{name} hat noch keine Beschreibung."
_SATZ_FIGUR_OHNE_INTERVIEW = (
    "Fuer {name} ist noch kein Interview zugeordnet - aus welchem spricht sie?"
)
_SATZ_FIGUR_OHNE_SPRACHPROFIL = "{name} hat noch kein Sprachprofil."
_SATZ_KEINE_SZENEN = "Es gibt noch keine Szenen."
_SATZ_SZENE_NICHT_ERZAEHLT = "{kopf} ist noch nicht erzaehlt."
_SATZ_SZENE_OHNE_FORM = "Fuer {kopf} ist noch keine Form bestaetigt."
_SATZ_SZENE_FELDER = "Fuer {kopf} fehlt noch: {felder}."
_SATZ_SZENE_OHNE_TEXT = "{kopf} hat noch keinen Szenentext."
#: Ersatznamen, wenn Figur oder Szene keinen Namen/keine Nummer hat.
_TEXT_EINE_FIGUR = "Eine Figur"
_TEXT_SZENE_KOPF = "Szene {nummer}"
_TEXT_EINE_SZENE = "Eine Szene"


def _wert(quelle, name: str):
    """Ein Feld aus einem Dict oder einer ``sqlite3.Row``; ``None``, wenn es
    die Spalte in einer alten Datenbank noch nicht gibt.

    Dieselbe Nachsicht wie in ``phasen.voraussetzungen``: die Migration ist
    additiv und laeuft im Bot, aber ein Leser darf daran nicht scheitern --
    der Webserver migriert ohnehin nichts."""
    if quelle is None:
        return None
    try:
        return quelle[name]
    except (IndexError, KeyError, TypeError):
        return None


def _text(quelle, name: str) -> str:
    """Ein Feld als getrimmter String -- leer, wenn es fehlt oder NULL ist."""
    return (_wert(quelle, name) or "").strip()


def _gesetzt(quelle, name: str) -> bool:
    """Wie ``_text``, aber ein **leerer String zaehlt als gesetzt**.

    Der Fall sind ``frage_einleitungen`` und ``fragen_weich``: "keine
    noetig" ist ein Ergebnis der Sensibilitaetspruefung, kein fehlender Wert
    (dieselbe Unterscheidung wie in ``phasen.voraussetzungen``)."""
    return _wert(quelle, name) is not None


def _eintrag(bereich: str, text: str, phase: int, szene=None, figur=None) -> dict:
    """Eine Fehlstelle. ``text`` ist **ein** Satz auf Deutsch, so wie die
    Gruppe ihn liest -- kein Feldname, keine Abkuerzung."""
    return {
        "bereich": bereich,
        "text": text,
        "szene": szene,
        "figur": figur,
        "phase": phase,
    }


def _begriffe_und_fragen(stand) -> list[dict]:
    """Phase 1 und 2: Begriffsliste, Fragen, Sensibilitaetspruefung,
    Eroeffnung und Abschluss -- die vier Bedingungen aus
    ``phasen.voraussetzungen[3]``, einzeln benannt.

    Ohne Fragen wird der Rest nicht aufgezaehlt: Einleitungen und Eroeffnung
    entstehen aus den Fragen, und drei Zeilen fuer denselben naechsten
    Schritt sind keine Arbeitsliste."""
    offen = []
    if not _text(stand, "begriffe"):
        offen.append(_eintrag(
            "begriffe", T._SATZ_BEGRIFFE, 1,
        ))
    if not _text(stand, "fragen"):
        offen.append(_eintrag(
            "fragen", T._SATZ_FRAGEN, 2,
        ))
        return offen
    from interview_theater import workshop
    if workshop.fragen_weich_aktiv() and not (
        _gesetzt(stand, "fragen_weich") or _gesetzt(stand, "frage_einleitungen")
    ):
        offen.append(_eintrag(
            "fragen", T._SATZ_FRAGEN_UNGEPRUEFT, 2,
        ))
    if not _text(stand, "interview_eroeffnung"):
        offen.append(_eintrag(
            "leitfaden",
            T._SATZ_EROEFFNUNG,
            2,
        ))
    if not _text(stand, "interview_abschluss"):
        offen.append(_eintrag(
            "leitfaden",
            T._SATZ_ABSCHLUSS,
            2,
        ))
    return offen


def _interviews(hat_verdichtung: bool, offene: list[str]) -> list[dict]:
    """Phase 3: Interviews ohne Verdichtung -- und der Fall, dass ueberhaupt
    noch keine vorliegt.

    ``offene`` sind die Bezeichnungen ("Interview 3"), nie der gespeicherte
    Aufnahmename: der ist oft ein Klarname oder der Telegram-Name dessen, der
    das Handy hielt (Birk, 05.09.2026)."""
    offen = []
    if not hat_verdichtung:
        offen.append(_eintrag("interviews", T._SATZ_KEIN_INTERVIEW, 3))
    for name in offene:
        offen.append(_eintrag(
            "interviews",
            T._SATZ_INTERVIEW_OFFEN.format(name=name),
            3,
        ))
    return offen


def _arbeitsstand(stand) -> list[dict]:
    """Die Arbeitsstandfelder, die Voraussetzung einer naechsten Phase sind:
    Setting und Geschichte (``phasen.voraussetzungen[5]``/``[6]``) und die
    abgenommene Figurenliste (``figuren_fixiert_am``)."""
    offen = []
    if not _text(stand, "rahmen"):
        offen.append(_eintrag(
            "setting", T._SATZ_SETTING, 4,
        ))
    if not _text(stand, "geschichte"):
        offen.append(_eintrag(
            "geschichte",
            T._SATZ_GESCHICHTE,
            4,
        ))
    if not _text(stand, "figuren_fixiert_am"):
        offen.append(_eintrag(
            "figuren", T._SATZ_FIGUREN_OFFEN, 4,
        ))
    return offen


def _figuren(figuren: list, phase: int) -> list[dict]:
    """Je Figur: Beschreibung, Quell-Interview, Sprachprofil.

    Quelle und Sprachprofil erst ab ``PHASE_SPRACHPROFIL`` -- vorher sind sie
    kein Rueckstand, sondern noch nicht dran."""
    offen = []
    if not figuren:
        return [_eintrag("figuren", T._SATZ_KEINE_FIGUREN, 4)]
    for f in figuren:
        name = _wert(f, "name") or T._TEXT_EINE_FIGUR
        if not _text(f, "beschreibung"):
            offen.append(_eintrag(
                "figuren", T._SATZ_FIGUR_OHNE_BESCHREIBUNG.format(name=name), 4,
                figur=name,
            ))
    if phase < PHASE_SPRACHPROFIL:
        return offen
    for f in figuren:
        name = _wert(f, "name") or T._TEXT_EINE_FIGUR
        if _wert(f, "quelle_aufnahme_id") is None:
            offen.append(_eintrag(
                "figuren",
                T._SATZ_FIGUR_OHNE_INTERVIEW.format(name=name),
                PHASE_SPRACHPROFIL,
                figur=name,
            ))
        elif not _text(f, "sprachprofil"):
            offen.append(_eintrag(
                "figuren",
                T._SATZ_FIGUR_OHNE_SPRACHPROFIL.format(name=name),
                PHASE_SPRACHPROFIL,
                figur=name,
            ))
    return offen


def _szenen(szenen: list) -> list[dict]:
    """Phase 6 und 7: keine Szene, Szene ohne Geschichte, Szene ohne
    bestaetigte Form, fehlende Pflichtfelder, Szene ohne Theatertext.

    Die Form steht fuer sich, obwohl sie ein Pflichtfeld ist: sie ist die
    einzige, die die Gruppe **per Knopf bestaetigt** (Birk, 06.09.2026
    00:30) -- "keine bestaetigte Form" ist ein anderer Satz als "es fehlen
    noch Angaben".

    Eine Szene ohne Prosa und ohne Volltext bricht ab: solange die Szene
    nicht einmal erzaehlt ist, sind Form, Ort und Ton keine Fehlstellen,
    sondern der uebernaechste Schritt."""
    from interview_theater import szene as szene_modul

    if not szenen:
        return [_eintrag("szenen", T._SATZ_KEINE_SZENEN, 4)]
    offen = []
    for s in szenen:
        nummer = _wert(s, "nummer")
        kopf = (T._TEXT_SZENE_KOPF.format(nummer=nummer) if nummer is not None
                else T._TEXT_EINE_SZENE)
        if not _text(s, "prosa") and not _text(s, "volltext"):
            offen.append(_eintrag(
                "szenen", T._SATZ_SZENE_NICHT_ERZAEHLT.format(kopf=kopf), 6,
                szene=nummer,
            ))
            continue
        if not _text(s, "form"):
            offen.append(_eintrag(
                "szenen", T._SATZ_SZENE_OHNE_FORM.format(kopf=kopf), 7,
                szene=nummer,
            ))
        fehlend = [
            szene_modul.T.FELDNAMEN.get(feld, feld)
            for feld in szene_modul.PFLICHTFELDER
            if feld != "form" and not _besetzt(s, feld)
        ]
        if fehlend:
            offen.append(_eintrag(
                "szenen",
                T._SATZ_SZENE_FELDER.format(kopf=kopf, felder=", ".join(fehlend)), 7,
                szene=nummer,
            ))
        if not _text(s, "volltext"):
            offen.append(_eintrag(
                "szenen", T._SATZ_SZENE_OHNE_TEXT.format(kopf=kopf), 7,
                szene=nummer,
            ))
    return offen


def _besetzt(s, feld: str) -> bool:
    """Ist dieses Pflichtfeld der Szene gefuellt?

    ``figuren`` ist keine Spalte, sondern eine Verknuepfung
    (``szene_figur``) -- beide Aufrufer legen die Namensliste deshalb unter
    dem Schluessel ``figuren`` in das Szenen-Dict."""
    if feld == "figuren":
        return bool(_wert(s, "figuren"))
    return bool(_text(s, feld))


def sortiere(eintraege: list[dict], jetzige: int) -> list[dict]:
    """Die Arbeitsreihenfolge: erst die aktuelle Phase, dann der Rueckstand
    aus frueheren (aufsteigend), dann das Kommende (aufsteigend).

    Der Rueckstand steht **vor** dem Kommenden, weil er blockiert: einer
    Gruppe, der die Eroeffnung fehlt, nuetzt keine Szenenliste -- sie kommt
    an Phase 3 nicht vorbei. Innerhalb einer Stufe bleibt die
    Einfuegereihenfolge erhalten (``sorted`` ist stabil), also die
    Reihenfolge der Pruefungen."""
    def schluessel(e: dict) -> tuple[int, int]:
        phase = e["phase"]
        if phase == jetzige:
            return (0, phase)
        return (1 if phase < jetzige else 2, phase)

    return sorted(eintraege, key=schluessel)


def aus_daten(
    stand,
    figuren: list,
    szenen: list,
    phase: int,
    hat_verdichtung: bool = False,
    offene_interviews: list[str] | None = None,
    hoechstens: int = HOECHSTENS,
) -> list[dict]:
    """Die reine Funktion hinter ``register`` -- kennt nur Dicts (oder
    ``sqlite3.Row``), keine Verbindung und keine Schreibschicht.

    ``szenen`` erwartet je Szene zusaetzlich den Schluessel ``figuren`` mit
    den Namen der Besetzung (die Verknuepfung ``szene_figur``); ``figuren``
    je Figur ``name``, ``beschreibung``, ``quelle_aufnahme_id`` und
    ``sprachprofil``."""
    eintraege = (
        _begriffe_und_fragen(stand)
        + _interviews(hat_verdichtung, list(offene_interviews or []))
        + _arbeitsstand(stand)
        + _figuren(figuren, phase)
        + _szenen(szenen)
    )
    return sortiere(eintraege, phase)[:hoechstens]


def register(conn, chat_id: int, hoechstens: int = HOECHSTENS) -> list[dict]:
    """Alle Fehlstellen der Gruppe, sortiert und gedeckelt -- der Weg des
    Bots, ueber ``repo``.

    Je Eintrag ``bereich``, ``text`` (ein Satz), ``szene``/``figur`` wo
    zutreffend und ``phase`` -- die Phase, in der das dranwaere. Eine
    vollstaendige Gruppe bekommt eine **leere Liste**, keinen Platzhalter.

    Kein Modellaufruf, kein Schreibvorgang."""
    from interview_theater import aufnahme, kontext, repo

    szenen = []
    for s in repo.hole_szenen(conn, chat_id):
        eintrag = dict(s)
        eintrag["figuren"] = [f["name"] for f in repo.szene_figuren(conn, s["id"])]
        szenen.append(eintrag)
    offene = [
        kontext.interviewbezeichnung(conn, chat_id, kopf["id"])
        for kopf in aufnahme.unausgewertete_interviews(conn, chat_id)
    ]
    return aus_daten(
        repo.hole_arbeitsstand(conn, chat_id),
        repo.figuren(conn, chat_id),
        szenen,
        phasen.aktuelle(conn, chat_id),
        hat_verdichtung=bool(repo.verdichtungen(conn, chat_id)),
        offene_interviews=offene,
        hoechstens=hoechstens,
    )


def zeilen(conn, chat_id: int, hoechstens: int = HOECHSTENS) -> list[str]:
    """Die Fehlstellen als fertige Chatzeilen (``- <Satz>``) -- oder eine
    leere Liste.

    ``/stand`` haengt sie unter den Stand. Leere Liste heisst: gar nichts
    schreiben, auch keine Ueberschrift."""
    return [f"- {e['text']}" for e in register(conn, chat_id, hoechstens)]


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

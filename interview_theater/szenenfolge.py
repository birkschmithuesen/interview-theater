"""Die Szenenfolge und die Szenenplanung als Knopf-Navigation (Phase 6).

**Warum es dieses Modul gibt.** Phase 6 ist die laengste Strecke des
Workshops: erst eine Folge von vier bis sechs Szenen, dann Szene fuer Szene
die Planung, dann je Szene ein Text. Bis zum 05.09.2026 lief das ganz im
Gespraech -- und genau dort verlor der Bot die Entscheidungen, die die Gruppe
schon getroffen hatte: eine zugestimmte Szenenfolge stand als Fliesstext im
Chat und nie in der Tabelle ``szene``, und die naechste Antwort schlug eine
andere Folge vor.

Der Weg ist derselbe wie bei den uebrigen Auswahl-Momenten (``knoepfe.py``):
der Bot legt einen **Vorschlag als Text** hin, mit einem Marker, den der Code
lesen kann (``vorschlag.py``), und darunter haengen Knoepfe, die den Vorschlag
**deterministisch** speichern. Was hier dazukommt, ist der Weg, einen neuen
Vorschlag anzustossen, ohne dass jemand etwas tippen muss -- \"Anzahl
aendern\" und \"Reihenfolge aendern\" brauchen eine neue Antwort des Modells.

**Kein Modellaufruf im Knopf-Handler** (AGENTS.md, Zusage 2 in
``knoepfe.py``): jede Funktion hier, die ein Modell fragt, gibt den Aufruf
sofort an einen eigenen Thread ab -- dasselbe Muster wie ``szene.starte``.
Die Sperre je ``chat_id`` liegt aus demselben Grund vor dem Thread und wird
im Thread freigegeben.
"""

from __future__ import annotations

import logging
import re
import threading

from interview_theater import anweisungen, repo

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf``.
ART = "szenenfolge"

#: Art des zweiten, kleineren Aufrufs: die fehlenden Felder EINER Szene.
ART_FELDER = "szenenfelder"

#: Ausgabebudget. Ein Vorschlag sind sechs Zeilen -- das Budget ist eine
#: Obergrenze gegen Durchdrehen, kein Zielwert (wie ``szene.MAX_TOKENS``).
#: ACHTUNG, AGENTS.md Falle 4: dieser Aufruf laeuft ueber ``klm.prosa`` und
#: damit mit AKTIVEM Reasoning. Reasoning verbraucht das Ausgabebudget VOR
#: dem eigentlichen Inhalt -- bei zu knappem Budget kommt HTTP 200 mit
#: leerem Inhalt und ``finish_reason: "length"`` zurueck, ein stiller
#: Durchfall. Live gemessen am 05.09.2026 abends (Test-Gruppe): mit 4000
#: Token endete jeder Lauf im Denken, die Gruppe sah nur "Die Szenenfolge
#: ist mir nicht gelungen". Deshalb wie in ``szene.py`` weit ueber der
#: Messung; was das Modell nicht braucht, kostet nichts.
MAX_TOKENS = 60_000

#: Zeitbudget des Aufrufs. Ebenfalls angehoben (vorher 120 s): ein
#: Reasoning-Lauf braucht laut ``reasoning-stufen-entscheidungshilfe.md``
#: § 4.4 mindestens 60 s, und ein Timeout spart hier nichts -- der Lauf
#: haengt in einem eigenen Thread, ein Abbruch ist trotzdem bezahlt.
TIMEOUT_S = 300.0

#: Wie viele Szenen vorgeschlagen werden, wenn niemand etwas anderes sagt.
ANZAHL_VORGABE = 5
#: Die Auswahl hinter \"Anzahl aendern\". Drei ist die Untergrenze, unter der
#: kein Abend entsteht; sechs die Obergrenze, die eine Workshopgruppe an einem
#: Wochenende ausschreiben kann.
ANZAHL_MOEGLICH = (3, 4, 5, 6)

#: Die Form, mit der jede neu angelegte Szene startet. Vorgabe, keine
#: Festlegung: \"Form aendern\" haengt unter jeder Szenenvorstellung.
FORM_VORGABE = "tanztheater"

#: Trennt zwei Fassungen im Feld ``szene.fruehere_fassungen``.
FASSUNGSTRENNER = "\n\n----- fruehere Fassung -----\n\n"

#: Die Anweisung fuer den Vorschlags-Aufruf. Bewusst kurz und ausdruecklich
#: auf das Format bezogen: der Marker ist die einzige Stelle, an der der Code
#: den Vorschlag wiederfindet (``vorschlag.lies``), und ein Vorschlag ohne
#: Marker bekommt keine Knoepfe -- geraten wird nichts.
ANWEISUNG_FOLGE = """Du planst mit einer Theatergruppe die Szenenfolge ihres Stuecks.

Schlage genau {anzahl} Szenen vor. Antworte in GENAU dieser Form, ohne
Einleitung und ohne Nachwort:

VORSCHLAG SZENENFOLGE:
Titel — ein Satz, was passiert — Figur, Figur
Titel — ein Satz, was passiert — Figur, Figur

Eine Zeile je Szene, {anzahl} Zeilen. Nimm nur Figuren, die unten im
Arbeitsstand stehen. Denk in Situationen: Ort, Beteiligte, was sich aendert.
Eine Szene ohne Veraenderung ist ein Gespraech, kein Theater -- eine Szene
ohne Konflikt dagegen schon.

Danach ein Satz und eine offene Frage an die Gruppe, hoechstens zwei Zeilen."""

#: Dasselbe fuer die fehlenden Felder EINER Szene. Der Anlass (Birk,
#: 05.09.2026): \"Passt, schreiben\" lief bis dahin in den Sperrtext
#: (``szene.sperrtext``) -- eine Liste dessen, was fehlt, und die Gruppe
#: musste es abtippen. Vorschlagen statt abfragen: der Bot legt hin, was er
#: aus dem Material weiss, die Gruppe tippt einen Knopf.
ANWEISUNG_FELDER = """Du planst mit einer Theatergruppe eine einzelne Szene.

Fuer die Szene unten fehlen noch Angaben: {felder}.

Schlage sie vor -- aus dem Material, das unten steht, nicht frei erfunden.
Antworte in GENAU dieser Form, ohne Einleitung und ohne Nachwort:

VORSCHLAG SZENE:
feld: Wert
feld: Wert

Eine Zeile je Feld, nur die fehlenden Felder, die Feldnamen genau so wie in
der Aufzaehlung oben. Danach ein Satz und eine offene Frage an die Gruppe,
hoechstens zwei Zeilen."""


class SzenenfolgeFehler(Exception):
    """Der Vorschlags-Aufruf lieferte nichts Verwertbares."""


# Eine Sperre je chat_id, wie in ``szene.py`` und ``ablauf.py``: zwei
# gleichzeitige Vorschlaege derselben Gruppe waeren zwei Listen im Chat, und
# die Gruppe wuesste nicht, welche gilt.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


# ---------------------------------------------------------------------------
# Vorschlag lesen
# ---------------------------------------------------------------------------

#: Trennzeichen einer Szenenzeile: \"Titel — was passiert — Mira, Pal\".
#: Derselbe Satz Trenner wie ``vorschlag._FIGUR_TRENNER`` -- Modelle liefern
#: Gedankenstrich und einfachen Bindestrich gemischt.
_TRENNER = re.compile(r"\s+[—–]\s+|\s+-\s+")


def zerlege(wert: str) -> list[tuple[str, str, list[str]]]:
    """Zerlegt den Szenenfolge-Block in ``(Titel, was_passiert, Figuren)``.

    Eine Zeile je Szene. Fuehrende Aufzaehlungszeichen (\"- \", \"1. \",
    \"Szene 1: \") fallen weg -- ein Modell nummeriert gern mit, und die
    Nummer vergibt der Code selbst. Zeilen ohne Titel fallen raus.

    Fehlt die dritte Spalte, bleibt die Figurenliste leer: eine Szene ohne
    Besetzung ist ein normaler Planungszustand (``szene.sperrtext`` sagt es
    spaeter), kein Grund, die ganze Zeile wegzuwerfen."""
    ergebnis: list[tuple[str, str, list[str]]] = []
    for zeile in (wert or "").splitlines():
        roh = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", zeile).strip()
        roh = re.sub(r"^\s*szene\s*\d{0,3}\s*[:.]\s*", "", roh, flags=re.IGNORECASE)
        if not roh:
            continue
        teile = [t.strip() for t in _TRENNER.split(roh)]
        titel = teile[0].strip(" .;:")
        if not titel:
            continue
        was = teile[1].strip() if len(teile) > 1 else ""
        figuren = []
        if len(teile) > 2:
            figuren = [f.strip(" .;:") for f in teile[2].split(",") if f.strip()]
        ergebnis.append((titel, was, figuren))
    return ergebnis


def lege_an(conn, chat_id: int, zeilen: list[tuple[str, str, list[str]]]) -> list[int]:
    """Legt aus einem Szenenfolge-Vorschlag die Szenen an und liefert ihre
    Nummern.

    **Ersetzend, nicht ergaenzend**: eine neue Folge ist eine neue Folge --
    haette die Gruppe nur eine Szene aendern wollen, haette sie das gesagt.
    Die alten Szenen werden weich entfernt (``repo.entferne_szene``, N3), also
    nicht geloescht: was schon geschrieben war, bleibt in der Datenbank.

    Die Besetzung wird nur gesetzt, soweit die Namen im Arbeitsstand stehen --
    eine Figur wird hier NIE angelegt. Figuren entstehen in Phase 4 mit
    Beschreibung und Interview; sie aus einer Szenenzeile zu raten waere genau
    der Fehler, den ``vorschlag.py`` vermeidet."""
    for alt in repo.hole_szenen(conn, chat_id):
        if alt["nummer"] is not None:
            repo.entferne_szene(conn, chat_id, alt["nummer"])
    nach_name = {f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)}
    nummern: list[int] = []
    for nummer, (titel, was, figuren) in enumerate(zeilen, start=1):
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
        if was:
            repo.setze_szenenfeld(conn, szene_id, "was_passiert", was)
        repo.setze_szenenfeld(conn, szene_id, "form", FORM_VORGABE)
        ids = [nach_name[n.lower()] for n in figuren if n.lower() in nach_name]
        if ids:
            repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
        nummern.append(nummer)
    return nummern


# ---------------------------------------------------------------------------
# Was im Chat steht
# ---------------------------------------------------------------------------


def vorstellung(conn, zeile) -> str:
    """Eine Szene, wie sie der Gruppe vorgestellt wird: alle Felder
    untereinander, fehlende Pflichtfelder als \"noch offen\" markiert.

    Deterministisch aus der Datenbank, kein Modellaufruf -- die Vorstellung
    ist eine Ansicht, keine Erfindung. Sie ist ausfuehrlicher als
    ``szene.planungszeile`` (eine Zeile, fuer Bestaetigungen): hier
    entscheidet die Gruppe, ob geschrieben werden darf."""
    from interview_theater import szene as szene_modul

    nummer = zeile["nummer"]
    kopf = f"Szene {nummer}" if nummer is not None else "Szene"
    if zeile["titel"]:
        kopf += f": {zeile['titel']}"
    fehlende, _ = szene_modul.fehlendes(conn, zeile)
    zeilen = [kopf]
    for feld in ("form", "ort", "zeit", "anlass", "figuren", "was_passiert",
                 "was_anders", "ton"):
        name = szene_modul.FELDNAMEN[feld]
        if feld == "figuren":
            namen = [f["name"] for f in repo.szene_figuren(conn, zeile["id"])]
            wert = ", ".join(namen)
        else:
            wert = (zeile[feld] or "").strip()
        if wert:
            zeilen.append(f"{name}: {wert}")
        elif feld in fehlende:
            zeilen.append(f"{name}: noch offen")
    ausserdem = [f for f in fehlende if f in szene_modul.ARBEITSSTAND_PFLICHTFELDER]
    if ausserdem:
        zeilen.append(
            "Es fehlt ausserdem: "
            + ", ".join(szene_modul.FELDNAMEN[f] for f in ausserdem)
        )
    return "\n".join(zeilen)


def ist_fertig(zeile) -> bool:
    """Hat die Gruppe diese Szene mit \"Passt\" abgenommen?

    Ueber eine eigene Spalte und nicht ueber \"hat Volltext\": ein
    geschriebener Text ist ein Entwurf, kein Ergebnis -- genau darum gibt es
    unter ihm die vier Knoepfe."""
    return bool("fertig_am" in zeile.keys() and zeile["fertig_am"])


def uebersicht(conn, chat_id: int) -> str:
    """Die Szenenfolge mit Status, wie sie Phase 7 (Durchlauf) zeigt.

    Drei Zustaende, in der Sprache der Gruppe: **fertig** (abgenommen),
    **geschrieben** (Text da, noch nicht abgenommen), **offen** (nur geplant).
    """
    zeilen = []
    for s in repo.hole_szenen(conn, chat_id):
        kopf = f"Szene {s['nummer']}" if s["nummer"] is not None else "Szene"
        if s["titel"]:
            kopf += f": {s['titel']}"
        if ist_fertig(s):
            stand = "fertig"
        elif (s["volltext"] or "").strip():
            stand = "geschrieben"
        else:
            stand = "offen"
        zeilen.append(f"{kopf} — {stand}")
    if not zeilen:
        return "Es gibt noch keine Szenen."
    return "Euer Durchlauf:\n" + "\n".join(zeilen)


def textbuch(conn, chat_id: int) -> str:
    """Alle Szenen als ein Textbuch (Markdown) -- der Datei-Export in Phase 7.

    Szenen ohne Volltext stehen mit ihrer Planung drin und nicht als Luecke:
    ein Textbuch, in dem Szene 4 fehlt, sieht aus wie ein Fehler; eines, in
    dem Szene 4 als \"noch nicht geschrieben\" steht, sagt die Wahrheit."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    teile = ["# Textbuch"]
    if stand and (stand["kernthema"] or "").strip():
        teile.append(f"Kernthema: {stand['kernthema'].strip()}")
    if stand and (stand["format"] or "").strip():
        teile.append(f"Format: {stand['format'].strip()}")
    for s in repo.hole_szenen(conn, chat_id):
        kopf = f"## Szene {s['nummer']}" if s["nummer"] is not None else "## Szene"
        if s["titel"]:
            kopf += f": {s['titel']}"
        teile.append(kopf)
        teile.append(vorstellung(conn, s))
        volltext = (s["volltext"] or "").strip()
        teile.append(volltext if volltext else "(noch nicht geschrieben)")
    return "\n\n".join(teile)


def dateiname(chat_id: int) -> str:
    """Der Name der Textbuch-Datei. Ohne chat_id im Namen: der Dateiname
    steht in der Gruppe und soll nichts ueber die Gruppe verraten."""
    return "textbuch.md"


# ---------------------------------------------------------------------------
# Die erwartete Regie-Notiz ("Passt, aber anders" unter einem Szenentext)
# ---------------------------------------------------------------------------
#
# Bewusst im Prozess und nicht in der Datenbank: es ist ein Zustand von
# Sekunden ("der Bot hat gerade gefragt, was anders werden soll"), kein Stand
# des Workshops. Nach einem Neustart ist er weg -- und das ist richtig, dann
# ist auch die Frage im Chat laengst nach oben gescrollt. Derselbe Gedanke wie
# bei ``szene._usa_erinnerungen``.
_regienotiz_erwartet: dict[int, int] = {}


def erwarte_regienotiz(chat_id: int, nummer: int) -> None:
    """Merkt: die naechste freie Nachricht dieser Gruppe ist die Regie-Notiz
    fuer Szene ``nummer``."""
    _regienotiz_erwartet[chat_id] = nummer


def nimm_regienotiz(chat_id: int) -> int | None:
    """Liefert die erwartete Szenennummer und vergisst sie -- einmalig, damit
    nicht jede weitere Nachricht die Szene neu schreiben laesst."""
    return _regienotiz_erwartet.pop(chat_id, None)


# ---------------------------------------------------------------------------
# Der Aufruf
# ---------------------------------------------------------------------------


def _material(conn, chat_id: int) -> str:
    """Was das Modell fuer einen Szenenfolge-Vorschlag braucht: Format und
    Rahmen, Kernthema, die Figuren, die bestehende Folge und das Verworfene.

    Aus ``szene.py`` geholt statt hier zweitgepflegt -- laeuft der Szenen-
    Prompt auseinander, laeuft auch dieser mit."""
    from interview_theater import szene as szene_modul

    bloecke = [
        szene_modul._format_rahmen_text(conn, chat_id),
        szene_modul._thema_text(conn, chat_id),
        szene_modul._figuren_text(conn, chat_id),
        szene_modul._continuity_text(conn, chat_id, None),
        szene_modul._verworfen_text(conn, chat_id),
    ]
    return "\n\n".join(b for b in bloecke if b)


def systemanweisung(anzahl: int) -> str:
    """Anweisung fuer den Folge-Aufruf: die Form (Marker!) plus der
    Phasenfokus aus ``prompts/phasen/6.md``, heiss nachgeladen.

    Die Phasendatei ist optional (``hole_optional``): fehlt sie am
    Workshoptag, entsteht trotzdem eine Szenenfolge."""
    teile = [ANWEISUNG_FOLGE.format(anzahl=anzahl)]
    phase = anweisungen.hole_optional("phasen/6")
    if phase and phase.strip():
        teile.append(phase.strip())
    return "\n\n".join(teile)


def baue_nutzertext(conn, chat_id: int, anzahl: int, wunsch: str | None = None) -> str:
    """Material, dann der Auftrag -- was am Ende steht, wiegt am schwersten
    (SPEC § 6.1), deshalb der Wunsch der Gruppe zuletzt."""
    teile = [_material(conn, chat_id)]
    auftrag = f"Euer Auftrag:\nSchlag {anzahl} Szenen vor."
    if wunsch and wunsch.strip():
        auftrag += f"\n{wunsch.strip()}"
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)


_TEXT_LAEUFT = "Ich schlage euch eine Szenenfolge vor, einen Moment."
_TEXT_BESETZT = "Ich denke gerade schon ueber die Szenenfolge nach, gleich."
_TEXT_FEHLER = (
    "Die Szenenfolge ist mir nicht gelungen. Sagt es nochmal, dann versuche "
    "ich es neu."
)
_TEXT_FELDER_LAEUFT = "Ich schlage die fehlenden Angaben vor, einen Moment."


def _sende(conn, tg, e, chat_id: int, text: str) -> None:
    """Wie ``szene._sende_und_merke``: die Zeile geht in die Gruppe UND ins
    Verlaufsfenster des naechsten Gespraechszugs."""
    from interview_theater import szene as szene_modul

    szene_modul._sende_und_merke(conn, tg, e, chat_id, text)


def _lauf(conn, tg, klm, e, chat_id: int, system: str, nutzer: str, art: str,
          sperre: threading.Lock, nachbereitung) -> None:
    """Der Thread-Rumpf: Modell fragen, Antwort mit Leiste ausspielen, Sperre
    in JEDEM Fall freigeben -- bliebe sie liegen, koennte die Gruppe fuer den
    Rest des Workshops keinen Vorschlag mehr bekommen (wie ``szene._lauf``)."""
    try:
        antwort = klm.prosa(
            chat_id, system, nutzer, art, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
        )
        if not (antwort or "").strip():
            raise SzenenfolgeFehler("Antwort des Sprachmodells war leer")
        nachbereitung(antwort)
    except Exception:
        log.exception("Szenenfolge-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None),
                "szenenfolge_fehlgeschlagen", "Szenenfolge-Aufruf fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall nicht schreibbar, chat_id=%s", chat_id)
        _sende(conn, tg, e, chat_id, _TEXT_FEHLER)
    finally:
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, anzahl: int | None = None,
           wunsch: str | None = None) -> threading.Thread | None:
    """Kuendigt an und gibt den Vorschlags-Aufruf an einen eigenen Thread ab.

    Liefert den Thread (fuer Tests) oder None, wenn nichts angestossen wurde.
    **Kein Modellaufruf im aufrufenden Thread** -- das ist die Bedingung
    dafuer, dass ein Knopf ihn ueberhaupt ausloesen darf (``knoepfe.py``,
    Zusage 2)."""
    if klm is None:
        log.error("Szenenfolge ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    anzahl = int(anzahl or ANZAHL_VORGABE)
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_LAEUFT)

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_szenenfolge(conn, tg, chat_id, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, systemanweisung(anzahl),
              baue_nutzertext(conn, chat_id, anzahl, wunsch), ART, sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread


def starte_feldvorschlag(conn, tg, klm, e, chat_id: int, ziel) -> threading.Thread | None:
    """Schlaegt die fehlenden Pflichtfelder EINER Szene vor -- der Ersatz fuer
    den Sperrtext an der Stelle \"Passt, schreiben\" (Birk, 05.09.2026).

    Der Sperrtext (``szene.sperrtext``) bleibt, wo er hingehoert: beim
    direkten Schreibauftrag. Wer dagegen gerade eine Szene vor Augen hat und
    \"Passt, schreiben\" tippt, soll nicht eine Liste von Luecken bekommen,
    sondern Vorschlaege mit Knoepfen darunter."""
    from interview_theater import szene as szene_modul

    if klm is None:
        log.error("Feldvorschlag ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    fehlende, _ = szene_modul.fehlendes(conn, ziel)
    # Die Arbeitsstand-Felder (Format, Rahmen) gehoeren in Phase 5 und werden
    # hier NICHT vorgeschlagen: sie haengen am Stueck, nicht an der Szene.
    fehlende = [f for f in fehlende if f not in szene_modul.ARBEITSSTAND_PFLICHTFELDER]
    if not fehlende:
        return None
    nummer = ziel["nummer"]
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None
    _sende(conn, tg, e, chat_id, _TEXT_FELDER_LAEUFT)
    system = ANWEISUNG_FELDER.format(felder=", ".join(fehlende))
    nutzer = "\n\n".join(
        t for t in (
            _material(conn, chat_id),
            szene_modul._diese_szene_text(conn, ziel),
            f"Euer Auftrag:\nSchlag die fehlenden Angaben fuer Szene {nummer} vor.",
        ) if t
    )

    def _fertig(antwort: str) -> None:
        from interview_theater import knoepfe

        knoepfe.sende_szenenfelder(conn, tg, chat_id, nummer, antwort)

    thread = threading.Thread(
        target=_lauf,
        args=(conn, tg, klm, e, chat_id, system, nutzer, ART_FELDER, sperre, _fertig),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread

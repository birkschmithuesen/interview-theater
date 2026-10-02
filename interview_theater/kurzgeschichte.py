"""Phase 6 als **eine Kurzgeschichte** (06.09.2026, Birk 11:50).

**Warum es das gibt.** Bis heute lief Phase 6 Szene fuer Szene: die Gruppe
bestaetigte eine Szene, ein Opus-Lauf schrieb sie als Prosa, dann die
naechste. Das ergab fuenf Texte, die einander nicht kannten -- jeder Lauf
sah nur Zusammenfassungen der Vorszenen. Birk hat es umgedreht: **ein**
Lauf schreibt die ganze Geschichte aus Setting, Figuren (mit ihrem
Sprachstil) und der gewaehlten Richtung.

**Wie viele Abschnitte, entscheidet die Szenenfolge** (Birk, 02.10.2026):
steht eine, bindet ihre Zahl -- ein Abschnitt je geplanter Szene, in deren
Reihenfolge. Die Zahl steht dafuer im **Auftrag** (``abschnittszahl``,
``_ZEILE_ABSCHNITTE``; bei aktivem Laengen-Profil traegt sie der
Budget-Block, ``laengen.SATZ_BINDUNG`` -- in beiden Faellen genau einmal).
Steht keine Szenenfolge, waehlt das Modell die Zahl selbst (typisch drei bis
sieben). Bis zum 02.10.2026 war sie immer frei; das kostete, weil
``lege_szenen_an`` nur **ergaenzend** abgleicht, bei zu wenigen Abschnitten
prosalose Szenen -- und Phase 7 verlangt Prosa fuer jede geplante Szene
(``phasen.voraussetzungen``).

**Danach werden die Abschnitte zu Szenen** -- Nummer, Titel, Prosa,
``was_passiert`` aus der Pflichtzeile "Zusammenfassung", Ort aus dem
Setting. Die bestehende Szenenfolge wird dabei ersetzt (weich, wie in
``szenenfolge.lege_an``), und das Journal haelt fest, dass sie aus der
Kurzgeschichte stammt.

Der Feinschliff (Phase 7) arbeitet danach je Abschnitt wie je Szene: Form
waehlen, uebersetzen.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Sequence

from interview_theater import anweisungen, repo

log = logging.getLogger(__name__)

ART = "kurzgeschichte"

#: Wie im Szenenlauf: Reasoning ist an, das Budget ist eine Obergrenze
#: gegen Durchdrehen (AGENTS.md Falle 4).
MAX_TOKENS = 200_000
TIMEOUT_S = 900.0

#: Die Ueberschrift eines Abschnitts. Zwei Formen, beide erlaubt --
#: ``## 1. Titel`` und ``ABSCHNITT 1: Titel``: Modelle liefern Markdown,
#: auch wenn der Prompt es nicht verlangt, und ein Abschnitt, der wegen
#: zweier Rauten verlorengeht, kostet einen ganzen Lauf.
_UEBERSCHRIFT = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:ABSCHNITT\s*)?(\d{1,2})[.):]\s*(.+?)\s*$",
    re.IGNORECASE,
)
#: Die Pflichtzeile je Abschnitt -- sie wird ``szene.was_passiert``.
_ZUSAMMENFASSUNG = re.compile(r"^\s*Zusammenfassung\s*:\s*(.+)$", re.IGNORECASE)

#: Dasselbe auf Englisch (Karte A1, K5): ``SECTION 1: …``/``PART 1: …`` und
#: ``Summary: …``. Beide werden probiert, deutsch zuerst.
_UEBERSCHRIFT_EN = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:(?:ABSCHNITT|SECTION|PART)\s*)?(\d{1,2})[.):]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_ZUSAMMENFASSUNG_EN = re.compile(r"^\s*Summary\s*:\s*(.+)$", re.IGNORECASE)

#: Die eine Zeile in ``ANWEISUNG``, die ein Laengenbudget ersetzt
#: (30.09.2026, Karte R). Sie steht als eigener Absatz und kommt genau
#: einmal vor -- ein Test haelt beides fest, denn eine Ersetzung, die ins
#: Leere greift, waere ein stiller Durchfall: der Prompt behielte die feste
#: Zahl, das Budget stuende daneben, und das Modell muesste raten.
#:
#: **Sie bleibt zeichengleich.** Ohne Budget ist ``systemanweisung()`` genau
#: der Text, der vor dieser Karte entstand (gemessen: 12.785 Zeichen,
#: sha256 704119e3...). ``ANWEISUNG`` bleibt deshalb woertlich unveraendert
#: (sie traegt geschweifte Klammern, ``format`` scheidet aus) --
#: ``systemanweisung`` ersetzt die Zeile per ``str.replace``.
ZEILE_GESAMTLAENGE = "Insgesamt 1.500 bis 3.500 Woerter."

ANWEISUNG = """Du schreibst die Kurzgeschichte eines Theaterstuecks.

Unten stehen das Setting, die Figuren mit ihrem Sprachstil und die
Geschichte, auf die sich die Gruppe geeinigt hat. Daraus schreibst du EINE
zusammenhaengende Kurzgeschichte -- keine Szenenliste, kein Theatertext,
kein Drehbuch.

**Nennt der Auftrag eine Abschnittszahl, ist sie verbindlich**: dann steht
schon eine Szenenfolge, und du schreibst genau so viele Abschnitte, in
dieser Reihenfolge -- keinen dazu, keinen weg, keinen umgestellt. Nennt er
keine, waehlst du die Zahl der Abschnitte selbst an der Geschichte (typisch
drei bis sieben).

Insgesamt 1.500 bis 3.500 Woerter.

Jeder Abschnitt beginnt mit einer Ueberschrift und einer Pflichtzeile:

```
1. Titel des Abschnitts
Zusammenfassung: ein Satz, was in diesem Abschnitt passiert

<der Abschnitt als erzaehlende Prosa>

2. Titel des naechsten Abschnitts
Zusammenfassung: ein Satz
...
```

Die Zeile `Zusammenfassung:` ist **Pflicht** -- aus ihr entsteht spaeter die
Planung der Szene. Ohne sie faellt der Abschnitt durch.

Die Regeln fuer den Text selbst stehen unten (Prosa-Regelblock). Kein
Kommentar davor oder danach, keine Moral am Schluss, keine Zwischentitel
ausser den Abschnitts-Ueberschriften."""

_TEXT_LAEUFT = (
    "Ich schreibe eure Geschichte jetzt am Stueck. Das dauert ein paar Minuten."
)
_TEXT_BESETZT = "Ich schreibe schon, einen Moment."
_TEXT_FEHLER = (
    "Die Geschichte ist mir nicht gelungen. Sagt es nochmal, dann versuche "
    "ich es neu."
)
_TEXT_FERTIG = "Eure Geschichte in {anzahl} Abschnitten:"
JOURNAL = "Szenenfolge aus der Kurzgeschichte: {anzahl} Abschnitte"
#: Der Titel eines Abschnitts, der ohne eigene Ueberschrift kam.
_ABSCHNITT_N = "Abschnitt {nummer}"

_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()


def _sperre_fuer(chat_id: int) -> threading.Lock:
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


def laeuft(chat_id: int) -> bool:
    """Schreibt gerade ein Lauf fuer diese Gruppe?"""
    return _sperre_fuer(chat_id).locked()


def zerlege(text: str) -> list[tuple[str, str, str]]:
    """Zerlegt eine Kurzgeschichte in ``(Titel, Zusammenfassung, Prosa)``
    je Abschnitt.

    Deterministisch und nachsichtig: eine Ueberschrift beginnt einen neuen
    Abschnitt, die erste ``Zusammenfassung:``-Zeile darunter gehoert dazu,
    alles weitere ist der Text. Abschnitte ohne Text fallen weg -- eine
    Ueberschrift allein ist keine Szene."""
    abschnitte: list[tuple[str, str, list[str]]] = []
    for zeile in (text or "").splitlines():
        treffer = _UEBERSCHRIFT.match(zeile) or _UEBERSCHRIFT_EN.match(zeile)
        if treffer is not None and len(treffer.group(2)) <= 80:
            abschnitte.append((treffer.group(2).strip(" .:—-"), "", []))
            continue
        if not abschnitte:
            continue
        titel, fassung, koerper = abschnitte[-1]
        zusammen = (_ZUSAMMENFASSUNG.match(zeile)
                    or _ZUSAMMENFASSUNG_EN.match(zeile))
        if zusammen is not None and not fassung:
            abschnitte[-1] = (titel, zusammen.group(1).strip(), koerper)
            continue
        koerper.append(zeile)
    ergebnis: list[tuple[str, str, str]] = []
    for titel, fassung, koerper in abschnitte:
        prosa = "\n".join(koerper).strip()
        if prosa:
            ergebnis.append((titel, fassung, prosa))
    return ergebnis


def lege_szenen_an(conn, chat_id: int, abschnitte) -> list[int]:
    """Gleicht die Abschnitte mit der bestehenden Szenenfolge ab --
    **abgleichend**, wie ``szenenfolge.lege_an`` (06.09.2026).

    Je Abschnitt: Nummer, Titel, ``prosa``, ``was_passiert`` aus der
    Zusammenfassung und der Ort aus dem Setting (``szene.uebernimm_rahmen``).
    ``form`` bleibt leer: sie entscheidet die Gruppe im Feinschliff.

    Bis zu diesem Umbau entfernte diese Funktion **alle** bestehenden Szenen
    weich und legte danach neue an -- im Live-Fall Gruppe 1 zum zweiten Mal
    an einem Nachmittag, diesmal samt der schon geschriebenen Prosa. Jetzt
    gilt: gleiche Nummer -> aktualisieren, fehlende -> ergaenzen,
    ueberzaehlige -> stehen lassen.

    ``prosa`` und ``volltext`` sind hier ausdruecklich ueberschreibbar: der
    Prosa-Lauf ist ihr Verfasser, und die Gruppe hat ihn gerade selbst per
    Knopf gestartet. Die **Formfestlegung** (``form``, ``form_vorschlag``,
    ``stil``) bleibt dagegen unangetastet -- die traegt ein Knopfdruck, kein
    Modelllauf."""
    from interview_theater import szene as szene_modul

    zeilen = [
        {
            "titel": titel or T._ABSCHNITT_N.format(nummer=nummer),
            "was_passiert": fassung,
            "kurzbeschreibung": fassung,
            "zusammenfassung": fassung,
            "prosa": prosa,
        }
        for nummer, (titel, fassung, prosa) in enumerate(abschnitte, start=1)
    ]
    bericht = repo.gleiche_szenenfolge_ab(
        conn, chat_id, zeilen, ueberschreibbar=("prosa",)
    )
    for nummer in bericht["nummern"]:
        szene_modul.uebernimm_rahmen(conn, chat_id, bericht["ids"][nummer])
    # Auch der Prosalauf ist ein erfolgreicher Szenenlauf und haengt seine
    # Fassung an (06.09.2026). Steht hier NACH ``gleiche_szenenfolge_ab``,
    # damit die Fassung an der Szene haengt, die am Ende wirklich existiert.
    for nummer, (_titel, fassung, prosa) in enumerate(abschnitte, start=1):
        szene_id = bericht["ids"].get(nummer)
        if szene_id is None:
            continue
        repo.haenge_szenenfassung_an(
            conn, chat_id, szene_id, prosa, fassung or None,
        )
    nummern = list(bericht["nummern"])
    repo.schreibe_journal(
        conn, chat_id, "entschieden", T.JOURNAL.format(anzahl=len(nummern)),
        quelle="szene",
    )
    return nummern


def systemanweisung(budgets: Sequence[int] | None = None) -> str:
    """Die Anweisung plus dem Prosa-Regelblock -- heiss nachgeladen wie jeder
    Prompt.

    ``budgets`` (30.09.2026, Karte R) sind die Wortbudgets der Abschnitte.
    Sind sie da, tritt ihre **Summe** an die Stelle der festen Zeile
    ``ZEILE_GESAMTLAENGE``; die Liste je Abschnitt steht im **Nutzertext**,
    weil sie je Gruppe verschieden ist. Ein Fakt hat genau eine Stelle im
    Prompt (Prompt-Audit 06.09.2026) -- deshalb wird die feste Zeile
    **ersetzt** und nicht ergaenzt.

    Ohne ``budgets`` ist der Text **zeichengleich** zu dem Stand vor dieser
    Karte (gemessen: 12.785 Zeichen). Daran haengt die Zusage an Dortmund."""
    anweisung = T.ANWEISUNG
    if budgets:
        from interview_theater import laengen

        anweisung = anweisung.replace(
            T.ZEILE_GESAMTLAENGE, laengen.gesamtzeile(budgets),
        )
    teile = [anweisung]
    prosa = anweisungen.hole_optional("formen/prosa")
    if prosa and prosa.strip():
        teile.append(prosa.strip())
    tells = anweisungen.hole_optional("theater-tells")
    if tells and tells.strip():
        teile.append(tells.strip())
    return "\n\n".join(teile)


#: Die Ueberschrift des Blocks mit der bestehenden Fassung (30.09.2026,
#: Kuerzen). Nur gesetzt, wenn ``vorlage`` an ist: ein Auftrag "25 Prozent
#: kuerzer" ueber einen Text, den das Modell nie sah, ist ein Neuschrieb.
UEBERSCHRIFT_VORLAGE = (
    "Die bisherige Fassung, die ihr ueberarbeitet (Abschnitt fuer Abschnitt):"
)


def vorlage_text(conn, chat_id: int) -> str:
    """Die bestehenden Abschnitte mit Prosa -- Ueberschrift und Text, in der
    Reihenfolge der Szenennummern -- als ein Block, oder "", wenn es keine
    gibt. Reine Leseabfrage."""
    from interview_theater import szene as szene_modul

    abschnitte = []
    szenen = sorted(
        repo.hole_szenen(conn, chat_id), key=lambda s: s["nummer"] or 0
    )
    for s in szenen:
        prosa = szene_modul.prosa_von(s)
        if not prosa:
            continue
        titel = (s["titel"] or "").strip() or T._ABSCHNITT_N.format(nummer=s["nummer"])
        abschnitte.append(f"{s['nummer']}. {titel}\n\n{prosa}")
    if not abschnitte:
        return ""
    return T.UEBERSCHRIFT_VORLAGE + "\n\n" + "\n\n".join(abschnitte)


#: Die Koepfe des Nutzertexts (W3).
_STILE_KOPF = "So sprechen die Figuren:\n"
_AUFTRAG = "Euer Auftrag:\nSchreib die Geschichte am Stueck."
#: Die bindende Abschnittszahl (02.10.2026, Karte P2-Fix, Birks
#: Entscheidung). Sie steht im **Auftrag** und nicht in der
#: Systemanweisung: nur der Nutzertext kennt die Datenlage.
#:
#: Eigener Wortlaut, nicht der von ``laengen.SATZ_BINDUNG`` -- der sagt
#: zusaetzlich "mit diesen Laengen" und gehoert zum Budget-Block. Beide
#: stehen nie zusammen in einem Prompt (siehe ``baue_nutzertext``).
_ZEILE_ABSCHNITTE = (
    "\nSchreib genau {anzahl} Abschnitte -- einen je geplanter Szene, in "
    "deren Reihenfolge."
)
_ZEILE_REGIE = "\nDie Gruppe sagt dazu: {regie}"


def abschnittszahl(conn, chat_id: int) -> int:
    """Wie viele Abschnitte die Geschichte haben MUSS -- die Zahl der
    geplanten Szenen, oder ``0``.

    **Dieselbe Menge, mit der ``lege_szenen_an`` abgleicht und die
    ``budget_eintraege`` bemisst**: ``repo.hole_szenen`` filtert
    ``entfernt_am IS NULL`` selbst (``repo.py:2286-2290``). Zwei verschiedene
    Zaehlungen waeren zwei Wahrheiten -- die eine im Prompt, die andere beim
    Speichern.

    ``0`` heisst "keine Szenenfolge": dann waehlt das Modell die Zahl selbst,
    und im Auftrag steht gar keine Zeile (datengetrieben wie
    ``kontext.baue``). Das ist nicht nur Theorie -- die Phase setzt allein
    die Gruppe, und wer mit ``/phase 6`` ohne Szenen dort landet, soll
    schreiben koennen.

    Reine Leseabfrage, kein Modellaufruf."""
    return len(repo.hole_szenen(conn, chat_id))


def budget_eintraege(conn, chat_id: int,
                     faktor: float = 1.0) -> list[tuple[int, str, int]]:
    """Je Abschnitt ``(nummer, form, budget)`` -- oder ``[]``, wenn dieses
    Profil keine Budgets waehlt.

    **Die Zahl der Abschnitte steht hier schon fest**: Phase 6 ist erst
    erreichbar, wenn mindestens eine Szene angelegt ist
    (``phasen.voraussetzungen``), und ``prompts/formen/prosa.md`` erklaert
    eine vorhandene Szenenfolge fuer verbindlich. Die **Form** kommt aus
    ``laengen.form_der_szene``: bestaetigt (``szene.form``) vor
    vorgeschlagen (``form_vorschlag``) vor Profilvorgabe. Gelesen, nicht
    geschrieben -- ``szene.form`` bleibt unberuehrt, sie bestaetigt allein
    die Gruppe.

    Reine Leseabfrage, kein Modellaufruf."""
    from interview_theater import laengen

    if not laengen.aktiv():
        return []
    szenen = sorted(
        (s for s in repo.hole_szenen(conn, chat_id) if not s["entfernt_am"]),
        key=lambda s: s["nummer"] or 0,
    )
    if not szenen:
        return []
    nummern = [s["nummer"] or i + 1 for i, s in enumerate(szenen)]
    formen = [laengen.form_der_szene(s) for s in szenen]
    werte = laengen.budgets(formen, nummern=nummern, seed=chat_id, faktor=faktor)
    # Eine ausdrueckliche Laengenansage der Gruppe deckelt -- nach dem Faktor.
    ansage = laengen.woerter_aus_festlegungen(repo.festlegungen(conn, chat_id))
    werte = [laengen.budget_mit_ansage(w, ansage) for w in werte]
    return list(zip(nummern, formen, werte))


def baue_nutzertext(
    conn, chat_id: int, regie: str | None = None, vorlage: bool = False,
    eintraege: Sequence[tuple[int, str, int]] | None = None,
) -> str:
    """Setting, Figuren mit Sprachstil, Geschichte, die bestehende
    Szenenfolge -- und eine Regie-Notiz, wenn die Gruppe eine hatte.

    ``vorlage`` an (Kuerzen): die bestehende Fassung steht als eigener Block
    vor dem Auftrag. Ohne ``vorlage`` bleibt der Nutzertext zeichengleich
    wie vorher. Eine Eingabe-Budgetpruefung gibt es in diesem Lauf nicht --
    der Block ist hoechstens die eine Geschichte (1.500 bis 3.500 Woerter).

    ``eintraege`` (30.09.2026, Karte R) sind die Wortbudgets je Abschnitt.
    Ohne sie -- und mit einer leeren Liste -- bleibt der Nutzertext
    **zeichengleich** wie vorher; der Block faellt ersatzlos weg,
    datengetrieben wie in ``kontext.baue``. Er steht **vor** dem Auftrag,
    nahe am Ende: das Ende des Prompts wiegt am schwersten (SPEC § 6.1).

    Die **bindende Abschnittszahl** steht im Auftrag, sobald Szenen geplant
    sind (``abschnittszahl``) -- es sei denn, der Budget-Block traegt sie
    schon (``laengen.SATZ_BINDUNG``). Ohne geplante Szenen und ohne
    ``eintraege`` bleibt der Nutzertext **zeichengleich** wie vorher."""
    from interview_theater import laengen, szenenfolge

    teile = [szenenfolge._erfundenes(conn, chat_id)]
    stile = [
        f"- {f['name']}: {(f['sprachstil'] or '').strip()}"
        for f in repo.figuren(conn, chat_id)
        if (f["sprachstil"] or "").strip()
    ]
    if stile:
        teile.append(T._STILE_KOPF + "\n".join(stile))
    if vorlage:
        teile.append(vorlage_text(conn, chat_id))
    if eintraege:
        teile.append(laengen.block_prosa(eintraege))
    auftrag = T._AUFTRAG
    # Die bindende Abschnittszahl (02.10.2026, Birks Entscheidung) -- aber
    # nur, wenn der Budget-Block sie nicht schon traegt: ``block_prosa``
    # haengt ``laengen.SATZ_BINDUNG`` an jede Budget-Liste. Zwei bindende
    # Saetze in einem Prompt waeren eine Doppelnennung, und bei aktivem
    # Laengen-Profil traefe das jeden echten Lauf (``schreibe`` holt die
    # Eintraege immer). Ein Fakt hat genau eine Stelle im Prompt.
    if not eintraege:
        anzahl = abschnittszahl(conn, chat_id)
        if anzahl:
            auftrag += T._ZEILE_ABSCHNITTE.format(anzahl=anzahl)
    if regie and regie.strip():
        auftrag += T._ZEILE_REGIE.format(regie=regie.strip())
    teile.append(auftrag)
    return "\n\n".join(t for t in teile if t)


def _faktor(conn, chat_id: int) -> float:
    """Der Laengen-Faktor der Gruppe, oder 1,0. Eine Zeile, aber an zwei
    Stellen gebraucht (Nutzertext und Journalzeile) -- und zweimal gelesen
    waeren zwei Wahrheiten."""
    from interview_theater import laengen

    return laengen.faktor_aus_stand(repo.hole_arbeitsstand(conn, chat_id))


def hole_text(conn, klm, e, chat_id: int, regie: str | None = None,
              vorlage: bool = False,
              eintraege: Sequence[tuple[int, str, int]] | None = None,
              art: str = ART) -> str:
    """**Nur** der Modellaufruf -- Prompt bauen, fragen, Antwort liefern.

    Kein Speichern, keine Chatnachricht, keine Sperre. Herausgezogen am
    30.09.2026 (Karte R), weil der Nachpass die Antwort **pruefen** muss,
    bevor sie in der Datenbank steht: hat sie eine andere Abschnittszahl oder
    fehlt ein Belegzitat, wird sie verworfen und die alte Fassung bleibt.

    ``art`` landet in der Tabelle ``aufruf`` und macht Nachpass-Laeufe
    getrennt zaehlbar."""
    from interview_theater import szene_claude

    system = systemanweisung([b for _n, _f, b in (eintraege or [])] or None)
    nutzer = baue_nutzertext(conn, chat_id, regie, vorlage=vorlage,
                             eintraege=eintraege)
    if szene_claude.ist_aktiv(e, conn, chat_id):
        import httpx

        return szene_claude.prosa(
            conn, e,
            getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
            chat_id, system, nutzer, art, timeout=TIMEOUT_S,
        )
    return klm.prosa(chat_id, system, nutzer, art,
                     max_tokens=MAX_TOKENS, timeout=TIMEOUT_S)


def schreibe(conn, tg, klm, e, chat_id: int, regie: str | None = None,
             vorlage: bool = False, art: str = ART, zeilen=None) -> list[int]:
    """Der ganze Lauf, **synchron und ohne Sperre**: Modell fragen, zerlegen,
    Szenen anlegen, in den Chat melden. Liefert die Nummern der Abschnitte.

    Wie ``szene.schreibe`` verhaelt es sich zu ``starte``: die Sperre haelt
    der Aufrufer (``_lauf``), Fehler fliegen heraus. Wer es direkt ruft
    (Tests, der Nachpass), kuemmert sich selbst darum.

    ``zeilen`` ist die sichtbare Arbeitszeile des Aufrufers; sie wird wie
    bisher **vor** der Fertig-Meldung gestoppt."""
    eintraege = budget_eintraege(conn, chat_id, faktor=_faktor(conn, chat_id))
    antwort = hole_text(conn, klm, e, chat_id, regie, vorlage, eintraege, art)
    abschnitte = zerlege(antwort or "")
    if not abschnitte:
        raise ValueError("Kurzgeschichte ohne erkennbare Abschnitte")
    nummern = lege_szenen_an(conn, chat_id, abschnitte)
    if eintraege:
        # Der Wuerfel ist reproduzierbar (Seed = chat_id), aber niemand soll
        # ihn nachrechnen muessen, um zu verstehen, warum Abschnitt 2 laenger
        # sein durfte. Angehaengt, nie geaendert.
        from interview_theater import laengen

        repo.schreibe_journal(
            conn, chat_id, laengen.JOURNAL_ART,
            laengen.journalzeile(
                seed=chat_id, muster=laengen.muster_fuer(chat_id),
                faktor=_faktor(conn, chat_id), eintraege=eintraege,
            ),
            quelle=laengen.JOURNAL_QUELLE,
        )
    from interview_theater import knoepfe, szene as szene_modul

    if zeilen is not None:
        zeilen.stoppe()
    szene_modul._sende_und_merke(
        conn, tg, e, chat_id, T._TEXT_FERTIG.format(anzahl=len(nummern)),
    )
    knoepfe.zeige_kurzgeschichte(conn, tg, chat_id)
    return nummern


def starte(
    conn, tg, klm, e, chat_id: int, regie: str | None = None,
    vorlage: bool = False,
):
    """Kuendigt an und gibt den Lauf an einen eigenen Thread ab
    (Zusage 2: kein Modellaufruf im Knopf-Handler).

    ``vorlage`` reicht an ``baue_nutzertext`` durch: das Kuerzen braucht die
    bestehende Fassung im Prompt."""
    if klm is None:
        log.error("Kurzgeschichte ohne Sprachmodell, chat_id=%s", chat_id)
        return None
    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        tg.sende(chat_id, T._TEXT_BESETZT)
        return None
    from interview_theater import szene as szene_modul

    szene_modul._sende_und_merke(conn, tg, e, chat_id, T._TEXT_LAEUFT)

    def _lauf() -> None:
        from interview_theater import arbeitszeilen

        zeilen = arbeitszeilen.sichtbar(tg, chat_id, "prosa")
        try:
            schreibe(conn, tg, klm, e, chat_id, regie, vorlage=vorlage,
                     zeilen=zeilen)
            # Der Nachpass (30.09.2026, Karte R): EIN Lauf fuer alle
            # Abschnitte, im selben Thread und unter derselben Sperre. Im
            # ``try``, weil es nach einem gescheiterten Lauf keine Geschichte
            # gibt, ueber die nachzuzaehlen waere. Er geht ueber
            # ``hole_text`` und nie ueber ``schreibe``, kommt hier also nie
            # wieder vorbei -- eine ``art``-Wache wie in ``szene._lauf``
            # braucht er nicht. Ohne aktives Profil ein No-Op.
            from interview_theater import nachpass

            # Eigenes ``try`` wie in ``szene._lauf`` (Schlussreview I1): die
            # Geschichte steht schon -- ein reissender Nachpass ist ein
            # Vorfall, keine Fehlerzeile an die Gruppe.
            try:
                nachpass.nach_geschichte(conn, tg, klm, e, chat_id)
            except Exception:
                log.exception("Prosa-Nachpass gescheitert, chat_id=%s", chat_id)
                nachpass._vorfall(conn, chat_id, e, nachpass.VORFALL_FEHLER,
                                  "Prosa-Nachpass gescheitert")
        except Exception:
            log.exception("Kurzgeschichte fehlgeschlagen, chat_id=%s", chat_id)
            try:
                # Tagesdeckel (Karte Padua S): Pause statt Fehlerzeile -- und
                # zuerst geprueft, damit bei Deckel nicht zusaetzlich ein
                # "kurzgeschichte_fehlgeschlagen"-Vorfall fuer denselben Lauf
                # entsteht.
                from interview_theater import kosten

                if not kosten.melde_pause_wenn_deckel(conn, tg, e, chat_id):
                    repo.merke_vorfall(
                        conn, chat_id, getattr(e, "bot_name", None),
                        "kurzgeschichte_fehlgeschlagen", "Lauf gescheitert",
                    )
                    szene_modul._sende_und_merke(conn, tg, e, chat_id, T._TEXT_FEHLER)
            except Exception:
                log.exception("Fehlermeldung zur Kurzgeschichte fehlgeschlagen")
        finally:
            zeilen.stoppe()
            sperre.release()

    thread = threading.Thread(target=_lauf, daemon=True)
    try:
        thread.start()
    except Exception:
        sperre.release()
        raise
    return thread


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

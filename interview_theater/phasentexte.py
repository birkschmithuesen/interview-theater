"""Der einheitliche Phasenrahmen im Chat: Eintritt, Abschluss, Parameterliste.

**Warum es das gibt** (Birk, 06.09.2026, 01:25). Bis dahin sah jeder
Phasenwechsel anders aus: mal eine Zeile "Wir sind jetzt bei 4 · Setting &
Figuren", mal der Leitfaden, mal die Szenenfolge, mal gar nichts -- und was
eine Phase ueberhaupt will und was am Ende dastehen soll, stand nur im
Prompt, also nie im Chat. Eine Gruppe, die um 14 Uhr in eine Station kommt,
hatte damit keinen Anhaltspunkt, wo sie ist und wann sie fertig ist.

Jetzt hat jede der acht Phasen im Chat **dieselbe Form**, zweimal:

* beim **Eintritt** eine Nachricht mit Kopfzeile, Einleitung und der
  Checkliste der Parameter, die diese Phase setzt (``eintritt``),
* beim **Abschluss** -- in dem Moment, in dem die naechste Phase moeglich
  wird -- eine Nachricht mit denselben Parametern, jetzt mit ihren Werten
  (``abschluss``, verschickt aus ``knoepfe.biete_phase_proaktiv``).

**Deterministisch, kein Modellaufruf.** Beides sind Bot-Texte an die Gruppe
und **keine Prompts**: sie gehen nie an ein Modell, sondern direkt in den
Chat. Deshalb liegen die Einleitungen hier als Daten und nicht unter
``prompts/`` -- ein Prompt-Text, den das Modell nachplappert, waere genau der
Fehler, den ``tests/test_anweisungen.py`` seit dem 05.09.2026 verhindert.

**Eine Parameterliste, drei Leser.** ``parameterzeilen`` ist die einzige
Stelle, an der steht, welche Phase was setzt: die Checkliste beim Eintritt,
die Wertezeilen beim Abschluss und ``/stand`` lesen alle aus ihr. Ein
zweiter Ort waere ein zweiter Stand.

**Telegram-Format:** ``telegram.sende`` schickt ohne ``parse_mode``, also
reinen Text. Kein Fettdruck, keine Tabellen -- die Struktur traegt das
Emoji in der Kopfzeile und die Einrueckung.
"""

from collections.abc import Callable

from interview_theater import phasen, repo

#: Wie lang ein einzelner Wert in einer Parameterzeile werden darf. Laenger
#: gekuerzt (``_kuerze``): der Abschluss ist eine Quittung, keine Ausgabe des
#: Arbeitsstands -- wer den Wortlaut will, fragt den Stand ab oder liest die
#: Gruppenseite.
WERT_GRENZE = 120

#: Trenner in Aufzaehlungen innerhalb einer Zeile (Figuren, Szenen, Fragen).
#: Derselbe Punkt wie in ``phasen.bezeichnung`` -- eine Schreibweise.
TRENNER = " · "

#: Wie lang eine Einleitung hoechstens sein darf. Geprueft in
#: ``tests/test_phasentexte.py``: vier Saetze sind ein Rahmen, kein Vortrag.
EINLEITUNG_GRENZE = 400

#: Die Einleitung je Phase -- zwei bis vier Saetze: was hier passiert, was
#: die Gruppe tut, was ich tue, was am Ende steht.
#:
#: Zielgruppe sind junge Frauen zwischen 15 und 18 (AGENTS.md, "Rahmen des
#: Stuecks"), angesprochen mit "ihr". Keine Eigennamen -- weder erfundene
#: Figuren noch Orte: was hier als Beispiel steht, taucht spaeter als
#: Vorschlag des Bots wieder auf. Keine Slash-Befehle: beworben wird der
#: Knopf (AGENTS.md, "Slash-Befehle werden nicht mehr beworben").
EINLEITUNGEN = {
    1: (
        "Hier kommt eure Begriffsliste aus dem Plenum zu mir. Ihr schickt "
        "sie getippt oder als Sprachnachricht, so wie sie bei euch an der "
        "Wand steht. Ich halte sie fest, ordne sie und frage nach, wo ein "
        "Begriff noch zu gross ist. Am Ende stehen die Kernbegriffe, mit "
        "denen ihr weiterarbeitet."
    ),
    2: (
        "Aus euren Begriffen werden jetzt die Interviewfragen. Ich schlage "
        "euch zehn vor, ihr tippt genau drei davon an. Danach schauen wir, "
        "welche Frage heikel ist und was ihr vorher dazu sagt, und womit ihr "
        "ein Gespraech anfangt und aufhoert. Am Ende habt ihr einen "
        "Leitfaden zum Mitnehmen."
    ),
    3: (
        "Jetzt fuehrt ihr die Interviews. Den Leitfaden habt ihr dabei, "
        "aufgenommen wird ueber euer Handy: Aufnahme starten, so viele "
        "Sprachnachrichten schicken wie noetig, und ich tippe alles mit. "
        "Sagt ihr mir, dass ein Interview fertig ist, fasse ich zusammen, "
        "was darin steckt."
    ),
    4: (
        "Ab hier wird erfunden. Ihr denkt euch aus, worin euer Stueck spielt "
        "-- Ort, Zeit, Anlass -- und wer darin vorkommt. Die Interviews "
        "bleiben dabei absichtlich zu; sie kommen spaeter dazu und schaerfen, "
        "was ihr jetzt baut. Am Ende steht euer Setting und eine "
        "Figurenliste, die ihr abgenommen habt."
    ),
    5: (
        "Jetzt die Geschichte, im Groben: was passiert und wie es ausgeht. "
        "Kein Wortlaut, sondern der Bogen -- und dazu die Szenenfolge mit "
        "Titel, einem Satz, den Figuren und einem Vorschlag fuer die Form. "
        "Auch das erfindet ihr frei, ohne Material."
    ),
    6: (
        "Jetzt kommen die Interviews zurueck. Ich lege neben jede Szene und "
        "jede Figur die Stellen aus euren Aufnahmen, die dazu passen, mit "
        "dem woertlichen Zitat. Eure Geschichte aendert sich dadurch nicht, "
        "sie wird genauer. Ihr entscheidet Vorschlag fuer Vorschlag und "
        "koennt noch eine Runde drehen."
    ),
    7: (
        "Jetzt werden die Texte geschrieben, Szene fuer Szene. Zuerst "
        "bestaetigt ihr die Form -- Dialog, Monolog, Chor, Lied oder Rap --, "
        "dann schreibe ich die Szene, und ihr sagt mir, was anders werden "
        "soll. So lange, bis sie sitzt. Am Ende steht zu jeder Szene ein "
        "Text."
    ),
    8: (
        "Hier seht ihr euer Textbuch am Stueck, koennt "
        "es euch als Datei schicken lassen und einzelne Szenen noch einmal "
        "aufmachen. Wir achten auf die Uebergaenge und darauf, was sich beim "
        "Sprechen sperrig anfuehlt."
    ),
}

#: Was statt der Einleitung von Phase 8 dasteht, solange **nicht** jede
#: Szene einen Text hat (06.09.2026, in der Simulation gemessen).
#:
#: Der alte Text fing mit "Alle Szenen stehen" an -- ein Satz ueber die
#: Datenlage, den der Text nicht geprueft hat. Im Lauf tag1-gruppe2 sprang
#: der Bot mitten im Szenenschritt nach Phase 8 und behauptete das, waehrend
#: keine einzige Szene geschrieben war; der naechste Knopfdruck antwortete
#: mit "Szene 1 ist noch nicht geschrieben". Eine Behauptung ueber den Stand
#: gehoert an die Daten gebunden, sonst ist sie ein Versprechen.
EINLEITUNG_8_OFFEN = (
    "Hier seht ihr euer Textbuch am Stueck. Ein Teil der Szenen ist noch "
    "ungeschrieben - tippt eine davon an, dann hole ich das nach. Bei den "
    "fertigen achten wir auf die Uebergaenge und darauf, was sich beim "
    "Sprechen sperrig anfuehlt."
)


def _einleitung(conn, chat_id: int, phase: int) -> str:
    """Die Einleitung einer Phase -- fuer Phase 8 abhaengig davon, ob
    wirklich jede Szene einen Text hat."""
    if phase != 8:
        return EINLEITUNGEN.get(phase, "")
    szenen = repo.hole_szenen(conn, chat_id)
    if szenen and all((s["volltext"] or "").strip() for s in szenen):
        return "Alle Szenen stehen. " + EINLEITUNGEN[8]
    return EINLEITUNG_8_OFFEN

#: Die feste Zeile vor der Checkliste beim Eintritt.
_KOPF_EINTRITT = "▶️ Phase {nummer} von {gesamt} · {name}"
_ZEILE_CHECKLISTE = "Dafuer braucht es: {liste}"
_KOPF_ABSCHLUSS = "✅ Phase {bezeichnung} abgeschlossen"
_ERLEDIGT = "✅"
_OFFEN = "⬜"


def _kuerze(wert: str, grenze: int = WERT_GRENZE) -> str:
    """Kuerzt einen Wert auf ``grenze`` Zeichen, mit Auslassungszeichen.

    An einer Wortgrenze, wenn es eine gibt: ein mitten im Wort abgeschnittener
    Satz liest sich wie ein Fehler, nicht wie eine Kuerzung."""
    text = " ".join((wert or "").split())
    if len(text) <= grenze:
        return text
    schnitt = text[: grenze - 1]
    if " " in schnitt[grenze // 2:]:
        schnitt = schnitt.rsplit(" ", 1)[0]
    return schnitt.rstrip(" ,;·-") + "…"


def _stand(conn, chat_id: int):
    return repo.hole_arbeitsstand(conn, chat_id)


def _feld(conn, chat_id: int, name: str) -> str:
    """Ein Arbeitsstandfeld als Text -- leer, wenn es die Spalte in einer
    alten Datenbank noch nicht gibt (die Migration ist additiv, aber ein
    Leser darf daran nicht scheitern; dieselbe Vorsicht wie in
    ``phasen.voraussetzungen``)."""
    stand = _stand(conn, chat_id)
    if stand is None:
        return ""
    try:
        return (stand[name] or "").strip()
    except (IndexError, KeyError):
        return ""


def _einzeilig(wert: str) -> str:
    """Mehrzeilige Arbeitsstandfelder (Begriffe, Fragen, Geschichte) werden
    zu einer Zeile mit ``·`` -- eine Parameterzeile ist eine Zeile."""
    zeilen = [z.strip() for z in (wert or "").splitlines() if z.strip()]
    return TRENNER.join(zeilen)


def _interviews(conn, chat_id: int) -> str:
    namen = [a["name"] for a in repo.transkripte(conn, chat_id) if a["name"]]
    return TRENNER.join(namen)


def _auswertungen(conn, chat_id: int) -> str:
    anzahl = len(repo.verdichtungen(conn, chat_id))
    return f"{anzahl} ausgewertet" if anzahl else ""


def _figuren(conn, chat_id: int) -> str:
    """``Name — Satz``, wie die Gruppe die Liste abgenommen hat."""
    teile = []
    for figur in repo.figuren(conn, chat_id):
        satz = (figur["beschreibung"] or "").strip()
        teile.append(f"{figur['name']} — {satz}" if satz else figur["name"])
    return TRENNER.join(teile)


def _szenenzeile(zeile) -> str:
    """``Nummer · Titel · Form`` -- die Form nur, wenn sie bestaetigt ist
    (``szene.form``, nicht ``form_vorschlag``: ein Vorschlag ist keine
    Entscheidung, AGENTS.md 06.09.2026)."""
    stuecke = [str(zeile["nummer"]) if zeile["nummer"] is not None else "?"]
    if (zeile["titel"] or "").strip():
        stuecke.append(zeile["titel"].strip())
    if (zeile["form"] or "").strip():
        stuecke.append(zeile["form"].strip())
    return TRENNER.join(stuecke)


def _szenen(conn, chat_id: int) -> str:
    return TRENNER.join(_szenenzeile(s) for s in repo.hole_szenen(conn, chat_id))


def _zuordnungen(conn, chat_id: int) -> str:
    anzahl = len(repo.schaerfungen(conn, chat_id))
    if not anzahl:
        return ""
    runde = repo.letzte_schaerfungsrunde(conn, chat_id)
    stellen = "Stelle" if anzahl == 1 else "Stellen"
    return f"{anzahl} {stellen} aus den Interviews zugeordnet (Runde {runde})"


def _geschriebene_szenen(conn, chat_id: int) -> str:
    return TRENNER.join(
        _szenenzeile(s) for s in repo.hole_szenen(conn, chat_id) if s["volltext"]
    )


def _abgenommene_szenen(conn, chat_id: int) -> str:
    return TRENNER.join(
        _szenenzeile(s) for s in repo.hole_szenen(conn, chat_id) if s["fertig_am"]
    )


#: Je Phase: welche Parameter sie setzt, in der Reihenfolge der Arbeit.
#:
#: Ein Eintrag ist ``(Name, Leser, Text-wenn-leer)``. Der Leser bekommt
#: ``conn`` und ``chat_id`` und liefert einen fertigen Textwert oder den
#: leeren String -- leer heisst "steht noch nicht", und daraus entsteht
#: sowohl das ``⬜`` in der Checkliste als auch die "noch offen"-Zeile in
#: ``/stand``.
#:
#: **Das ist die einzige Liste dieser Art.** Wer eine Phase um ein Feld
#: erweitert, aendert sie hier -- Eintrittsnachricht, Abschlussnachricht und
#: ``/stand`` folgen automatisch.
PARAMETER: dict[int, tuple[tuple[str, Callable[..., str], str], ...]] = {
    1: (
        ("Begriffe", lambda c, i: _einzeilig(_feld(c, i, "begriffe")), "noch keine"),
    ),
    2: (
        ("Fragen", lambda c, i: _einzeilig(_feld(c, i, "fragen")), "noch keine"),
        (
            "Einleitungen",
            lambda c, i: _einzeilig(_feld(c, i, "frage_einleitungen")),
            "noch offen",
        ),
        (
            "Eroeffnung",
            lambda c, i: _einzeilig(_feld(c, i, "interview_eroeffnung")),
            "noch offen",
        ),
        (
            "Abschluss",
            lambda c, i: _einzeilig(_feld(c, i, "interview_abschluss")),
            "noch offen",
        ),
    ),
    3: (
        ("Interviews", _interviews, "noch keine"),
        ("Auswertungen", _auswertungen, "noch keine"),
    ),
    4: (
        ("Setting", lambda c, i: _einzeilig(_feld(c, i, "rahmen")), "noch offen"),
        ("Figuren", _figuren, "noch keine"),
    ),
    5: (
        ("Geschichte", lambda c, i: _einzeilig(_feld(c, i, "geschichte")), "noch offen"),
        ("Szenen", _szenen, "noch keine"),
    ),
    6: (
        ("Zuordnungen", _zuordnungen, "noch keine"),
    ),
    7: (
        ("Szenentexte", _geschriebene_szenen, "noch keine"),
    ),
    8: (
        ("Textbuch", _abgenommene_szenen, "noch keine"),
    ),
}


def parameterzeilen(conn, chat_id: int, phase: int) -> list[tuple[str, str]]:
    """Die Parameter einer Phase als ``(Name, Wert)`` -- Wert leer, solange
    nichts dasteht.

    Die eine Funktion, aus der Eintritt, Abschluss und ``/stand`` lesen. Sie
    ruft nur ``repo`` (kein eigenes SQL, damit das weiche Loeschen an einer
    Stelle bleibt) und nie ein Modell."""
    zeilen = []
    for name, leser, _ in PARAMETER.get(phase, ()):
        zeilen.append((name, _kuerze(leser(conn, chat_id))))
    return zeilen


def standzeilen(conn, chat_id: int, phase: int) -> list[str]:
    """Dieselben Parameter als fertige ``Name: Wert``-Zeilen, mit dem
    Ersatztext, wenn nichts dasteht -- die Form, die ``/stand`` braucht."""
    leertexte = {name: leer for name, _, leer in PARAMETER.get(phase, ())}
    return [
        f"{name}: {wert or leertexte.get(name, 'noch offen')}"
        for name, wert in parameterzeilen(conn, chat_id, phase)
    ]


def checkliste(conn, chat_id: int, phase: int) -> str:
    """``⬜ Setting  ⬜ Figuren`` -- der Status aus dem Arbeitsstand, nicht
    geraten. Tritt eine Gruppe in eine Phase ein, in der schon etwas steht
    (Rueckkehr aus einer hoeheren Phase), steht dort ``✅``."""
    teile = [
        f"{_ERLEDIGT if wert else _OFFEN} {name}"
        for name, wert in parameterzeilen(conn, chat_id, phase)
    ]
    return "  ".join(teile)


def eintritt(conn, chat_id: int, phase: int) -> str:
    """Die Eintrittsnachricht einer Phase: Kopfzeile, Einleitung, Checkliste.

    Ohne Knoepfe -- die haengt der Aufrufer darunter
    (``knoepfe.eintritt_in_phase``): welche Knoepfe zum Einstieg gehoeren,
    weiss ``knoepfe`` und nicht dieses Modul."""
    kopf = _KOPF_EINTRITT.format(
        nummer=phase, gesamt=phasen.LETZTE, name=phasen.kurzname(phase),
    )
    zeilen = [kopf]
    einleitung = _einleitung(conn, chat_id, phase)
    if einleitung:
        zeilen.append(einleitung)
    liste = checkliste(conn, chat_id, phase)
    if liste:
        zeilen.append(_ZEILE_CHECKLISTE.format(liste=liste))
    return "\n\n".join(zeilen)


def abschluss(conn, chat_id: int, phase: int) -> str:
    """Die Abschlussnachricht einer Phase: Kopfzeile und je Parameter eine
    Zeile mit dem, was wirklich dasteht.

    Was leer geblieben ist, steht **nicht** da: die Nachricht kommt in dem
    Moment, in dem die naechste Phase moeglich wurde -- eine Zeile "noch
    offen" darin waere ein Widerspruch in sich."""
    zeilen = [_KOPF_ABSCHLUSS.format(bezeichnung=phasen.bezeichnung(phase))]
    for name, wert in parameterzeilen(conn, chat_id, phase):
        if wert:
            zeilen.append(f"{name}: {wert}")
    return "\n".join(zeilen)

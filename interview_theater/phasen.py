"""Die acht Arbeitsphasen als gespeicherter, sichtbarer Zustand.

**Warum es das jetzt gibt.** Die SPEC hat eine Phasen-Zustandsmaschine
verworfen -- zu Recht: verworfen war, dass der Code die Phase *erraet* und
still umschaltet, und dann ein gespeicherter Zustand der Gruppe widerspricht
("wir sind laut Bot in Phase 3, arbeiten aber an Figuren"). Seit dem
04.09.2026 ist die Phase trotzdem ein Feld -- aber eines, das nur **hoerbar**
gesetzt wird: von der Gruppe (Erkenner-art ``phase_setzen``, Befehl
``/phase``) oder vom Bot **mit Meldung**. Nie still. Zurueckspringen geht
jederzeit, auch von 8 nach 5.

**Zwei Wirkungen, beide zustandsfrei** (siehe ``naechste_moegliche``):

1. *Vorschlag* -- erlaubt die Materiallage eine hoehere Phase, bekommt der
   Gespraechs-Prompt einen Hinweisblock (``kontext.baue``), und der Bot bietet
   den Wechsel im Gespraech an. Einmal je Stufe, nicht jeden Zug
   (``arbeitsstand.phase_angeboten``).
2. *Automatischer Sprung* -- hat der Erkenner im selben Lauf genau die
   Aenderung geschrieben, die die naechste Phase moeglich macht, schaltet der
   Code um und meldet es in derselben Notiert-Zeile (``erkenner.laufe``).
   Nur vorwaerts, nur um eine Phase, nie rueckwaerts. Nach dem
   Notiert-Muster: schalten, melden, weiterlaufen -- kein Wartezustand auf
   ein "ja", ein Widerspruch schaltet zurueck.

**Kein Modellaufruf.** ``moegliche_naechste`` liest ausschliesslich die
Datenbank (ueber ``repo``, damit das weiche Loeschen -- ``entfernt_am IS
NULL`` -- an einer Stelle bleibt und diese Datei kein eigenes SQL braucht).
Sie laeuft in jedem Gespraechszug, im kritischen Pfad.

**Die freie Stelle 5/6** (Korrektur vom 04.09.2026 abends): Figuren und
Hauptkonflikt haben dieselbe Voraussetzung (ein gesetztes Kernthema) und
dieselbe Berechtigung. Figuren zuerst ist der haeufigere Weg, nicht der
richtige -- welche der beiden zuerst kommt, entscheidet die Gruppe. Deshalb
schaltet der Code zwischen 5 und 6 **nie** von selbst um (``FREIE_STELLE``):
dort gibt es nur ein Angebot, das beide nennt (``kontext.baue``), oder das
Wort der Gruppe (``phase_setzen``, ``/phase``).

**Die Phase steuert den Fokus, nicht den Informationszugang.** Die
datengetriebenen Bloecke aus ``kontext.baue`` bleiben unveraendert: was in
der Datenbank steht, geht in den Prompt, unabhaengig von der Phase. Die
Phase entscheidet nur, welchen Prompt-Zusatz der Bot bekommt
(``prompts/phasen/N.md``) -- worauf er den Fokus legt, was er in dieser
Phase nicht tut.
"""

from interview_theater import repo

#: Nummer, Kurzname, ein Satz. Die acht Stationen sind wortgleich die aus
#: ``prompts/system.md`` -- dort als Landkarte fuer das Gespraech, hier als
#: Datenmodell. Der Kurzname ist das, was in Meldungen und auf der
#: Weboberflaeche steht ("5 · Figuren"), der Satz erklaert ihn, wenn die
#: Gruppe ``/phase`` ohne Argument schickt.
#:
#: Korrigiert am 04.09.2026 abends, nach dem Widerspruch aus der Praxis: die
#: Begriffe werden **analog im Plenum** gesammelt, nicht mit dem Bot -- Phase 1
#: ist die Uebergabe der fertigen Liste, keine Sammelphase. Fragen formulieren
#: und Interviews fuehren sind zwei Arbeiten, nicht eine. Und Figuren und
#: Hauptkonflikt stehen nebeneinander, nicht hintereinander (FREIE_STELLE).
PHASEN = (
    (1, "Begriffe", "Die im Plenum gesammelte Begriffsliste aufnehmen und ordnen."),
    (2, "Fragen", "Aus den Begriffen Interviewfragen entwickeln."),
    (3, "Interviews", "Interviews fuehren, das Material verdichten."),
    (4, "Kernthema", "Aus den Verdichtungen das Kernthema herausschaelen."),
    (5, "Figuren", "Figuren aus dem Material entwickeln."),
    (6, "Hauptkonflikt", "Den Hauptkonflikt benennen, der das Stueck traegt."),
    (7, "Szenen", "Die Szenenfolge entwerfen und die Szenentexte schreiben."),
    (8, "Durchlauf", "Durchlauf und Feinschliff vor der Auffuehrung."),
)

#: Die beiden Phasen, deren Reihenfolge offen ist: Figuren (5) und
#: Hauptkonflikt (6). Zwischen ihnen schaltet der Code nie von selbst um --
#: siehe ``sprung_nach`` und den Moduldocstring.
FREIE_STELLE = frozenset({5, 6})

#: Die Phase, die gilt, solange keine gesetzt wurde (``phase IS NULL``).
ERSTE = 1

#: Hoechste Nummer -- eine Stelle statt einer 8 an sechs Stellen.
LETZTE = PHASEN[-1][0]


def kurzname(nummer: int) -> str:
    """Der Kurzname einer Phase; leer bei einer unbekannten Nummer."""
    for eintrag in PHASEN:
        if eintrag[0] == nummer:
            return eintrag[1]
    return ""


def satz(nummer: int) -> str:
    """Der erklaerende Satz einer Phase; leer bei unbekannter Nummer."""
    for eintrag in PHASEN:
        if eintrag[0] == nummer:
            return eintrag[2]
    return ""


def bezeichnung(nummer: int) -> str:
    """Wie eine Phase ueberall genannt wird: ``"5 · Figuren"``.

    Eine einzige Schreibweise fuer Chatmeldung, ``/stand``, Begruessung,
    Prompt und Weboberflaeche -- damit niemand zwei Bezeichnungen fuer
    dasselbe lernen muss."""
    name = kurzname(nummer)
    return f"{nummer} · {name}" if name else str(nummer)


#: Die Meldung, mit der jede Phasenaenderung hoerbar wird -- gleiche Form wie
#: die Kernthema-Zeile des Erkenners: sagen, was jetzt gilt, und wie man
#: widerspricht.
MELDUNG = "Wir sind jetzt bei {bezeichnung}. Falls nicht, sagt es mir."


def meldung(nummer: int) -> str:
    """Die Zeile, mit der ein Phasenwechsel gemeldet wird."""
    return MELDUNG.format(bezeichnung=bezeichnung(nummer))


def setze(conn, chat_id: int, nummer: int, quelle: str) -> bool:
    """Setzt die Phase und schreibt die Entscheidung ins Journal. Liefert
    True, wenn sich dadurch etwas geaendert hat.

    Derselbe Wert ist keine Aenderung -- dann gibt es weder einen
    Journaleintrag noch eine Meldung (dieselbe Regel wie ueberall im
    Erkenner: sonst bestaetigte der Bot bei jedem Zug erneut dieselbe
    Phase). ``quelle`` ist 'erkenner' oder 'befehl' und haelt im Journal
    fest, auf welchem Weg die Gruppe hierhergekommen ist."""
    if repo.hole_phase(conn, chat_id) == nummer:
        return False
    repo.setze_phase(conn, chat_id, nummer)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Phase {bezeichnung(nummer)}", quelle=quelle
    )
    return True


def liste() -> str:
    """Die acht Phasen als Text, eine Zeile je Phase (fuer ``/phase`` ohne
    Argument)."""
    return "\n".join(f"{nummer} · {name} - {text}" for nummer, name, text in PHASEN)


def nummer_fuer(wert: str | int | None) -> int | None:
    """Uebersetzt, was die Gruppe gesagt hat, in eine Phasennummer.

    Tolerant, in vier Durchgaengen: eine Zahl 1-8; ein Kurzname genau;
    ein Teiltreffer im Kurznamen, in beide Richtungen ("figuren" trifft
    "Figuren", "wir sind bei den Figuren" ebenso); erst danach ein
    Teiltreffer im erklaerenden Satz. Passt nichts, ist das None -- und der
    Aufrufer aendert nichts, statt zu raten.

    **Erst alle Kurznamen, dann alle Saetze** -- die Trennung ist kein
    Schoenheitsfehler, sondern noetig: "interview" steht als Wort auch im
    Satz von Phase 2 ("Interviewfragen entwickeln") und wuerde in einem
    einzigen Durchgang die Fragen-Phase treffen statt der Interviews.

    Bei mehreren Teiltreffern gewinnt die kleinste Nummer: der frueheren
    Phase zu widersprechen ist billiger als eine zu ueberspringen -- die
    Gruppe korrigiert es mit einem Satz."""
    if wert is None:
        return None
    if isinstance(wert, int):
        return wert if 1 <= wert <= LETZTE else None

    text = wert.strip().lower().strip(".:!?")
    if not text:
        return None
    if text.isdigit():
        nummer = int(text)
        return nummer if 1 <= nummer <= LETZTE else None

    for nummer, name, _ in PHASEN:
        if text == name.lower():
            return nummer
    for nummer, name, _ in PHASEN:
        name = name.lower()
        if name in text or text in name:
            return nummer
    for nummer, _, erklaerung in PHASEN:
        if text in erklaerung.lower():
            return nummer
    return None


def aktuelle(conn, chat_id: int) -> int:
    """Die geltende Phase. Noch nie gesetzt (NULL) heisst ERSTE -- eine
    Gruppe, die gerade erst anfaengt, ist im Ankommen, ohne dass jemand das
    erklaeren muesste."""
    gespeichert = repo.hole_phase(conn, chat_id)
    if gespeichert is None:
        return ERSTE
    return gespeichert


def voraussetzungen(conn, chat_id: int) -> dict[int, bool]:
    """Welche Phase die Materiallage hergibt, je Phase ein Ja/Nein.

    Rein aus den Daten, ohne gespeicherten Zustand und ohne Modellaufruf:
    Begriffe da -> 2 ist moeglich; Fragen da -> 3; eine fertige Verdichtung
    -> 4; Kernthema -> 5 **und** 6 (dieselbe Voraussetzung, die Reihenfolge
    entscheidet die Gruppe); Hauptkonflikt und zwei Figuren -> 7; eine Szene
    mit Volltext -> 8. Phase 1 braucht keine Voraussetzung, dorthin kommt man
    immer zurueck (aber nie automatisch).

    Die Bedingungen sind nicht kumulativ: eine Gruppe, die ohne Interviews
    direkt ein Kernthema setzt, darf trotzdem nach 5 -- die Reihenfolge ist
    eine Landkarte, kein Zwang (SPEC § 6.1)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kernthema = bool(stand and stand["kernthema"])
    return {
        2: bool(stand and stand["begriffe"]),
        3: bool(stand and stand["fragen"]),
        4: bool(repo.verdichtungen(conn, chat_id)),
        5: kernthema,
        6: kernthema,
        7: bool(stand and stand["hauptkonflikt"])
        and len(repo.figuren(conn, chat_id)) >= 2,
        8: any(s["volltext"] for s in repo.hole_szenen(conn, chat_id)),
    }


def moegliche_naechste(conn, chat_id: int) -> list[int]:
    """Alle Phasen ueber der aktuellen, die die Materiallage hergibt --
    aufsteigend, meist leer oder einelementig.

    Reine Leseabfrage, kein Schreiben, kein Modellaufruf: der Aufrufer
    entscheidet, ob daraus ein Angebot (``kontext.baue``) oder ein
    automatischer Sprung (``erkenner.laufe``) wird. Rueckwaerts liefert sie
    nie etwas -- eine Gruppe, die von 8 nach 5 zurueckgeht, soll nicht im
    naechsten Zug nach 8 zurueckgeschoben werden.

    Eine **Liste**, seit Figuren und Hauptkonflikt gleichberechtigt
    nebeneinander stehen: mit gesetztem Kernthema sind aus Phase 4 heraus
    beide moeglich, und das Angebot muss beide nennen duerfen, statt sich
    still fuer eine zu entscheiden."""
    jetzige = aktuelle(conn, chat_id)
    return sorted(
        nummer for nummer, erfuellt in voraussetzungen(conn, chat_id).items()
        if erfuellt and nummer > jetzige
    )


def naechste_moegliche(conn, chat_id: int) -> int | None:
    """Die hoechste moegliche Phase (``moegliche_naechste``) oder None.

    Bleibt als eigene Funktion, weil an genau einer Stelle eine einzelne Zahl
    gebraucht wird: ``arbeitsstand.phase_angeboten`` merkt sich, welche Stufe
    schon angeboten wurde, und ein Merkposten braucht einen Wert, keine
    Liste."""
    moegliche = moegliche_naechste(conn, chat_id)
    return max(moegliche) if moegliche else None


#: Welche Erkenner-art welche Phase moeglich macht, sofern sie ohne Blick in
#: die Datenbank feststeht -- die Grundlage des automatischen Sprungs
#: (``erkenner.laufe``): nur wenn der Erkenner IM SELBEN LAUF genau die
#: Aenderung geschrieben hat, die die naechste Phase traegt, schaltet der Code
#: um. "Begriffe gesetzt" belegt Phase 2, ein beilaeufiger Journaleintrag
#: belegt gar nichts.
#:
#: ``figur_setzen`` und ``hauptkonflikt_setzen`` stehen nicht hier, sondern in
#: ``ermoeglichte_phase``: wohin sie zeigen, haengt davon ab, was schon da ist
#: -- das ist die Rechnung, die die freie Reihenfolge von 5 und 6 aufloest.
#: Zu 4 und 8 fuehrt keine art: eine fertige Verdichtung und ein Szenentext
#: entstehen ausserhalb des Erkenners (``aufnahme.py``, ``szene.py``), dorthin
#: gibt es deshalb nur das Angebot.
ART_ERMOEGLICHT = {
    "begriffe_setzen": 2,
    "fragen_setzen": 3,
    "kernthema_setzen": 5,
}


def ermoeglichte_phase(conn, chat_id: int, art: str | None) -> int | None:
    """Welche Phase diese Aenderungsart gerade moeglich macht -- oder None.

    Fuer die drei Arten aus ART_ERMOEGLICHT steht das fest. Die beiden
    anderen haengen an der Materiallage, und zwar so, wie eine Gruppe es
    erzaehlen wuerde:

    - ``figur_setzen`` zaehlt erst ab der zweiten Figur. Steht der
      Hauptkonflikt schon, sind die Figuren das letzte fehlende Stueck fuer
      die Szenen (7); steht er noch nicht, ist er das Naechstliegende (6).
    - ``hauptkonflikt_setzen`` spiegelbildlich: mit zwei Figuren im
      Arbeitsstand geht es an die Szenen (7), ohne sie an die Figuren (5).

    Das ergibt zwei Wege zu denselben Szenen -- welchen die Gruppe nimmt,
    entscheidet sie, nicht der Code."""
    if art in ART_ERMOEGLICHT:
        return ART_ERMOEGLICHT[art]
    if art not in ("figur_setzen", "hauptkonflikt_setzen"):
        return None
    stand = repo.hole_arbeitsstand(conn, chat_id)
    hat_konflikt = bool(stand and stand["hauptkonflikt"])
    genug_figuren = len(repo.figuren(conn, chat_id)) >= 2
    if art == "figur_setzen":
        if not genug_figuren:
            return None
        return 7 if hat_konflikt else 6
    return 7 if genug_figuren else 5


def sprung_nach(conn, chat_id: int, wirkliche_aenderungen: list[dict]) -> int | None:
    """Die Phase, in die der Code nach diesem Erkennerlauf selbst umschalten
    darf -- oder None (der Normalfall).

    Vier Bedingungen, alle noetig: (1) es geht um genau eine Phase vorwaerts,
    (2) der Schritt ist nicht der zwischen 5 und 6 (FREIE_STELLE), (3) eine
    der gerade geschriebenen Aenderungen macht laut ``ermoeglichte_phase``
    genau diese Phase moeglich, (4) die Materiallage gibt sie tatsaechlich
    her. Nie rueckwaerts, nie ueber eine Phase hinweg -- alles andere ist ein
    Angebot, kein Sprung.

    **Die freie Stelle.** Von 5 nach 6 und von 6 nach 5 schaltet der Code
    nie: beide haben dieselbe Voraussetzung, beide sind richtig, und welche
    zuerst drankommt, ist die eine Entscheidung, die der Gruppe gehoert. Der
    Bot bietet sie an (``kontext.baue``), er nimmt sie nicht vorweg. Deshalb
    gibt es zwischen diesen beiden Phasen keinen automatischen Weg -- auch
    nicht, wenn ``ermoeglichte_phase`` fuer ``figur_setzen`` auf 6 zeigt: die
    Rechnung stimmt, der Schritt bleibt trotzdem der Gruppe ueberlassen.

    Hat die Gruppe im selben Lauf selbst eine Phase genannt, schaltet der
    Code gar nicht: wer gerade gesagt hat, wo er steht, laesst sich nicht im
    selben Atemzug weiterschieben."""
    if any(a.get("art") == "phase_setzen" for a in wirkliche_aenderungen):
        return None
    jetzige = aktuelle(conn, chat_id)
    ziel = jetzige + 1
    if ziel > LETZTE:
        return None
    if {jetzige, ziel} == set(FREIE_STELLE):
        return None
    if not any(
        ermoeglichte_phase(conn, chat_id, a.get("art")) == ziel
        for a in wirkliche_aenderungen
    ):
        return None
    if not voraussetzungen(conn, chat_id).get(ziel):
        return None
    return ziel

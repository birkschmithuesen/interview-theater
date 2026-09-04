"""Die sieben Arbeitsphasen als gespeicherter, sichtbarer Zustand.

**Warum es das gibt.** Die SPEC hat eine Phasen-Zustandsmaschine verworfen --
zu Recht: verworfen war, dass der Code die Phase *erraet* und still
umschaltet, und dann ein gespeicherter Zustand der Gruppe widerspricht ("wir
sind laut Bot in Phase 3, arbeiten aber an Figuren"). Seit dem 04.09.2026 ist
die Phase trotzdem ein Feld -- aber eines, das **nur die Gruppe setzt**:
Erkenner-art ``phase_setzen`` oder Befehl ``/phase``. Zurueckspringen geht
jederzeit, auch von 7 nach 4.

**Der automatische Sprung ist verworfen** (Birk, 04.09.2026 abends, nach dem
Probelauf). Er hat einmal existiert (``ART_ERMOEGLICHT``, ``sprung_nach``) und
ist ersatzlos gestrichen, aus einem Satz heraus: **Datenstand ist nicht
Absicht.** Eine fertige Verdichtung sagt nicht, ob noch drei Interviews
kommen; ein gesetztes Kernthema sagt nicht, dass die Gruppe mit dem Kernthema
fertig ist. Was der Code aus den Daten lesen kann, ist immer nur, was
*moeglich* waere -- und das ist eine Frage, keine Entscheidung.

**Deshalb gibt es genau eine Wirkung, und die ist eine Frage**
(``moegliche_naechste`` / ``offenes_angebot``): erlaubt die Materiallage eine
hoehere Phase, bekommt der Gespraechs-Prompt einen Hinweisblock
(``kontext.baue``) mit der Anweisung, im Fluss nachzufragen -- "Kommen noch
Interviews, oder gehen wir ans Kernthema?". Die Antwort der Gruppe ist ein
Satz, den der Erkenner als ``phase_setzen`` liest. Angeboten wird einmal je
Stufe, nicht jeden Zug (``arbeitsstand.phase_angeboten``), sonst wuerde aus
einem Angebot Draengeln.

**Kein Modellaufruf.** ``moegliche_naechste`` liest ausschliesslich die
Datenbank (ueber ``repo``, damit das weiche Loeschen -- ``entfernt_am IS
NULL`` -- an einer Stelle bleibt und diese Datei kein eigenes SQL braucht).
Sie laeuft in jedem Gespraechszug, im kritischen Pfad.

**Die Phase steuert den Fokus, nicht den Informationszugang.** Die
datengetriebenen Bloecke aus ``kontext.baue`` bleiben unveraendert: was in
der Datenbank steht, geht in den Prompt, unabhaengig von der Phase. Die
Phase entscheidet nur, welchen Prompt-Zusatz der Bot bekommt
(``prompts/phasen/N.md``) -- worauf er den Fokus legt, was er in dieser Phase
nicht von sich aus anfaengt. Ein Kaefig ist sie nicht: bittet die Gruppe
ausdruecklich um etwas aus einer anderen Phase, tut er es, und der Erkenner
setzt die Phase nach.
"""

from interview_theater import repo

#: Nummer, Kurzname, ein Satz. Die sieben Stationen sind wortgleich die aus
#: ``prompts/system.md`` -- dort als Landkarte fuer das Gespraech, hier als
#: Datenmodell. Der Kurzname ist das, was in Meldungen und auf der
#: Weboberflaeche steht ("5 · Hauptkonflikt"), der Satz erklaert ihn, wenn die
#: Gruppe ``/phase`` ohne Argument schickt.
#:
#: Korrigiert am 05.09.2026 (Birk, nach dem Probelauf): **Kernthema und
#: Figuren sind EINE Phase.** Vorher waren es zwei mit freier Reihenfolge --
#: im Probelauf bat die Gruppe dann "Kernthema und Figuren in einem Schritt",
#: und das ist auch die ehrlichere Beschreibung der Arbeit: welches von
#: beidem zuerst kommt, ergibt sich aus dem Material und nicht aus einer
#: Nummerierung. Damit faellt auch die alte Sonderlogik der "freien Stelle"
#: zwischen 5 und 6 ersatzlos weg.
#:
#: Die uebrigen Entscheidungen von 04.09.2026 abends gelten weiter: die
#: Begriffe werden **analog im Plenum** gesammelt, nicht mit dem Bot -- Phase 1
#: ist die Uebergabe der fertigen Liste, keine Sammelphase. Fragen formulieren
#: und Interviews fuehren sind zwei Arbeiten, nicht eine.
PHASEN = (
    (1, "Begriffe", "Die im Plenum gesammelte Begriffsliste aufnehmen und ordnen."),
    (2, "Fragen", "Aus den Begriffen Interviewfragen entwickeln."),
    (3, "Interviews", "Interviews fuehren, das Material verdichten."),
    (
        4,
        "Kernthema & Figuren",
        "Aus den Verdichtungen das Kernthema herausschaelen und die Figuren "
        "entwickeln.",
    ),
    (5, "Hauptkonflikt", "Den Hauptkonflikt benennen, der das Stueck traegt."),
    (6, "Szenen", "Die Szenenfolge entwerfen und die Szenentexte schreiben."),
    (7, "Durchlauf", "Durchlauf und Feinschliff vor der Auffuehrung."),
)

#: Woerter, unter denen eine Phase gemeint sein kann -- zusaetzlich zum
#: Kurznamen (``nummer_fuer``).
#:
#: Noetig, seit ein Kurzname aus zwei Sachen besteht: gegen "Kernthema &
#: Figuren" trifft ein Teilstringvergleich weder "wir sind noch beim
#: Kernthema" noch "lasst uns jetzt Figuren machen" -- beides sind genau die
#: Saetze, mit denen eine Gruppe diese Phase benennt. Die Stichwoerter stehen
#: hier als Daten und nicht als Sonderfall im Code, damit eine achte Phase
#: (oder ein weiterer Doppelname) nichts als diese Tabelle braucht.
STICHWOERTER = {
    1: ("begriffe", "begriff", "begriffsliste"),
    # "interviewfragen" steht hier bewusst NICHT: der Vergleich laeuft in
    # beide Richtungen, und "interview" waere darin enthalten -- die Gruppe
    # landete beim Formulieren statt beim Aufnehmen.
    2: ("fragen", "frage", "frageliste"),
    3: ("interviews", "interview", "aufnahmen"),
    4: ("kernthema", "kernthemas", "thema", "figuren", "figur"),
    5: ("hauptkonflikt", "konflikt"),
    6: ("szenen", "szene", "szenenfolge", "szenentexte"),
    7: ("durchlauf", "feinschliff"),
}

#: Die Phase, die gilt, solange keine gesetzt wurde (``phase IS NULL``).
ERSTE = 1

#: Hoechste Nummer -- eine Stelle statt einer 7 an sechs Stellen.
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
    """Wie eine Phase ueberall genannt wird: ``"5 · Hauptkonflikt"``.

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
    """Die sieben Phasen als Text, eine Zeile je Phase (fuer ``/phase`` ohne
    Argument)."""
    return "\n".join(f"{nummer} · {name} - {text}" for nummer, name, text in PHASEN)


def nummer_fuer(wert: str | int | None) -> int | None:
    """Uebersetzt, was die Gruppe gesagt hat, in eine Phasennummer.

    Tolerant, in vier Durchgaengen: eine Zahl 1-7; ein Kurzname genau; ein
    Stichwort aus ``STICHWOERTER`` (in beide Richtungen -- "figuren" trifft,
    "wir sind bei den Figuren" ebenso); erst danach ein Teiltreffer im
    erklaerenden Satz. Passt nichts, ist das None -- und der Aufrufer aendert
    nichts, statt zu raten.

    **Erst alle Stichwoerter, dann alle Saetze** -- die Trennung ist kein
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
    for nummer, _, _ in PHASEN:
        for stichwort in STICHWOERTER.get(nummer, ()):
            if stichwort in text or text in stichwort:
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
    -> 4; Kernthema **und** zwei Figuren -> 5 (ein Konflikt braucht zwei
    Wollen, also beides); Hauptkonflikt -> 6; eine Szene mit Volltext -> 7.
    Phase 1 braucht keine Voraussetzung, dorthin kommt man immer zurueck.

    Die Bedingungen sind nicht kumulativ: eine Gruppe, die ohne Interviews
    direkt ein Kernthema und zwei Figuren setzt, darf trotzdem nach 5 -- die
    Reihenfolge ist eine Landkarte, kein Zwang (SPEC § 6.1).

    Und sie sind eine Frage, keine Entscheidung: was hier True ergibt, wird
    der Gruppe angeboten (``offenes_angebot``), nie geschaltet."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    kernthema = bool(stand and stand["kernthema"])
    return {
        2: bool(stand and stand["begriffe"]),
        3: bool(stand and stand["fragen"]),
        4: bool(repo.verdichtungen(conn, chat_id)),
        5: kernthema and len(repo.figuren(conn, chat_id)) >= 2,
        6: bool(stand and stand["hauptkonflikt"]),
        7: any(s["volltext"] for s in repo.hole_szenen(conn, chat_id)),
    }


def moegliche_naechste(conn, chat_id: int) -> list[int]:
    """Alle Phasen ueber der aktuellen, die die Materiallage hergibt --
    aufsteigend, meist leer oder einelementig.

    Reine Leseabfrage, kein Schreiben, kein Modellaufruf: der Aufrufer macht
    daraus ein Angebot (``kontext.baue``, ``aufnahme``), nie einen Wechsel.
    Rueckwaerts liefert sie nie etwas -- eine Gruppe, die von 7 nach 4
    zurueckgeht, soll nicht im naechsten Zug nach 7 zurueckgeschoben
    werden."""
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


def offenes_angebot(conn, chat_id: int) -> int | None:
    """Die Stufe, die gerade angeboten werden darf -- oder None, weil keine
    moeglich ist oder sie schon angeboten wurde.

    **Liest nur.** Gemerkt wird erst mit ``merke_angebot``, und zwar von dem
    Aufrufer, der das Angebot auch wirklich ausspricht. Beides zusammen in
    einer Funktion war die naheliegende Loesung und die falsche: es gibt seit
    dem 05.09.2026 zwei Stellen, die anbieten -- der Gespraechs-Prompt
    (``kontext._baue_phasenhinweis``) und die Verdichtungs-Nachricht am Ende
    eines Interviews (``aufnahme._phasenfrage``). Wuerde schon das Nachsehen
    den Merkposten setzen, verschluckte die eine Stelle das Angebot der
    anderen."""
    moegliche = moegliche_naechste(conn, chat_id)
    if not moegliche:
        return None
    merkposten = max(moegliche)
    if repo.hole_phase_angeboten(conn, chat_id) == merkposten:
        return None
    return merkposten


def merke_angebot(conn, chat_id: int, nummer: int) -> None:
    """Haelt fest, dass diese Stufe angeboten wurde -- damit das Angebot sich
    nicht jeden Zug wiederholt (``arbeitsstand.phase_angeboten``)."""
    repo.setze_phase_angeboten(conn, chat_id, nummer)

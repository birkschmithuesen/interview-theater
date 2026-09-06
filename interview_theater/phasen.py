"""Die sieben Arbeitsphasen als gespeicherter, sichtbarer Zustand.

**Erst erfinden, dann schaerfen** (Birk, 05.09.2026, 23:30 -- der Umbau ab
Phase 4). Bis dahin entstanden Figuren und Szenen AUS den Interviews, und die
Gruppe erkannte ihren eigenen kreativen Anteil nicht wieder. Jetzt umgekehrt:
in Phase 4 erfindet die Gruppe Setting, Figuren **und** die Geschichte im
Groben samt Szenenfolge -- **frei**, aus Begriffen und Fragen, ohne Material
--, und erst in Phase 5 kommen die Interviews dazu und schaerfen, was schon
dasteht.

**Setting, Figuren und Geschichte sind EINE Phase** (Birk, 06.09.2026, 09:20).
Vorher waren es zwei (4 Setting & Figuren, 5 Geschichte), und zwischen der
fixierten Figurenliste und der Frage nach der Geschichte stand ein
Phasenwechsel mit eigener Meldung -- eine Zaesur mitten in einem Arbeitsgang,
den die Gruppe als einen erlebt. Jetzt leitet der Bot nach der Figurenliste
mit einer Zeile und einer offenen Frage weiter ("Was soll passieren, wie soll
es ausgehen?"), ohne Phasenmeldung.

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

**Der Rahmen ist Teil von Phase 4 geworden** (Setting = Ort, Zeit, Anlass).
``arbeitsstand.rahmen`` bleibt dasselbe Feld, es wird nur frueher und ohne
Material gefuellt. Das **Kernthema** entfaellt als eigene Station: seine
Rolle im Kernpaket uebernimmt ``arbeitsstand.geschichte`` (Bogen und Ende).
Die Kernthema-Felder, -Knoepfe und -Marker bleiben rueckwaertskompatibel im
Code, werden aber nicht mehr angeboten.

Alte Datenbanken werden umnummeriert (``db.PHASEN_UMNUMMERIERUNG_3``):
5 -> 4, 6 -> 5, 7 -> 6, 8 -> 7.
"""

from interview_theater import repo

#: Nummer, Kurzname, ein Satz. Die acht Stationen sind wortgleich die aus
#: ``prompts/system.md`` -- dort als Landkarte fuer das Gespraech, hier als
#: Datenmodell. Der Kurzname ist das, was in Meldungen und auf der
#: Weboberflaeche steht ("5 · Format & Rahmen"), der Satz erklaert ihn, wenn die
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
        "Setting, Figuren & Geschichte",
        "Frei erfinden: worin es spielt, wer vorkommt, was passiert.",
    ),
    (
        5,
        "Schaerfung",
        "Die erfundene Geschichte am Interviewmaterial schaerfen.",
    ),
    (6, "Szenentexte", "Szene fuer Szene die Texte schreiben."),
    (
        7,
        "Schaerfung des Stuecks",
        "Das ganze Textbuch pruefen und Szene fuer Szene nachschaerfen.",
    ),
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
    # Setting UND Figuren -- der Rahmen (Ort, Zeit, Anlass) ist seit dem
    # Umbau vom 05.09.2026 nachts Teil DIESER Station und nicht mehr eine
    # eigene. "kernthema", "format" und "konflikt" bleiben als Altlast
    # stehen: eine Gruppe (oder ein Journaleintrag von gestern) sagt weiter
    # "wir sind beim Kernthema" und meint die Station, an der erfunden wird.
    4: (
        "setting", "figuren", "figur", "rahmen", "rahmung",
        "kernthema", "kernthemas", "format", "konflikt", "hauptkonflikt",
        "geschichte", "handlung", "grobstruktur",
    ),
    # "schaerfung" steht in ZWEI Phasen (5 am Material, 7 am fertigen
    # Stueck). Aufgeloest wird das nicht hier, sondern in ``nummer_fuer``
    # ueber die Phase, in der die Gruppe gerade steht: wer vor der
    # Schaerfung steht, meint 5; wer die Szenen schon hat, meint 7.
    5: ("schaerfung", "schaerfen", "clustern", "verdichtungen"),
    6: ("szenentexte", "szenentext", "szenen", "szene"),
    7: ("durchlauf", "feinschliff", "stueckpruefung", "pruefrunde"),
}

#: Die Stichwoerter, die in mehr als einer Phase vorkommen koennen, mit der
#: spaeteren Phase, die sie meinen, sobald die Gruppe schon dort ist. Der
#: Anlass ist Birks Umbau vom 06.09.2026: **beide** Schaerfungen heissen
#: Schaerfung -- die am Material (5) und die am fertigen Stueck (7).
MEHRDEUTIG = {5: 7}

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
    """Wie eine Phase ueberall genannt wird: ``"5 · Format & Rahmen"``.

    Eine einzige Schreibweise fuer Chatmeldung, ``/stand``, Begruessung,
    Prompt und Weboberflaeche -- damit niemand zwei Bezeichnungen fuer
    dasselbe lernen muss."""
    name = kurzname(nummer)
    return f"{nummer} · {name}" if name else str(nummer)


def knopfbezeichnung(nummer: int) -> str:
    """Wie eine Phase auf einem KNOPF heisst: ``"Kernthema & Figuren"`` --
    nach Inhalt, nie nach Nummer (05.09.2026, Birk).

    Der Grund ist einer aus dem Raum: "Weiter zu Phase 5" sagt einer Gruppe,
    die zum ersten Mal mit dem Bot arbeitet, gar nichts -- sie kennt die
    Nummerierung nicht und soll sie auch nicht lernen muessen. "Weiter zu
    Format & Rahmen" sagt, was als naechstes passiert.

    In Meldungen und auf der Weboberflaeche bleibt es bei ``bezeichnung()``
    mit Nummer: dort ist die Nummer eine Ordnung, kein Bedienelement.
    """
    return kurzname(nummer) or str(nummer)


#: Die Meldung, mit der jede Phasenaenderung hoerbar wird -- gleiche Form wie
#: die Kernthema-Zeile des Erkenners: sagen, was jetzt gilt, und wie man
#: widerspricht.
MELDUNG = "Wir sind jetzt bei {bezeichnung}. Falls nicht, sagt es mir."


def meldung(nummer: int) -> str:
    """Die Zeile, mit der ein Phasenwechsel gemeldet wird."""
    return MELDUNG.format(bezeichnung=bezeichnung(nummer))


def setze(conn, chat_id: int, nummer: int, quelle: str, notiz: str | None = None) -> bool:
    """Setzt die Phase und schreibt die Entscheidung ins Journal. Liefert
    True, wenn sich dadurch etwas geaendert hat.

    Derselbe Wert ist keine Aenderung -- dann gibt es weder einen
    Journaleintrag noch eine Meldung (dieselbe Regel wie ueberall im
    Erkenner: sonst bestaetigte der Bot bei jedem Zug erneut dieselbe
    Phase). ``quelle`` ist 'erkenner' oder 'befehl' und haelt im Journal
    fest, auf welchem Weg die Gruppe hierhergekommen ist.

    ``notiz`` haengt einen Klammerzusatz an den Journaltext (05.09.2026):
    startet die Gruppe ausdruecklich eine Aufnahme, waehrend sie noch in
    Phase 1 oder 2 steht, wandert sie mit nach Phase 3 -- und im Journal
    soll stehen, WARUM ("durch Aufnahmestart"). Das ist kein Raten aus dem
    Datenstand (AGENTS.md, "Die Phase setzt allein die Gruppe"), sondern
    eine Handlung der Gruppe selbst: sie hat die Aufnahme gestartet."""
    if repo.hole_phase(conn, chat_id) == nummer:
        return False
    repo.setze_phase(conn, chat_id, nummer)
    text = f"Phase {bezeichnung(nummer)}"
    if notiz:
        text = f"{text} ({notiz})"
    repo.schreibe_journal(conn, chat_id, "entschieden", text, quelle=quelle)
    return True


def liste() -> str:
    """Die sieben Phasen als Text, eine Zeile je Phase (fuer ``/phase`` ohne
    Argument)."""
    return "\n".join(f"{nummer} · {name} - {text}" for nummer, name, text in PHASEN)


def nummer_fuer(wert: str | int | None, jetzige: int | None = None) -> int | None:
    """Uebersetzt, was die Gruppe gesagt hat, in eine Phasennummer.

    Tolerant, in vier Durchgaengen: eine Zahl 1-8; ein Kurzname genau; ein
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
    Gruppe korrigiert es mit einem Satz.

    ``jetzige`` loest die eine Mehrdeutigkeit auf, die es seit dem
    06.09.2026 gibt: **beide** Schaerfungen heissen Schaerfung. Sagt eine
    Gruppe, die schon bei den Szenentexten oder darueber steht,
    "Schaerfung", meint sie die des Stuecks (7) und nicht die am Material
    (5) -- ein Ruecksprung um zwei Stationen waere die teurere Fehlannahme.
    Ohne ``jetzige`` bleibt es bei der frueheren Phase."""
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
            return _aufgeloest(nummer, jetzige)
    for nummer, _, _ in PHASEN:
        for stichwort in STICHWOERTER.get(nummer, ()):
            if stichwort in text or text in stichwort:
                return _aufgeloest(nummer, jetzige)
    for nummer, _, erklaerung in PHASEN:
        if text in erklaerung.lower():
            return _aufgeloest(nummer, jetzige)
    return None


def _aufgeloest(nummer: int, jetzige: int | None) -> int:
    """Die spaetere Phase, wenn das Wort in beiden vorkommt und die Gruppe
    schon dort ist (``MEHRDEUTIG``) -- sonst die gefundene."""
    spaeter = MEHRDEUTIG.get(nummer)
    # ``>`` und nicht ``>=``: eine Gruppe, die IN der Material-Schaerfung
    # steht und "Schaerfung" sagt, meint die, in der sie ist -- erst ab der
    # naechsten Station meint dasselbe Wort die des Stuecks.
    if spaeter is not None and jetzige is not None and jetzige > nummer:
        return spaeter
    return nummer


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
    -> 4; **Setting (rahmen), fixierte Figurenliste, Geschichte und
    mindestens eine Szene** -> 5; dieselbe Lage -> 6 (die Schaerfung ist ein
    Angebot, keine Pflicht); **alle geplanten Szenen mit Volltext** -> 7.
    Phase 1 braucht keine Voraussetzung, dorthin kommt man immer zurueck.

    **Phase 7 verlangt seit dem 06.09.2026 ALLE Szenen** und nicht mehr nur
    eine: dort geht das komplette Textbuch an den Stueck-Judge
    (``stueckpruefung``), und ein Urteil ueber ein Stueck, dem drei Szenen
    fehlen, ist keins.

    **Warum 4 weiter an einer Verdichtung haengt**, obwohl dort ohne Material
    gearbeitet wird: die Bedingung ist nicht "das Material wird gebraucht",
    sondern "die Interviews sind durch". Wer erfindet, bevor die Aufnahmen
    ausgewertet sind, verliert die Schaerfung in Phase 6.

    Die Bedingungen sind nicht kumulativ: eine Gruppe, die ohne Interviews
    direkt Setting und Figuren setzt, darf trotzdem nach 5 -- die
    Reihenfolge ist eine Landkarte, kein Zwang (SPEC § 6.1).

    Und sie sind eine Frage, keine Entscheidung: was hier True ergibt, wird
    der Gruppe angeboten (``offenes_angebot``), nie geschaltet.

    **Phase 4 hat seit dem 05.09.2026 eine zweite Bedingung**: es darf kein
    beendetes Interview ohne Verdichtung mehr geben
    (``aufnahme.unausgewertete_interviews``). Der Grund ist derselbe wie bei
    allem anderen hier -- die Materiallage: geschaerft wird spaeter am GANZEN
    Material, nicht an dem, was zufaellig schon ausgewertet war. Solange
    etwas offen ist, bietet die Knopfleiste \"Auswerten\" an statt \"Weiter\"."""
    from interview_theater import aufnahme

    stand = repo.hole_arbeitsstand(conn, chat_id)
    # Phase 5 haengt nicht an "mindestens zwei Figuren", sondern daran, dass
    # die Figurenliste **fixiert** ist -- die Gruppe hat sie abgenommen.
    # Auch bei nur einer Figur: ein Monolog ist ein Stueck.
    fixiert = bool(stand and (stand["figuren_fixiert_am"] or "").strip())
    setting = bool(stand and (stand["rahmen"] or "").strip())
    geschichte = bool(stand and (stand["geschichte"] or "").strip())
    szenen = bool(repo.hole_szenen(conn, chat_id))

    def feld(name: str) -> bool:
        """Ein Arbeitsstandfeld, das eine alte Datenbank noch nicht hat --
        die Migration ist additiv und laeuft beim Start, aber ein Leser darf
        daran nicht scheitern."""
        try:
            return bool(stand and (stand[name] or "").strip())
        except (IndexError, KeyError):
            return False

    def geprueft(name: str) -> bool:
        """Wie ``feld``, aber ein **leerer String zaehlt als gesetzt**
        (06.09.2026, Birk, Live-Befund Testgruppe).

        Der Fall sind die ``frage_einleitungen``: die Sensibilitaetspruefung
        kann zu dem Ergebnis kommen, dass keine Frage eine Einleitung
        braucht -- und *"keine noetig"* ist ein Ergebnis, kein fehlender
        Wert. In der Datenbank ist der Unterschied ``NULL`` (noch nie
        geprueft) gegen ``''`` (geprueft, nichts noetig). Ohne diese
        Unterscheidung waere die Gruppe entweder fuer immer blockiert oder
        die Pruefung nie noetig."""
        try:
            return bool(stand) and stand[name] is not None
        except (IndexError, KeyError):
            return False

    szenen_alle = repo.hole_szenen(conn, chat_id)
    return {
        2: bool(stand and stand["begriffe"]),
        # **Phase 3 haengt seit dem 06.09.2026 an VIER Dingen** (Birk, 09:20
        # und 10:00): den Fragen, den geprueften Einleitungen, dem
        # Eroeffnungs- UND dem Abschlusstext. Der Grund steht in
        # ``leitfaden.py``: die Gruppe geht damit auf fremde Menschen zu, und
        # eine Frageliste ohne Eroeffnung ist kein Interview, sondern eine
        # Ansprache. Der Live-Befund vom 10:00 war die Gegenprobe: standen
        # nur die Fragen, meldete der Bot Phase 2 als abgeschlossen und die
        # Gruppe ging ohne Leitfaden los.
        3: (
            bool(stand and stand["fragen"])
            # Geprueft ist die Sensibilitaet, sobald EINES der beiden Felder
            # gesetzt ist: seit dem 06.09.2026, 10:18 schreibt die Pruefung
            # weiche Fassungen (``fragen_weich``), davor Einleitungen. Eine
            # Gruppe, die den alten Weg schon hinter sich hat, wird nicht
            # zurueckgeworfen.
            and (geprueft("fragen_weich") or geprueft("frage_einleitungen"))
            and feld("interview_eroeffnung")
            and feld("interview_abschluss")
        ),
        4: bool(repo.verdichtungen(conn, chat_id))
        and not aufnahme.unausgewertete_interviews(conn, chat_id),
        5: setting and fixiert and bool(repo.figuren(conn, chat_id))
        and geschichte and szenen,
        6: geschichte and szenen,
        7: bool(szenen_alle) and all(
            (s["volltext"] or "").strip() for s in szenen_alle
        ),
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
    gemerkt = repo.hole_phase_angeboten(conn, chat_id)
    # ``abs``: ein NEGATIVER Merkposten ist dieselbe Stufe, nur abgelehnt
    # (``lehne_angebot_ab``) -- auch dann bleibt es still, bis
    # ``erneuere_nach_aenderung`` den Weg wieder freigibt.
    if gemerkt is not None and abs(gemerkt) == merkposten:
        return None
    return merkposten


def merke_angebot(conn, chat_id: int, nummer: int) -> None:
    """Haelt fest, dass diese Stufe angeboten wurde -- damit das Angebot sich
    nicht jeden Zug wiederholt (``arbeitsstand.phase_angeboten``)."""
    repo.setze_phase_angeboten(conn, chat_id, nummer)


#: Der Merkposten-Wert fuer "nichts gemerkt". Nicht ``None``, weil
#: ``setze_phase_angeboten`` eine Zahl schreibt; 0 ist keine Phase und
#: vergleicht sich deshalb mit keiner Stufe.
KEIN_ANGEBOT = 0


def vergiss_angebot(conn, chat_id: int) -> None:
    """Raeumt den Merkposten ab -- das naechste ``offenes_angebot`` bietet
    dieselbe Stufe wieder an (06.09.2026, Nacht-Simulation Punkt 6).

    Der Anlass: das Angebot fiel genau einmal je Stufe. Ging es unter, oder
    drueckte die Gruppe \"Noch etwas aendern\", kam es nie wieder -- auch nicht,
    wenn die Gruppe zwei Zuege spaeter ausdruecklich \"weiter\" sagte. Eine
    Bitte der Gruppe ist der Grund, ein Angebot zu ERNEUERN; genau dafuer ist
    diese Funktion da. Von selbst raeumt niemand ab."""
    repo.setze_phase_angeboten(conn, chat_id, KEIN_ANGEBOT)


def lehne_angebot_ab(conn, chat_id: int, nummer: int) -> None:
    """\"Noch etwas aendern\": das Angebot ist abgelehnt, aber nicht fuer immer.

    Gemerkt wird die Stufe NEGATIV. Fuer ``offenes_angebot`` zaehlt sie
    dadurch weiter als angeboten (kein Draengeln bei jeder Nachricht) -- und
    ``erneuere_nach_aenderung`` erkennt am Vorzeichen, dass das Angebot beim
    naechsten gespeicherten Parameter derselben Phase wiederkommen soll: die
    Gruppe hat ja gesagt, dass sie noch etwas aendern will, und wenn sie es
    getan hat, ist die Frage \"weiter?\" wieder faellig."""
    repo.setze_phase_angeboten(conn, chat_id, -abs(nummer))


def erneuere_nach_aenderung(conn, chat_id: int) -> bool:
    """Gab die Gruppe nach \"Noch etwas aendern\" wirklich etwas Neues an, wird
    das Angebot einmal erneuert. Liefert True, wenn das passiert ist.

    Einmal je Aenderung, nicht bei jeder Nachricht: der Aufrufer ist der
    Erkenner-Nachlauf, und der ruft hier nur auf, wenn tatsaechlich etwas in
    den Arbeitsstand geschrieben wurde."""
    gemerkt = repo.hole_phase_angeboten(conn, chat_id)
    if gemerkt is None or gemerkt >= 0:
        return False
    vergiss_angebot(conn, chat_id)
    return True

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

**Kein Modellaufruf.** ``naechste_moegliche`` liest ausschliesslich die
Datenbank (ueber ``repo``, damit das weiche Loeschen -- ``entfernt_am IS
NULL`` -- an einer Stelle bleibt und diese Datei kein eigenes SQL braucht).
Sie laeuft in jedem Gespraechszug, im kritischen Pfad.

**Die Phase steuert den Fokus, nicht den Informationszugang.** Die
datengetriebenen Bloecke aus ``kontext.baue`` bleiben unveraendert: was in
der Datenbank steht, geht in den Prompt, unabhaengig von der Phase. Die
Phase entscheidet nur, welchen Prompt-Zusatz der Bot bekommt
(``prompts/phasen/N.md``) -- worauf er den Fokus legt, was er in dieser
Phase nicht tut.
"""

from theatersoap import repo

#: Nummer, Kurzname, ein Satz. Die acht Stationen sind wortgleich die aus
#: ``prompts/system.md`` -- dort als Landkarte fuer das Gespraech, hier als
#: Datenmodell. Der Kurzname ist das, was in Meldungen und auf der
#: Weboberflaeche steht ("5 · Figuren entwickeln"), der Satz erklaert ihn,
#: wenn die Gruppe ``/phase`` ohne Argument schickt.
PHASEN = (
    (1, "Ankommen", "Ankommen, erste Begriffe und Assoziationen sammeln."),
    (2, "Interviews", "Interviews fuehren, Material zusammentragen."),
    (3, "Kernthema", "Aus dem Material ein Kernthema herausschaelen."),
    (4, "Hauptkonflikt", "Den Hauptkonflikt benennen, der das Stueck traegt."),
    (5, "Figuren entwickeln", "Figuren aus dem Material entwickeln."),
    (6, "Szenen entwerfen", "Die Szenenfolge entwerfen, noch ohne Text."),
    (7, "Szenentexte", "Szenentexte schreiben und schaerfen."),
    (8, "Durchlauf", "Durchlauf und Feinschliff vor der Auffuehrung."),
)

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
    """Wie eine Phase ueberall genannt wird: ``"5 · Figuren entwickeln"``.

    Eine einzige Schreibweise fuer Chatmeldung, ``/stand``, Begruessung,
    Prompt und Weboberflaeche -- damit niemand zwei Bezeichnungen fuer
    dasselbe lernen muss."""
    name = kurzname(nummer)
    return f"{nummer} · {name}" if name else str(nummer)


def liste() -> str:
    """Die acht Phasen als Text, eine Zeile je Phase (fuer ``/phase`` ohne
    Argument)."""
    return "\n".join(f"{nummer} · {name} - {text}" for nummer, name, text in PHASEN)


def nummer_fuer(wert: str | int | None) -> int | None:
    """Uebersetzt, was die Gruppe gesagt hat, in eine Phasennummer.

    Tolerant, in dieser Reihenfolge: eine Zahl 1-8; ein Kurzname (getrimmt,
    Kleinschreibung); ein Teiltreffer in Kurzname oder Satz, in beide
    Richtungen ("figuren" trifft "Figuren entwickeln", "wir sind bei den
    Figuren" ebenso). Passt nichts, ist das None -- und der Aufrufer aendert
    nichts, statt zu raten.

    Bei mehreren Teiltreffern gewinnt die kleinste Nummer ("szenen" trifft
    'Szenen entwerfen' vor 'Szenentexte'): der frueheren Phase zu
    widersprechen ist billiger als eine zu ueberspringen -- die Gruppe
    korrigiert es mit einem Satz."""
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
    for nummer, name, erklaerung in PHASEN:
        name = name.lower()
        if name in text or text in name:
            return nummer
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
    Begriffe da -> 2 ist moeglich; eine fertige Verdichtung -> 3; Kernthema
    -> 4; Hauptkonflikt -> 5; zwei Figuren -> 6; eine Szene -> 7; alle Szenen
    ausgeschrieben -> 8. Phase 1 braucht keine Voraussetzung, dorthin kommt
    man immer zurueck (aber nie automatisch).

    Die Bedingungen sind nicht kumulativ: eine Gruppe, die ohne Interviews
    direkt ein Kernthema setzt, darf trotzdem nach 4 -- die Reihenfolge ist
    eine Landkarte, kein Zwang (SPEC § 6.1)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    szenen = repo.hole_szenen(conn, chat_id)
    return {
        2: bool(stand and stand["begriffe"]),
        3: bool(repo.verdichtungen(conn, chat_id)),
        4: bool(stand and stand["kernthema"]),
        5: bool(stand and stand["hauptkonflikt"]),
        6: len(repo.figuren(conn, chat_id)) >= 2,
        7: bool(szenen),
        8: bool(szenen) and all(s["volltext"] for s in szenen),
    }


def naechste_moegliche(conn, chat_id: int) -> int | None:
    """Die hoechste Phase, die die Materiallage hergibt und die ueber der
    aktuellen liegt -- sonst None.

    Reine Leseabfrage, kein Schreiben, kein Modellaufruf: der Aufrufer
    entscheidet, ob daraus ein Angebot (``kontext.baue``) oder ein
    automatischer Sprung (``erkenner.laufe``) wird. Rueckwaerts liefert sie
    nie etwas -- eine Gruppe, die von 8 nach 5 zurueckgeht, soll nicht im
    naechsten Zug nach 8 zurueckgeschoben werden."""
    jetzige = aktuelle(conn, chat_id)
    moegliche = [
        nummer for nummer, erfuellt in voraussetzungen(conn, chat_id).items()
        if erfuellt and nummer > jetzige
    ]
    return max(moegliche) if moegliche else None


#: Welche Erkenner-art welche Phase moeglich macht -- die Grundlage des
#: automatischen Sprungs (``erkenner.laufe``): nur wenn der Erkenner IM
#: SELBEN LAUF genau die Aenderung geschrieben hat, die die naechste Phase
#: traegt, schaltet der Code um. "Kernthema gesetzt" belegt Phase 4, ein
#: beilaeufiger Journaleintrag belegt gar nichts.
ART_ERMOEGLICHT = {
    "begriffe_setzen": 2,
    "kernthema_setzen": 4,
    "hauptkonflikt_setzen": 5,
    "figur_setzen": 6,
}


def sprung_nach(conn, chat_id: int, wirkliche_aenderungen: list[dict]) -> int | None:
    """Die Phase, in die der Code nach diesem Erkennerlauf selbst umschalten
    darf -- oder None (der Normalfall).

    Drei Bedingungen, alle drei noetig: (1) eine der gerade geschriebenen
    Aenderungen traegt laut ART_ERMOEGLICHT genau die naechste Phase, (2) die
    Materiallage gibt sie tatsaechlich her (``naechste_moegliche``), (3) es
    geht um genau eine Phase vorwaerts. Nie rueckwaerts, nie ueber eine
    Phase hinweg -- alles andere ist ein Angebot, kein Sprung."""
    jetzige = aktuelle(conn, chat_id)
    ziel = jetzige + 1
    if ziel > LETZTE:
        return None
    if not any(
        ART_ERMOEGLICHT.get(a.get("art")) == ziel for a in wirkliche_aenderungen
    ):
        return None
    moeglich = naechste_moegliche(conn, chat_id)
    if moeglich is None or moeglich < ziel:
        return None
    return ziel

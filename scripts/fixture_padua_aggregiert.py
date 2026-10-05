"""Drei Straenge, je MEHRERE Sessions auf EINEM ``chat_id`` -- fuer Audit-Karte
t_97f605c7 ("was landet in Folgeprompts, wenn eine Gruppe einen Strang nicht
nur einmal, sondern wiederholt durchlaeuft").

**Warum eine eigene Datei statt einer Erweiterung von**
``scripts/fixture_padua_voll.py``: jene Fixture deckt pro Phase genau EINE
Diskussion/EIN Interview/EINEN Brainstorm ab -- genug, um zu zeigen, dass ein
Prompt ueberhaupt Material enthaelt, aber nichts darueber, was mit dem ZWEITEN,
DRITTEN, ... Durchlauf desselben Strangs passiert. Drei der vier verifizierten
Tatsachen oben (Kartentext) sind aber genau DAS: ``merke_diskussion_verdichtung``
ERSETZT bei jedem Aufruf die eine Zeile der Gruppe (``UNIQUE(chat_id)``), waehrend
``speichere_verdichtung`` bei jedem Aufruf eine NEUE Zeile anhaengt, und
``lege_begriffsboard_an`` haengt ebenfalls an, aber ``begriffsboard.schreibe_detail``
liest davon nur den JUENGSTEN Stand in EINE Spalte. Ohne mehrere Sessions auf
derselben Gruppe bleiben Ersetzen-vs-Anhaengen und "nur der letzte Stand zaehlt"
ungetestete Annahmen -- diese Fixture macht sie nachrechenbar.

**Die Honeypot-Fabrikation**: in genau einer Session je Strang wird absichtlich
ein erfundenes Detail (Name, Ort, Zahl) in ein Feld eingebaut, das NIE gegen das
Transkript verifiziert wird (die freie ``zusammenfassung`` einer Interview-
Verdichtung, der freie Verdichtungstext der Diskussion, die freie Buehnenkarte
des Brainstorms -- ``interview_theater.verdichter.verdichte()`` prueft NUR
``beleg_zitat``, nie ``zusammenfassung``). Jede Session, die das tut, markiert
sich selbst im Rueckgabewert (``fabrikation``/``fabrikationswort``), damit der
Pruefer aus Task 2 gezielt nachsehen kann, ob sein Detektor genau diese eine
Stelle findet -- nicht mehr und nicht weniger.

Alles hier ist **erfunden**. Das Interviewmaterial kommt aus
``simulation/interviews/set1`` (ebenfalls erfunden, gehoert ins Repository);
das Betriebsverzeichnis mit den echten Gruppen wird nie geoeffnet.
"""

from __future__ import annotations

import json
from pathlib import Path

from interview_theater import begriffsboard, repo, zitat

#: Weit oberhalb von ``fixture_padua_voll.CHAT_ID_BASIS`` (9_100_000_000_000)
#: und von ``repo.WEB_CHAT_ID_BASIS`` (7_000_000_000_000) -- eine Fixture-
#: chat_id dieser Datei soll mit keiner der anderen Fixture und keiner echten
#: Gruppe kollidieren, auch nicht in einer gemeinsam genutzten Wegwerf-DB.
CHAT_ID_BASIS = 9_200_000_000_000

#: Die drei Straenge, in dieser Reihenfolge nummeriert -- ``chat_id_fuer``
#: macht daraus feste, stabile chat_ids statt eines Hashwerts, damit ein
#: Pruefer-Skript sie ohne Umweg ueber diese Datei berechnen kann.
_STRAENGE = ("diskussion", "interviews", "brainstorm")


def chat_id_fuer(strang: str) -> int:
    """``chat_id`` fuer einen Strang -- analog zu
    ``fixture_padua_voll.chat_id_fuer(phase)``, nur mit einem String- statt
    einem Phasen-Schluessel."""
    if strang not in _STRAENGE:
        raise ValueError(f"unbekannter Strang: {strang!r}")
    return CHAT_ID_BASIS + _STRAENGE.index(strang) + 1


# --------------------------------------------------------------------------
# Strang 1: Phase 1, Hintergrund-Diskussion, mehrere Mithoer-Sessions
# --------------------------------------------------------------------------

#: Je Session zwei kurze, erfundene Diskussionssaetze -- ein wachsendes
#: Begriffsthema (arrival/waiting -> noise -> belonging -> trust -> language).
_DISKUSSION_SAETZE = (
    ("we keep coming back to waiting. everybody waited for something",
     "arrival felt different for each of us, some came by train, some by car"),
    ("and noise. the station is never quiet, you cannot think",
     "even at night there was noise, trucks or trains far away"),
    ("belonging is the hard one. you can wait and still belong",
     "home is not a place, someone said, it's who opens the door"),
    ("trust took years for some of us, not days",
     "we trust the bot with our words, that's new too"),
    ("language barriers made ordinary tasks feel large",
     "by the end we could laugh about the mistakes we made with words"),
)

#: Die Begriffe, die JE Session neu zur ``arbeitsstand.begriffe``-Liste
#: hinzukommen -- additiv, wie die Gruppe sie im echten Betrieb im Gespraech
#: nennt. Diese Liste schrumpft NIE: einmal genannt, bleibt ein Begriff im
#: Arbeitsstand stehen, auch wenn ihn das Begriffsboard spaeter nicht mehr
#: fuehrt (siehe ``_DISKUSSION_BOARD_BEGRIFFE`` unten).
_DISKUSSION_NEUE_BEGRIFFE = (
    ("arrival", "waiting"),
    ("noise",),
    ("belonging",),
    ("trust",),
    ("language",),
)

#: Was das Begriffsboard JE Session tatsaechlich fuehrt -- anders als
#: ``arbeitsstand.begriffe`` darf das SCHRUMPFEN: "arrival" faellt ab Session 3
#: aus dem Board (das Modell greift es im Lauf nicht mehr auf), bleibt aber
#: in der Begriffsliste stehen. Das ist der Fall, den
#: ``test_begriffe_detail_spiegelt_nur_den_juengsten_board_stand`` prueft:
#: ``begriffe_detail`` darf fuer "arrival" am Ende NICHTS mehr zeigen, obwohl
#: Session 1 und 2 dafuer Begruendung und Zitat hatten.
_DISKUSSION_BOARD_BEGRIFFE = (
    ("arrival", "waiting"),
    ("arrival", "waiting", "noise"),
    ("waiting", "noise", "belonging"),
    ("waiting", "noise", "belonging", "trust"),
    ("waiting", "noise", "belonging", "trust", "language"),
)

#: Zitat und Begruendung je Begriff -- einmal festgehalten, von
#: ``_diskussion_board_json`` fuer jede Session neu zusammengestellt, je
#: nachdem, welche Begriffe das Board in dieser Session noch fuehrt.
_DISKUSSION_BOARD_INFO = {
    "arrival": ("arrival felt different for each of us, some came by train, "
                "some by car",
                "named when the group compared how each of them travelled"),
    "waiting": ("we keep coming back to waiting. everybody waited for "
                "something",
                "the group returns to it in every session"),
    "noise": ("the station is never quiet, you cannot think",
              "named as the thing that blocks thinking"),
    "belonging": ("you can wait and still belong",
                  "named as the hardest term so far"),
    "trust": ("trust took years for some of us, not days",
              "distinguished from the few days the group has spent together"),
    "language": ("language barriers made ordinary tasks feel large",
                 "the last term added, about ordinary tasks"),
}

#: Je Session ein handgeschriebener Verdichtungstext, so wie ein Modell ihn
#: geliefert haette -- jeder traegt GENAU EIN woertliches Zitat in doppelten
#: Anfuehrungszeichen, das im bis dahin akkumulierten Diskussionstranskript
#: wirklich vorkommt (``_DISKUSSION_ZITATE`` unten, per ``assert`` geprueft).
_DISKUSSION_VERDICHTUNGEN = (
    'The group spent this opening session on arrival and waiting. One voice '
    'said "we keep coming back to waiting. everybody waited for something", '
    'and arrival felt different depending on how each person travelled.',

    'A second strand joined waiting this session: noise. Someone put it '
    'plainly, "the station is never quiet, you cannot think" - and the group '
    'agreed that noise made the waiting harder to sit through.',

    'Belonging came up as the hardest of the terms so far: "you can wait and '
    'still belong", one participant said. Dorotea, who joined only for this '
    'part of the conversation, added that belonging starts with whoever '
    'opens the door for you - a detail nobody else recorded hearing.',

    'Trust needed its own session: "trust took years for some of us, not '
    'days", someone said, separating it clearly from the handful of days '
    'the group has spent together so far.',

    'The last term, language, closed the arc: "language barriers made '
    'ordinary tasks feel large", and by the end the group could laugh about '
    'the mistakes they made with words.',
)

#: Die woertlichen Belegzitate, eines je Session, in genau der Form, in der
#: sie oben in ``_DISKUSSION_VERDICHTUNGEN`` stehen -- fuer den ``assert``
#: gegen ``repo.diskussion_transkript``.
_DISKUSSION_ZITATE = (
    "we keep coming back to waiting. everybody waited for something",
    "the station is never quiet, you cannot think",
    "you can wait and still belong",
    "trust took years for some of us, not days",
    "language barriers made ordinary tasks feel large",
)

#: GENAU EINE Session (1-basiert) traegt die Honeypot-Fabrikation: einen
#: erfundenen Eigennamen, der in KEINEM Diskussionstranskript vorkommt, aber
#: im (unverifizierten) Verdichtungstext dieser Session steht.
_DISKUSSION_FABRIKATION_SESSION = 3
_DISKUSSION_FABRIKATIONSWORT = "Dorotea"


def _diskussion_board_json(begriffe: tuple[str, ...]) -> str:
    eintraege = []
    for i, begriff in enumerate(begriffe):
        zitat_text, begruendung = _DISKUSSION_BOARD_INFO[begriff]
        eintraege.append({
            "begriff": begriff,
            "nennungen": i + 1,
            "zitat": zitat_text,
            "begruendung": begruendung,
            "doppelbedeutung": "",
        })
    return json.dumps(eintraege, ensure_ascii=False)


def baue_diskussion_sessions(conn, chat_id: int, anzahl: int = 5) -> list[dict]:
    """Fuehrt ``anzahl`` aufeinanderfolgende P1-Mithoer-Sessions auf EINEM
    ``chat_id`` aus -- siehe Modul-Docstring fuer das WARUM."""
    repo.sichere_gruppe(conn, chat_id, "padua-aggregiert",
                        "Padua aggregated: background discussion")
    ergebnisse: list[dict] = []
    begriffe_kumuliert: list[str] = []
    message_id = 300
    for i in range(anzahl):
        session = i + 1
        idx = i % len(_DISKUSSION_SAETZE)

        for text in _DISKUSSION_SAETZE[idx]:
            message_id += 1
            aufnahme_id = repo.lege_aufnahme_an(
                conn, chat_id, message_id, "kurz", "web", status="fertig",
                diskussion=True,
            )
            repo.setze_transkript(conn, aufnahme_id, text)

        for neu in _DISKUSSION_NEUE_BEGRIFFE[idx]:
            if neu not in begriffe_kumuliert:
                begriffe_kumuliert.append(neu)
        begriffe_text = ", ".join(begriffe_kumuliert)
        repo.setze_arbeitsstand(conn, chat_id, "begriffe", begriffe_text)

        board_begriffe = _DISKUSSION_BOARD_BEGRIFFE[idx]
        letzte_aufnahme_id = repo.hoechste_diskussion_aufnahme_id(conn, chat_id)
        repo.lege_begriffsboard_an(
            conn, chat_id, _diskussion_board_json(board_begriffe), "claude",
            letzte_aufnahme_id,
        )
        begriffsboard.schreibe_detail(conn, chat_id, begriffe_text)

        transkript_bisher = repo.diskussion_transkript(conn, chat_id)
        zitat_text = _DISKUSSION_ZITATE[idx]
        # Harte Zusicherung, wie fixture_padua_voll._material es tut: ein
        # unbelegtes Zitat waere im Dump ein erfundenes Zitat.
        assert zitat_text in transkript_bisher, (session, "Zitat fehlt im Transkript")

        verdichtung_text = _DISKUSSION_VERDICHTUNGEN[idx]
        fabrikation = session == _DISKUSSION_FABRIKATION_SESSION
        fabrikationswort = _DISKUSSION_FABRIKATIONSWORT if fabrikation else None
        if fabrikation:
            # Die Honeypot-Fabrikation ist NUR im (unverifizierten)
            # Verdichtungstext -- nie im Transkript selbst, sonst waere sie
            # keine Fabrikation.
            assert fabrikationswort in verdichtung_text, session
            assert fabrikationswort not in transkript_bisher, session

        repo.merke_diskussion_verdichtung(conn, chat_id, verdichtung_text, "claude")

        ergebnisse.append({
            "session": session,
            "verdichtung_text": verdichtung_text,
            "transkript_bisher": transkript_bisher,
            "zeichen": len(verdichtung_text),
            "fabrikation": fabrikation,
            "fabrikationswort": fabrikationswort,
        })
    return ergebnisse


# --------------------------------------------------------------------------
# Strang 2: Phase 3, mehrere Interviews auf EINEM chat_id
# --------------------------------------------------------------------------

_INTERVIEW_DATEIEN = (
    Path("simulation/interviews/set1/1-meryem-koffer.md"),
    Path("simulation/interviews/set1/2-ferzan-bahnhof.md"),
    Path("simulation/interviews/set1/3-aynur-winter.md"),
    Path("simulation/interviews/set1/4-ljiljana-papiere.md"),
    Path("simulation/interviews/set1/5-halina-nachbarin.md"),
)

#: Je Interview ein handgeschriebenes ``zusammenfassung``-Feld (2-3 Saetze,
#: echter Inhalt aus dem jeweiligen Transkript) und 1-2 Kernthemen mit
#: woertlichen Zitaten -- dieselben Zitate, die auch im Dateikopf unter
#: ``zitate_soll`` stehen, hier per ``assert`` ueber ``zitat.pruefe`` erneut
#: verifiziert (nicht blind aus dem Dateikopf uebernommen).
_INTERVIEW_DATEN = (
    {
        "zusammenfassung": (
            "Meryem remembers leaving home with one solid brown suitcase her "
            "father bought, packed with two dresses, a headscarf, a Quran, "
            "and tomato seeds her mother wrapped in a handkerchief. The "
            "suitcase stayed packed under her bed for three years because "
            "the family always planned to go back, until her son was born "
            "and she finally unpacked it."
        ),
        "themen": [
            {"thema": "suitcase", "kurz": "the brown suitcase",
             "beleg_zitat": "Der Koffer war braun, so ein Braun wie Milchkaffee.",
             "zitat_geprueft": 1},
            {"thema": "not unpacking", "kurz": "three years packed",
             "beleg_zitat": "Drei Jahre stand der Koffer unter dem Bett, gepackt.",
             "zitat_geprueft": 1},
        ],
    },
    {
        "zusammenfassung": (
            "Ferzan's first memory of arriving is the railway station, "
            "waiting three hours alone on a bench with a broken bag while "
            "his cousin was delayed. He could not understand the "
            "announcements except platform numbers, noticed pigeons living "
            "inside the station hall, and finally laughed for the first "
            "time here when the broken bag spilled socks across the floor."
        ),
        "themen": [
            {"thema": "waiting", "kurz": "three hours on the bench",
             "beleg_zitat": "Ich habe drei Stunden auf dieser Bank gesessen "
                            "und nichts gegessen.",
             "zitat_geprueft": 1},
            {"thema": "noise", "kurz": "the loudspeaker",
             "beleg_zitat": "Der Lautsprecher hat geredet und ich habe kein "
                            "einziges Wort verstanden.",
             "zitat_geprueft": 1},
        ],
    },
    {
        # Honeypot-Session (Interview 3 von 5: nicht das erste, nicht das
        # letzte): "Mehmet" ist frei erfunden und steht in KEINEM Satz
        # dieses Transkripts -- die Zusammenfassung wird von
        # ``verdichter.verdichte`` nie gegen das Transkript geprueft.
        "zusammenfassung": (
            "Aynur describes her first winter: thin cloth shoes soaked "
            "through immediately, a coal oven she was afraid to tend in the "
            "dark cellar, and days so short she thought the sun was broken. "
            "Her son Mehmet started school three weeks after they arrived, "
            "and a neighbour eventually showed her how to dry laundry "
            "indoors instead of on the frozen balcony."
        ),
        "themen": [
            {"thema": "cold", "kurz": "thin cloth shoes",
             "beleg_zitat": "Meine Schuhe waren aus Stoff, weisst du, so "
                            "duenne Stoffschuhe.",
             "zitat_geprueft": 1},
            {"thema": "darkness", "kurz": "the sun is broken",
             "beleg_zitat": "Ich hab gedacht, die Sonne ist kaputt hier.",
             "zitat_geprueft": 1},
        ],
    },
    {
        "zusammenfassung": (
            "Ljiljana recalls the early months as an endless sequence of "
            "government offices and waiting numbers, with a blue folder of "
            "translated, certified documents she still keeps today. Her "
            "family lived for years on temporary permits renewed every few "
            "months, and she still opens official-looking letters standing "
            "up, out of old habit."
        ),
        "themen": [
            {"thema": "paperwork", "kurz": "the blue folder",
             "beleg_zitat": "Meine Mappe war blau, und sie ist immer noch "
                            "blau.",
             "zitat_geprueft": 1},
            {"thema": "waiting", "kurz": "green waiting room",
             "beleg_zitat": "Der Flur war gruen, die Stuehle waren gruen, "
                            "alles gruen.",
             "zitat_geprueft": 1},
        ],
    },
    {
        "zusammenfassung": (
            "Halina's first memory is the stairwell of her new building, "
            "where she read every nameplate hoping to find someone whose "
            "name she could pronounce. For three weeks she avoided greeting "
            "neighbours out of fear of not understanding their answer, "
            "until a neighbour showed up with a jar of flour and no shared "
            "language at all, and patiently explained the yellow recycling "
            "bag three times."
        ),
        "themen": [
            {"thema": "fear of language", "kurz": "afraid of the answer",
             "beleg_zitat": "Ich habe drei Wochen niemanden gegruesst, weil "
                            "ich Angst hatte vor der Antwort.",
             "zitat_geprueft": 1},
            {"thema": "neighbour", "kurz": "flour without words",
             "beleg_zitat": "Sie hatte Mehl in der Hand, ein Glas voll, kein "
                            "Wort Polnisch.",
             "zitat_geprueft": 1},
        ],
    },
)

#: GENAU EIN Interview (1-basiert, Session 3 von 5 -- weder erstes noch
#: letztes) traegt die Honeypot-Fabrikation.
_INTERVIEW_FABRIKATION_SESSION = 3
_INTERVIEW_FABRIKATIONSWORT = "Mehmet"


def baue_interview_sessions(conn, chat_id: int, anzahl: int = 5) -> list[dict]:
    """Fuehrt ``anzahl`` Interviews auf EINEM ``chat_id`` aus, je eines aus
    ``simulation/interviews/set1`` -- siehe Modul-Docstring fuer das WARUM."""
    repo.sichere_gruppe(conn, chat_id, "padua-aggregiert",
                        "Padua aggregated: interviews")
    ergebnisse: list[dict] = []
    for i in range(anzahl):
        session = i + 1
        idx = i % len(_INTERVIEW_DATEIEN)
        roh = _INTERVIEW_DATEIEN[idx].read_text(encoding="utf-8")
        transkript = roh.split("---", 2)[2].strip()
        daten = _INTERVIEW_DATEN[idx]
        zusammenfassung = daten["zusammenfassung"]
        themen = daten["themen"]

        for thema in themen:
            # Dieselbe harte Zusicherung wie bei ``fixture_padua_voll._material``:
            # ein Belegzitat, das ``zitat.pruefe`` nicht bestaetigt, waere im
            # Dump ein erfundenes Zitat.
            assert zitat.pruefe(thema["beleg_zitat"], transkript), (
                _INTERVIEW_DATEIEN[idx], thema["thema"])

        fabrikation = session == _INTERVIEW_FABRIKATION_SESSION
        fabrikationswort = _INTERVIEW_FABRIKATIONSWORT if fabrikation else None
        if fabrikation:
            assert fabrikationswort in zusammenfassung, session
            assert fabrikationswort not in transkript, session

        aufnahme_id = repo.lege_aufnahme_an(
            conn, chat_id, 500 + i, "lang", "text", status="fertig")
        repo.setze_transkript(conn, aufnahme_id, transkript)
        verdichtung_id = repo.speichere_verdichtung(
            conn, chat_id, aufnahme_id, zusammenfassung, themen)

        ergebnisse.append({
            "session": session,
            "aufnahme_id": aufnahme_id,
            "verdichtung_id": verdichtung_id,
            "zusammenfassung": zusammenfassung,
            "transkript": transkript,
            "zeichen": len(zusammenfassung),
            "fabrikation": fabrikation,
            "fabrikationswort": fabrikationswort,
        })
    return ergebnisse


# --------------------------------------------------------------------------
# Strang 3: Phase 4, mehrere Brainstorm-Sessions auf EINEM chat_id
# --------------------------------------------------------------------------

#: Je Session ein kurzer, erfundener Brainstorm-Satz -- Figuren-/Setting-
#: Ideen, die aufeinander aufbauen.
_BRAINSTORM_SAETZE = (
    "what if the station has a lost-and-found window nobody ever visits",
    "the cousin could be funnier if he over-apologises every single time "
    "he's late",
    "what if there's a stationmaster character who used to be a dancer",
    "Elena could keep a secret notebook of all her regular customers",
    "let's end on the socks joke but have the stationmaster join the laugh "
    "too",
)

#: Je Session eine handgeschriebene Buehnenkarte (``repo.lege_buehnenkarte_an``
#: persistiert sie -- die Funktion existiert, siehe Modul-Docstring). Jede
#: Karte ist eine Regie-Notiz zur jeweiligen Session-Idee; GENAU EINE
#: (Session 3) traegt die Honeypot-Fabrikation.
_BRAINSTORM_KARTEN = (
    "STAGE NOTE: Keep the lost-and-found window as a single visual detail "
    "in scene 1, not a subplot - a locked window Samir glances at once.",

    "STAGE NOTE: Tommaso's double apology already lands in the interview "
    "material; let the brainstorm's 'over-apologising' sharpen it, don't "
    "add a third apology.",

    "STAGE NOTE: Give the stationmaster a name - Rosaria - and let her "
    "mention she has worked this platform for eleven years, long enough to "
    "recognise every regular face.",

    "STAGE NOTE: Elena's notebook could replace a line of dialogue with a "
    "gesture - she checks it instead of answering him directly.",

    "STAGE NOTE: If the stationmaster joins the laugh, let it happen "
    "without a line - a held beat, then he walks on.",
)

#: GENAU EINE Session (1-basiert, nicht die erste, nicht die letzte) traegt
#: die Honeypot-Fabrikation -- ein Name und eine Zahl, die in KEINEM
#: Brainstorm-Mitschnitt vorkommen.
_BRAINSTORM_FABRIKATION_SESSION = 3
_BRAINSTORM_FABRIKATIONSWORT = "Rosaria"


def baue_brainstorm_sessions(conn, chat_id: int, anzahl: int = 5) -> list[dict]:
    """Fuehrt ``anzahl`` Brainstorm-Sessions auf EINEM ``chat_id`` in Phase 4
    aus -- siehe Modul-Docstring fuer das WARUM. Ruft bewusst NICHT
    ``buehnenkarte.erzeuge()`` (braucht ein LLM), sondern persistiert
    handgeschriebene Karten ueber ``repo.lege_buehnenkarte_an`` -- diese
    Funktion gibt es (anders als ein Fehlen, das hier als ehrliche
    Einschraenkung vermerkt werden muesste)."""
    repo.sichere_gruppe(conn, chat_id, "padua-aggregiert",
                        "Padua aggregated: brainstorm")
    # Schlanker Setup statt der vollen fixture_padua_voll.baue()-Logik --
    # Phase 4 braucht nur Setting und Geschichte, damit sie ueberhaupt als
    # "in Phase 4" gilt (phasen.voraussetzungen verlangt hier nicht mehr).
    repo.setze_arbeitsstand(
        conn, chat_id, "rahmen",
        "A railway station in a northern Italian city, one wet November "
        "evening.",
    )
    repo.setze_arbeitsstand(
        conn, chat_id, "geschichte",
        "Samir waits for a cousin who does not come, then laughs for the "
        "first time here when a broken bag opens.",
    )
    repo.setze_phase(conn, chat_id, 4)

    ergebnisse: list[dict] = []
    for i in range(anzahl):
        session = i + 1
        idx = i % len(_BRAINSTORM_SAETZE)
        text = _BRAINSTORM_SAETZE[idx]

        aufnahme_id = repo.lege_aufnahme_an(
            conn, chat_id, 700 + i, "kurz", "web", status="fertig",
            brainstorm=True,
        )
        repo.setze_transkript(conn, aufnahme_id, text)
        transkript_bisher = repo.brainstorm_transkript(conn, chat_id)
        zeichen = len(transkript_bisher)

        karte_text = _BRAINSTORM_KARTEN[idx]
        fabrikation = session == _BRAINSTORM_FABRIKATION_SESSION
        fabrikationswort = _BRAINSTORM_FABRIKATIONSWORT if fabrikation else None
        if fabrikation:
            assert fabrikationswort in karte_text, session
            assert fabrikationswort not in transkript_bisher, session
        repo.lege_buehnenkarte_an(conn, chat_id, karte_text, "claude")

        ergebnisse.append({
            "session": session,
            "aufnahme_id": aufnahme_id,
            "brainstorm_transkript_zeichen": zeichen,
            "karte_persistiert": True,
            "fabrikation": fabrikation,
            "fabrikationswort": fabrikationswort,
        })
    return ergebnisse


def baue_alle(conn) -> dict:
    """Baut alle drei Straenge, je auf einem eigenen frischen ``chat_id``."""
    ergebnis: dict = {}
    for strang, baufunktion in (
        ("diskussion", baue_diskussion_sessions),
        ("interviews", baue_interview_sessions),
        ("brainstorm", baue_brainstorm_sessions),
    ):
        chat_id = chat_id_fuer(strang)
        sessions = baufunktion(conn, chat_id, 5)
        ergebnis[strang] = {"chat_id": chat_id, "sessions": sessions}
    return ergebnis

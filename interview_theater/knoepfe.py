"""Inline-Knoepfe fuer die drei Auswahl-Momente (05.09.2026).

**Warum es das gibt.** Die Sprachnavigation ist an Auswahl-Momenten
unzuverlaessig -- gemessen am 05.09.2026: der Absichtserkenner
(``erkenner.py``) erkennt eine Kernthema-Festlegung zuverlaessig, wenn er das
ganze Gespraech sieht (3/3), aber live sieht er nur ein Fenster von ein bis
drei Nachrichten. Im Fenster mit der Zustimmung schrieb er ``entschieden``
(eine Journalnotiz) statt ``kernthema_setzen`` (ein Arbeitsstand-Feld). Die
Festlegung landete deshalb nicht in der Datenbank und erschien nicht auf der
Weboberflaeche.

Ein Knopf traegt die Auswahl selbst -- es ist nichts zu erraten. Genau
dafuer, und nur dafuer, sind Knoepfe hier gedacht: **drei Stellen**, an denen
die Gruppe aus wenigen benannten Moeglichkeiten waehlt (Kernthema,
Aufnahme an/aus, naechste Phase). Alles andere -- Begriffe, Fragen,
Figurenbeschreibungen -- bleibt bewusst Sprache: dort gibt es keine Liste,
aus der sich waehlen liesse.

**Drei Zusagen, an denen sich dieser Code messen laesst:**

1. ``callback_data`` bleibt unter 64 Bytes (Telegram-Grenze). Ein Knopf
   traegt nur ``k:<id>`` -- der eigentliche Wert (ein Kernthema kann laenger
   sein als die ganze Grenze) steht in der Tabelle ``knopf``. Geprueft wird
   die Grenze in ``telegram.Telegram.sende_mit_knoepfen``, nicht hier.
2. **Kein Modellaufruf.** Wie bei den Slash-Befehlen (``befehle.py``) greift
   ein Knopf frueh und deterministisch: ``bot.schleife`` gibt ihn ab, bevor
   irgendein Kontext gebaut wird. Was ein Modell braucht, geht wie ueberall
   an einen eigenen Thread (``aufnahme.starte_abschluss``).
3. **Idempotent.** Jeder Druck wird ueber ``repo.beanspruche_knopf``
   beansprucht -- ein bedingtes UPDATE, das nur einmal gewinnt. Der zweite
   Druck bekommt eine freundliche Rueckmeldung und loest nichts aus.
"""

import logging

from interview_theater import phasen, repo

log = logging.getLogger(__name__)

#: Praefix in ``callback_data``. Ein Buchstabe, weil daneben nur noch die id
#: Platz hat -- und sie soll auch bei einer sechsstelligen id nicht an die
#: 64-Byte-Grenze stossen (``k:999999`` sind neun Bytes).
PRAEFIX = "k:"

ART_KERNTHEMA = "kernthema"
ART_AUFNAHME = "aufnahme"
ART_PHASE = "phase"
#: Format des Stuecks (Phase 5) -- dasselbe Ziel wie ``/stueck format <text>``.
ART_FORMAT = "format"
#: Form je Szene (Phase 6) -- dasselbe Ziel wie ``/szene <n> form <wert>``.
#: Der Wert der Knopfzeile traegt beides, durch ':' getrennt: "3:dialog".
ART_SZENENFORM = "szenenform"
#: Einwilligung ins US-Modell -- dasselbe Ziel wie ``/szene usa ja|nein``.
ART_SZENE_USA = "szene_usa"

#: Hoechstens drei Vorschlaege je Kernthema-Angebot. Mehr ist keine Auswahl
#: mehr, sondern eine Liste, die gelesen werden will -- und die Gruppe steht
#: im Raum vor einem Telefon.
MAX_VORSCHLAEGE = 3

_TEXT_KERNTHEMA_FRAGE = "Welches Kernthema nehmen wir? Tippt eins an - oder sagt mir ein anderes."
_TEXT_KERNTHEMA_KEINE = (
    "Ich habe noch keine Vorschlaege - die entstehen aus den ausgewerteten "
    "Interviews. Ihr koennt mir das Kernthema auch einfach sagen."
)
_TEXT_SCHON_BENUTZT = "Das habe ich schon uebernommen."
_TEXT_UNBEKANNT = "Diesen Knopf kenne ich nicht mehr."
_TEXT_AUFNAHME_STARTEN = "Aufnahme starten"
_TEXT_AUFNAHME_BEENDEN = "Aufnahme beenden"

#: Hoechstens vier Formatvorschlaege (Phase 5). Mehr Knoepfe als
#: Kernthema-Vorschlaege sind hier vertretbar, weil die Beschriftungen kurz
#: sind ("Sprechtheater") und nicht wie ein Kernthema ganze Saetze werden.
MAX_FORMATE = 4

#: Der Rueckfall, wenn niemand eigene Vorschlaege mitgibt -- die vier Formen,
#: die ``prompts/phasen/5.md`` selbst aufzaehlt. Fest verdrahtet und NICHT
#: vom Modell erfragt: ein Knopf-Handler ruft kein Sprachmodell (AGENTS.md),
#: und diese vier sind ohnehin die Auswahl, die die Phase anbietet. Eine
#: Mischform steht bewusst nicht dabei -- die sagt die Gruppe frei, dafuer
#: gibt es ``/stueck format <text>``.
STANDARD_FORMATE = ("Sprechtheater", "Musical", "Revue", "Hoerstueck")

_TEXT_FORMAT_FRAGE = "Welches Format nehmen wir? Tippt eins an - oder sagt mir ein anderes."
_TEXT_FORMAT_KEINE = (
    "Ich habe gerade keine Vorschlaege. Ihr koennt es mir auch einfach "
    "sagen: /stueck format Sprechtheater mit Chor."
)
_TEXT_SZENENFORM_FRAGE = "Welche Form soll Szene {nummer} haben?"
_TEXT_USA_FRAGE_KNOEPFE = "Tippt an, was gelten soll:"
_TEXT_USA_JA_KNOPF = "Ja, US-Modell"
_TEXT_USA_NEIN_KNOPF = "Nein, Schweiz"
_TEXT_USA_JA = (
    "Gut, Szenen kommen ab jetzt vom US-Modell. Ich sage es vor jeder "
    "Szene nochmal."
)
_TEXT_USA_NEIN = "Verstanden, alles bleibt in der Schweiz. Ich frage nicht wieder."


def _daten(knopf_id: int) -> str:
    """Die ``callback_data`` zu einer Knopf-id."""
    return f"{PRAEFIX}{knopf_id}"


def _id_aus_daten(daten: str) -> int | None:
    """Liest die Knopf-id aus ``callback_data``; None bei allem anderen.

    Tolerant gegenueber Fremdem: in einer Gruppe kann ein anderer Bot
    Knoepfe stehen haben, und ein Knopfdruck aus einer alten Fassung dieses
    Bots (anderes Format) darf die Schleife nicht zum Absturz bringen."""
    if not daten.startswith(PRAEFIX):
        return None
    rest = daten[len(PRAEFIX):]
    return int(rest) if rest.isdigit() else None


def _entferne_tastatur(tg, chat_id, message_id) -> None:
    """Nimmt die Knoepfe unter der Angebotsnachricht weg -- nachdem die
    Wirkung eingetreten ist, nie davor.

    Fehlschlaege werden geschluckt: die Wirkung steht schon in der Datenbank,
    und die Gruppe soll wegen einer misslungenen Kosmetik keine Fehlermeldung
    sehen (global-constraints.md 'Fehlerhaltung')."""
    if message_id is None:
        return
    try:
        tg.entferne_knoepfe(chat_id, message_id)
    except Exception:
        log.warning("Knoepfe entfernen fehlgeschlagen, chat_id=%s", chat_id)


# --- Angebote -------------------------------------------------------------


def kernthema_vorschlaege(conn, chat_id: int) -> list[str]:
    """Bis zu ``MAX_VORSCHLAEGE`` Kernthema-Vorschlaege, rein aus der
    Datenbank -- die Kurzformen der Verdichtungsthemen
    (``verdichtung_thema.kurz``, hoechstens acht Woerter).

    Kein Modellaufruf: die Themen sind schon beim Verdichten eines Interviews
    entstanden und bezahlt, sie hier ein zweites Mal zu erfragen waere ein
    zweiter Aufruf fuer dasselbe Ergebnis. Doppelte fallen raus (zwei
    Interviews koennen dasselbe Thema tragen), die Reihenfolge bleibt die der
    Entstehung -- die aelteste Verdichtung zuerst."""
    gesehen: list[str] = []
    for verdichtung in repo.verdichtungen(conn, chat_id):
        for thema in repo.themen_zu(conn, verdichtung["id"]):
            text = (thema["kurz"] or thema["thema"] or "").strip()
            if text and text not in gesehen:
                gesehen.append(text)
    return gesehen[:MAX_VORSCHLAEGE]


def biete_kernthema(conn, tg, chat_id: int, vorschlaege: list[str] | None = None) -> bool:
    """Bietet die Kernthema-Vorschlaege als Knoepfe an. Liefert False, wenn
    es nichts anzubieten gab -- dann hat der Aufrufer bereits die Zeile
    bekommen, die das erklaert.

    Der Volltext steht in der Beschriftung UND in der Tabelle ``knopf``, nie
    in ``callback_data`` (Zusage 1 im Moduldocstring)."""
    if vorschlaege is None:
        vorschlaege = kernthema_vorschlaege(conn, chat_id)
    vorschlaege = [v for v in vorschlaege if v.strip()][:MAX_VORSCHLAEGE]
    if not vorschlaege:
        tg.sende(chat_id, _TEXT_KERNTHEMA_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_KERNTHEMA, wert)))
        for wert in vorschlaege
    ]
    tg.sende_mit_knoepfen(chat_id, _TEXT_KERNTHEMA_FRAGE, knoepfe)
    return True


def biete_aufnahme(conn, tg, chat_id: int, text: str) -> None:
    """Haengt den Aufnahme-Umschalter unter ``text``.

    Die Beschriftung richtet sich nach dem Zustand JETZT: laeuft eine
    Aufnahme, heisst der Knopf "Aufnahme beenden", sonst "Aufnahme starten".
    Die Wirkung ist beide Male dieselbe wie ``/aufnahme`` -- ein Umschalter,
    kein Ein- und ein Ausschalter (befehle._befehl_aufnahme): sonst gaebe es
    zwei Zustaende und drei Bedienelemente, und genau daran ist die
    gesprochene Variante am 05.09.2026 gescheitert."""
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = _TEXT_AUFNAHME_BEENDEN if laeuft else _TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = f"Weiter zu {phasen.bezeichnung(nummer)}"
    tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_format(conn, tg, chat_id: int, vorschlaege: list[str] | None = None) -> bool:
    """Bietet die Formatvorschlaege aus Phase 5 als Knoepfe an (05.09.2026).

    Warum hier ein Knopf: seit ed51db1 stellt phasen/5.md das Format als
    NUMMERIERTE Auswahl ("1. Sprechtheater, 2. Musical, ..."). Die Gruppe
    antwortet darauf typischerweise mit "das erste" oder "ok" -- der
    Absichtserkenner sieht live nur ein Fenster von ein bis drei Nachrichten
    und kann daraus nicht ableiten, welcher Listenpunkt gemeint war. Ein
    Knopf traegt die Auswahl selbst; die Wirkung ist wortgleich die von
    ``/stueck format <text>`` (befehle._befehl_stueck).

    Liefert False, wenn es nichts anzubieten gab -- dann steht statt der
    Tastatur die Zeile, die das erklaert. Ohne ``vorschlaege`` gelten die
    ``STANDARD_FORMATE``.

    Der Volltext steht in der Beschriftung UND in der Tabelle ``knopf``, nie
    in ``callback_data`` (Zusage 1 im Moduldocstring): ein Format wie
    "Sprechtheater mit Chorpassagen und Liedern" sprengt die 64 Bytes."""
    if vorschlaege is None:
        vorschlaege = list(STANDARD_FORMATE)
    vorschlaege = [v.strip() for v in vorschlaege if v and v.strip()][:MAX_FORMATE]
    if not vorschlaege:
        tg.sende(chat_id, _TEXT_FORMAT_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_FORMAT, wert)))
        for wert in vorschlaege
    ]
    tg.sende_mit_knoepfen(chat_id, _TEXT_FORMAT_FRAGE, knoepfe)
    return True


def biete_szenenform(conn, tg, chat_id: int, nummer: int, text: str | None = None) -> None:
    """Bietet die sechs Formen fuer EINE Szene als Knoepfe an (05.09.2026).

    Warum hier ein Knopf: 553e3aa stellt die Form je Szene in phasen/6.md als
    nummerierte Auswahl. Dieselbe Schwaeche wie beim Format -- "nimm das
    dritte" ist fuer den Erkenner nicht aufloesbar, und eine falsch geratene
    Form fuehrt zu einem Szenentext nach den falschen Dramaturgieregeln
    (``prompts/formen/<name>.md``).

    Die Szenennummer MUSS mitwandern, sonst wuesste der Knopfdruck nicht,
    welche Szene gemeint ist. Sie steht dafuer im ``wert`` der Knopfzeile
    ("3:dialog"), nicht in ``callback_data`` -- dort steht wie ueberall nur
    die Knopf-id. Damit bleibt die 64-Byte-Grenze unabhaengig von Nummer und
    Formnamen eingehalten.

    Die Liste kommt aus ``szene.FORMEN`` und wird hier NICHT zweitgepflegt:
    kommt dort eine Form dazu, gibt es den Knopf automatisch."""
    from interview_theater import szene

    knoepfe = [
        (
            form.capitalize(),
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFORM, f"{nummer}:{form}")),
        )
        for form in szene.FORMEN
    ]
    tg.sende_mit_knoepfen(
        chat_id, text or _TEXT_SZENENFORM_FRAGE.format(nummer=nummer), knoepfe
    )


def biete_szene_usa(conn, tg, chat_id: int, text: str | None = None) -> None:
    """Haengt die beiden Einwilligungsknoepfe unter das USA-Angebot
    (``szene._TEXT_ANGEBOT_USA``).

    Der Anlass ist der teuerste gemessene Fehler des 05.09.2026: der Bot
    fragte nach dem US-Modell, die Gruppe antwortete siebenmal sinngemaess
    "ja" -- der Erkenner las es jedes Mal als Zustimmung zu den FIGUREN, und
    der Bot wiederholte dieselbe Erinnerung, bis der Notausgang
    (``szene.USA_ERINNERUNGEN_MAX``) griff und in der Schweiz schrieb. Eine
    Einwilligung ist genau der Fall, der nicht erraten werden darf: hier
    entscheidet die Gruppe ueber eine Datenuebermittlung.

    Zwei Knoepfe und nicht einer: anders als beim Aufnahme-Umschalter sind
    Ja und Nein zwei verschiedene Entscheidungen mit verschiedenen Folgen,
    und ein Nein muss genauso ein Druck sein wie ein Ja -- sonst waere
    Schweigen die einzige Form der Ablehnung."""
    knoepfe = [
        (_TEXT_USA_JA_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "ja"))),
        (_TEXT_USA_NEIN_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "nein"))),
    ]
    tg.sende_mit_knoepfen(chat_id, text or _TEXT_USA_FRAGE_KNOEPFE, knoepfe)


# --- Verarbeitung ---------------------------------------------------------


def _wirke(conn, tg, klm, e, knopf, chat_id: int) -> str:
    """Fuehrt die Wirkung eines beanspruchten Knopfes aus und liefert den
    kurzen Text fuer answerCallbackQuery.

    Wird NUR aufgerufen, wenn ``repo.beanspruche_knopf`` True geliefert hat --
    die Idempotenz haengt an dieser einen Bedingung und nicht daran, dass
    jede Wirkung fuer sich wiederholbar waere."""
    art = knopf["art"]
    if art == ART_KERNTHEMA:
        # Der eigentliche Punkt der Uebung: deterministisch schreiben, was
        # der Erkenner live nicht zuverlaessig traf.
        repo.setze_arbeitsstand(conn, chat_id, "kernthema", knopf["wert"])
        repo.schreibe_journal(
            conn, chat_id, "entschieden", f"Kernthema: {knopf['wert']}", quelle="knopf",
        )
        tg.sende(chat_id, f"Kernthema notiert: {knopf['wert']}")
        return "Kernthema uebernommen"
    if art == ART_AUFNAHME:
        # Wortgleich dasselbe wie /aufnahme -- inklusive der Verdichtung im
        # eigenen Thread. Kein zweiter Weg fuer dieselbe Sache.
        #
        # Import erst hier: ``befehle`` bietet Knoepfe an (biete_kernthema)
        # und ``knoepfe`` ruft einen Befehl auf -- ein Modulimport oben
        # waere ein Zyklus. Der Aufruf ist selten (ein Knopfdruck), der
        # Import danach im sys.modules-Cache.
        from interview_theater import befehle

        befehle._befehl_aufnahme(conn, tg, klm, e, chat_id)
        return "Aufnahme umgeschaltet"
    if art == ART_PHASE:
        nummer = int(knopf["wert"])
        if phasen.setze(conn, chat_id, nummer, "knopf"):
            tg.sende(chat_id, phasen.meldung(nummer))
        return f"Phase {nummer}"
    if art == ART_FORMAT:
        # Wortgleich das, was /stueck format tut (befehle._befehl_stueck):
        # dasselbe Feld, derselbe Schreibweg. Kein zweiter Mechanismus --
        # sonst gaebe es zwei Stellen, an denen 'format' entsteht.
        repo.setze_arbeitsstand(conn, chat_id, "format", knopf["wert"])
        repo.schreibe_journal(
            conn, chat_id, "entschieden", f"Format: {knopf['wert']}", quelle="knopf",
        )
        tg.sende(chat_id, f"Format notiert: {knopf['wert']}")
        return "Format uebernommen"
    if art == ART_SZENENFORM:
        # Der wert traegt Nummer UND Form ("3:dialog") -- siehe
        # biete_szenenform. Getrennt wird am ERSTEN ':', damit ein spaeter
        # erweiterter Formname mit ':' nicht die Nummer zerlegt.
        roh_nummer, _, form = str(knopf["wert"]).partition(":")
        nummer = int(roh_nummer)
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.setze_szenenfeld(conn, szene_id, "form", form)
        from interview_theater import szene as szene_modul

        tg.sende(
            chat_id,
            szene_modul.planungszeile(conn, repo.hole_szene(conn, szene_id)),
        )
        return f"Szene {nummer}: {form}"
    if art == ART_SZENE_USA:
        # ACHTUNG, hier ist am 05.09.2026 schon ein Fehler passiert:
        # repo.setze_szene_usa erwartet einen BOOL, nicht den String
        # "ja"/"nein". Ein String ist in Python immer wahr -- ein "nein"
        # haette als Zustimmung zur Datenuebermittlung in die USA geendet,
        # also genau falsch herum bei der einen Entscheidung, bei der das
        # niemand verzeiht. Deshalb der ausdrueckliche Vergleich.
        ja = str(knopf["wert"]).strip().lower() == "ja"
        repo.setze_szene_usa(conn, chat_id, ja)
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            "US-Modell fuer Szenentexte: ja" if ja else "US-Modell fuer Szenentexte: nein",
            quelle="knopf",
        )
        tg.sende(chat_id, _TEXT_USA_JA if ja else _TEXT_USA_NEIN)
        return "US-Modell: ja" if ja else "Bleibt in der Schweiz"
    # Unbekannte art: nur moeglich, wenn eine spaetere Fassung eine Art
    # einfuehrt und eine aeltere die Zeile liest. Nichts tun ist hier richtig.
    log.error("Unbekannte Knopf-art %r, chat_id=%s", art, chat_id)
    return _TEXT_UNBEKANNT


def behandle(conn, tg, klm, e, druck: dict) -> bool:
    """Verarbeitet einen normalisierten Knopfdruck
    (``telegram.lies_knopfdruck``). Liefert True, wenn er zu diesem Bot
    gehoerte und beantwortet wurde.

    Antwortet IMMER mit answerCallbackQuery, auch wenn nichts geschieht --
    ohne diese Antwort dreht sich in der App eine Ladeanzeige weiter, und das
    sieht fuer die Gruppe nach einem haengenden Bot aus.

    Ein Knopf aus einer anderen Gruppe (``knopf.chat_id`` passt nicht) wirkt
    nicht: dieselbe Datenbank traegt alle Gruppen des Workshops, und eine
    weitergeleitete Nachricht darf nie in fremde Daten schreiben."""
    knopf_id = _id_aus_daten(druck["data"])
    if knopf_id is None:
        return False

    chat_id = druck["chat_id"]
    knopf = repo.hole_knopf(conn, knopf_id)
    if knopf is None or (chat_id is not None and knopf["chat_id"] != chat_id):
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_UNBEKANNT)
        return True

    chat_id = knopf["chat_id"]
    if not repo.beanspruche_knopf(conn, knopf_id):
        # Zweiter Druck: beantworten, aber nichts wiederholen (AGENTS.md).
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_SCHON_BENUTZT)
        _entferne_tastatur(tg, chat_id, druck["message_id"])
        return True

    meldung = _wirke(conn, tg, klm, e, knopf, chat_id)
    tg.beantworte_knopf(druck["callback_query_id"], meldung)
    _entferne_tastatur(tg, chat_id, druck["message_id"])
    return True

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
#: Ein Interview jetzt auswerten -- dasselbe Ziel wie ``/auswerten <N>``. Der
#: ``wert`` traegt die ``aufnahme_id`` des Interview-Kopfes, damit der Druck
#: auch dann noch das gemeinte Interview trifft, wenn inzwischen ein weiteres
#: aufgenommen wurde (05.09.2026).
ART_AUSWERTEN = "auswerten"
#: Arbeitsstand zeigen -- dasselbe Ziel wie ``/stand``.
ART_STAND = "stand"
#: Bedienung zeigen -- dasselbe Ziel wie ``/hilfe``.
ART_HILFE = "hilfe"
#: Die Speicher-Leiste unter einem Vorschlag (05.09.2026): "So speichern"
#: schreibt den Wert aus dem Vorschlagsblock (``vorschlag.py``) in den
#: Arbeitsstand -- ueber dieselben Schreibwege wie ``erkenner.wende_an``.
#: Der ``wert`` traegt beides, durch '|' getrennt: "begriffe|Heimat, Arbeit".
#: '|' und nicht ':', weil ein Kernthema regelmaessig einen Doppelpunkt
#: enthaelt ("Ankommen: zwischen zwei Sprachen").
ART_SPEICHERN = "speichern"
#: "Nochmal anders" -- Tastatur weg, ein Satz, KEIN Modellaufruf (Zusage 2).
#: Der ``wert`` traegt die Art, damit die Leiste als Ganzes verfaellt.
ART_ANDERS = "anders"
#: Alle beendeten, aber noch nicht ausgewerteten Interviews nacheinander
#: verdichten -- der Weg aus der Phase-4-Sperre (``phasen.voraussetzungen``).
ART_AUSWERTEN_ALLE = "auswerten_alle"

#: Trennzeichen im ``wert`` der Speicher-Leiste.
TRENNER = "|"

_TEXT_SPEICHERN_KNOPF = "So speichern"
_TEXT_ANDERS_KNOPF = "Nochmal anders"
_TEXT_ANDERS = "Sagt mir, was anders sein soll."
_TEXT_AUSWERTEN_ALLE_KNOPF = "Alle auswerten"
_TEXT_AUSWERTEN_ALLE_LAEUFT = "Ich werte die offenen Interviews aus."
_TEXT_AUSWERTEN_ALLE_NICHTS = "Es ist nichts mehr offen."
#: Die Frage unter dem Weiter-Knopf nach einem Speichern -- eine Frage, kein
#: Wechsel (``phasen.py``: die Phase setzt allein die Gruppe).
_TEXT_WEITER_FRAGE = "Gehen wir weiter?"

#: Was nach dem Speichern in den Chat geht -- die Notiert-Zeile, im selben
#: Wortlaut wie beim Erkenner (``erkenner.baue_meldung``): die Gruppe soll
#: nicht zwei Formen fuer dieselbe Sache lernen.
_NOTIERT = {
    "begriffe": "Begriffe",
    "fragen": "Fragen",
    "kernthema": "Kernthema",
}

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
#: Die drei Knoepfe der Leiste nach einem beendeten Interview (05.09.2026).
_TEXT_AUSWERTEN_KNOPF = "Auswerten"
_TEXT_NAECHSTE_AUFNAHME_KNOPF = "Naechste Aufnahme"
_TEXT_STAND_KNOPF = "Stand zeigen"
_TEXT_HILFE_KNOPF = "Hilfe"
#: Der Knopf zeigt auf ein Interview, das es nicht mehr gibt -- nur moeglich,
#: wenn zwischen Angebot und Druck geloescht wurde (scripts/loeschen.py).
_TEXT_AUSWERTEN_UNBEKANNT = "Dieses Interview kenne ich nicht mehr."
#: Nur erreichbar, wenn ein Aufrufer ``behandle()`` ohne ``klm`` benutzt --
#: ein Programmierfehler, aber einer, der die Gruppe nicht ratlos laesst.
_TEXT_AUSWERTEN_UNMOEGLICH = "Ich kann gerade nicht auswerten."

#: Die Phase, in der es ueberhaupt etwas aufzunehmen gibt (``phasen.PHASEN``:
#: "3 · Interviews"). Davor wird gearbeitet, nicht aufgenommen: in Phase 1
#: kommt die im Plenum gesammelte Begriffsliste zum Bot, in Phase 2 werden im
#: Gespraech die Fragen entwickelt -- fuer beides gibt es kein Mikrofon.
#:
#: Anlass (05.09.2026, Birk im laufenden Workshop): "aber direkt schon mit
#: aufnahme starten? nach der begruessung kommt erst die eingabe der begriffe
#: und damit die fragen zu erstellen. hast du die reihenfolge der phasen
#: beachtet?" -- die Einstiegsleiste bot "Aufnahme starten" phasenblind an,
#: als erste und damit naheliegendste Handlung, und schickte die Gruppe zwei
#: Arbeitsschritte zu weit.
PHASE_INTERVIEWS = 3

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


def biete_aufnahme(conn, tg, chat_id: int, text: str) -> int:
    """Haengt den Aufnahme-Umschalter unter ``text``; liefert die
    ``message_id`` der Angebotsnachricht.

    Die message_id wird zurueckgegeben, weil der Erkenner-Pfad
    (``erkenner._melde_interviewmodus``) seine Bestaetigung wie jede andere
    Bot-Nachricht mitschreibt (``repo.merke_nachricht``) und dafuer die id
    braucht -- vorher stand dort ein ``tg.sende``, das sie ohnehin lieferte.

    Die Beschriftung richtet sich nach dem Zustand JETZT: laeuft eine
    Aufnahme, heisst der Knopf "Aufnahme beenden", sonst "Aufnahme starten".
    Die Wirkung ist beide Male dieselbe wie ``/aufnahme`` -- ein Umschalter,
    kein Ein- und ein Ausschalter (befehle._befehl_aufnahme): sonst gaebe es
    zwei Zustaende und drei Bedienelemente, und genau daran ist die
    gesprochene Variante am 05.09.2026 gescheitert."""
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = _TEXT_AUFNAHME_BEENDEN if laeuft else _TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    return tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = f"Weiter zu {phasen.bezeichnung(nummer)}"
    tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def _phasenknopf(conn, chat_id: int) -> tuple[str, str] | None:
    """Der Knopf "Weiter zu Phase N", wenn die Materiallage eine hoehere
    Stufe hergibt -- sonst None (``phasen.naechste_moegliche``, reine
    Leseabfrage).

    Die Sperre fuer Phase 4 steckt in ``phasen.voraussetzungen``, nicht
    hier: solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    ``naechste_moegliche`` die 4 gar nicht erst her -- an allen drei Stellen
    zugleich (diese Funktion, ``biete_nach_aufnahme``,
    ``kontext._baue_phasenhinweis``)."""
    nummer = phasen.naechste_moegliche(conn, chat_id)
    if nummer is None:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    return (f"Weiter zu {phasen.bezeichnung(nummer)}", _daten(knopf_id))


def _auswerten_alle_knopf(conn, chat_id: int, ausser: int | None = None) -> tuple[str, str] | None:
    """"Alle auswerten", solange ein beendetes Interview ohne Verdichtung
    offen ist -- sonst None.

    Das Gegenstueck zur Phase-4-Sperre: wo "Weiter zu Phase 4" wegfaellt,
    soll nicht einfach nichts stehen, sondern der Weg dorthin.

    ``ausser`` nimmt das Interview aus, fuer das schon ein eigener
    "Auswerten"-Knopf danebensteht (``biete_nach_aufnahme``): zwei Knoepfe
    fuer dieselbe eine Auswertung waeren keine Auswahl, sondern eine
    Verdopplung -- die Gruppe steht im Raum und trifft den ersten."""
    from interview_theater import aufnahme

    offen = [
        kopf for kopf in aufnahme.unausgewertete_interviews(conn, chat_id)
        if kopf["id"] != ausser
    ]
    if not offen:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN_ALLE, None)
    return (_TEXT_AUSWERTEN_ALLE_KNOPF, _daten(knopf_id))


def _nimm_alte_leiste_ab(conn, tg, chat_id: int, art: str) -> None:
    """Nimmt die Tastatur einer aelteren, ungedrueckten Speicher-Leiste
    derselben Art ab, bevor eine neue kommt.

    Warum: der Wert steckt im Knopf, nicht im Text. Nach drei Vorschlaegen
    staenden sonst drei Leisten im Chat, und ein Druck auf die von vor zwei
    Nachrichten speicherte den ueberholten Vorschlag -- genau die Sorte
    stiller Fehler, gegen die die Knoepfe angetreten sind. Die alten
    Knopfzeilen werden zusaetzlich als benutzt gestempelt
    (``repo.verfallen_lassen``), damit sie auch dann nicht mehr wirken, wenn
    die App die Tastatur noch einen Moment zeigt."""
    alte = repo.offene_knoepfe(conn, chat_id, art)
    if not alte:
        return
    repo.verfallen_lassen(conn, [k["id"] for k in alte])
    for message_id in dict.fromkeys(k["message_id"] for k in alte):
        _entferne_tastatur(tg, chat_id, message_id)


def speicherleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die zwei Knoepfe unter einem Vorschlag: "So speichern" · "Nochmal
    anders" (05.09.2026).

    ``wert`` ist der Text aus dem Vorschlagsblock (``vorschlag.lies``) --
    exakt der, der beim Druck gespeichert wird. Nichts wird hier
    umformuliert, gekuerzt oder ergaenzt: was die Gruppe im Chat liest, ist
    was in der Datenbank landet.

    Der Volltext steht in der Tabelle ``knopf``, nie in ``callback_data``
    (Zusage 1 im Moduldocstring) -- eine Begriffsliste sprengt die 64 Bytes
    muehelos."""
    speichern = repo.lege_knopf_an(
        conn, chat_id, ART_SPEICHERN, f"{art}{TRENNER}{wert}"
    )
    anders = repo.lege_knopf_an(conn, chat_id, ART_ANDERS, art)
    return [
        (_TEXT_SPEICHERN_KNOPF, _daten(speichern)),
        (_TEXT_ANDERS_KNOPF, _daten(anders)),
    ]


def sende_mit_speicherleiste(conn, tg, chat_id: int, text: str) -> tuple[int, bool]:
    """Schickt eine Bot-Antwort und haengt -- wenn beides zutrifft -- die
    Speicher-Leiste darunter (05.09.2026). Liefert ``(message_id, leiste?)``.

    Zwei Bedingungen, beide noetig:

    1. Es fehlt gerade etwas, das ueber die Leiste gespeichert werden kann
       (``offene_art``: Begriffe in Phase 1, Fragen in 2, Kernthema/Figuren
       in 4).
    2. Der Antworttext enthaelt einen **Vorschlagsblock** dieser Art
       (``vorschlag.lies``). Fehlt er, gibt es keine Leiste -- **kein
       Raten**: lieber keine Knoepfe als zwei, die den falschen Text
       speichern.

    Die Markerzeilen selbst gehen nie in den Chat (``vorschlag.ohne_marker``);
    sie sind Technik zwischen Prompt und Code, kein Inhalt fuer die Gruppe.

    Der Text ist auch ohne Leiste immer derselbe -- das ist wichtig: die
    Gruppe soll nicht daran, ob Knoepfe darunter stehen, ablesen muessen, ob
    das Modell die Form eingehalten hat."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(text) or text
    art = offene_art(conn, chat_id)
    wert = vorschlag.lies(text, art) if art else None
    if not art or not wert:
        return tg.sende(chat_id, sauber), False

    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    leiste = speicherleiste(conn, chat_id, art, wert)
    message_id = tg.sende_mit_knoepfen(chat_id, sauber, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


def offene_art(conn, chat_id: int) -> str | None:
    """Welche Art gerade noch fehlt und deshalb eine Speicher-Leiste
    verdient -- oder None.

    Die Reihenfolge ist die der Arbeit, nicht die des Alphabets, und sie
    haengt an der **Phase**, damit in Phase 1 nicht ploetzlich nach Figuren
    gefragt wird:

    * Phase 1 -- ``begriffe``, solange das Feld leer ist.
    * Phase 2 -- ``fragen``, solange das Feld leer ist.
    * Phase 4 -- ``kernthema``, solange es keins gibt; danach ``figuren``,
      solange es weniger als zwei gibt (dieselbe Schwelle wie
      ``phasen.voraussetzungen[5]``: ein Stueck braucht zwei Wollen).

    Steht der Wert, gibt es keine Leiste mehr -- **das** ist der Mechanismus
    hinter "die Leiste kommt nach jeder Aenderung wieder": speichert weder
    Knopf noch Erkenner, bleibt das Feld leer, und die naechste Bot-Antwort
    mit einem Vorschlagsblock traegt sie erneut."""
    phase = phasen.aktuelle(conn, chat_id)
    stand = repo.hole_arbeitsstand(conn, chat_id)

    def leer(feld: str) -> bool:
        return not (stand and (stand[feld] or "").strip())

    if phase == 1:
        return "begriffe" if leer("begriffe") else None
    if phase == 2:
        return "fragen" if leer("fragen") else None
    if phase == 4:
        if leer("kernthema"):
            return "kernthema"
        if len(repo.figuren(conn, chat_id)) < 2:
            return "figuren"
    return None


def _aufnahme_anbieten(conn, chat_id: int, nur_phase_3: bool = False) -> bool:
    """Darf eine Knopfleiste von sich aus eine Aufnahme ANBIETEN?

    Ja ab ``PHASE_INTERVIEWS`` -- und ja, solange eine Aufnahme laeuft, egal
    in welcher Phase: dann heisst der Knopf "Aufnahme beenden", und ein
    laufendes Interview ohne Ausschalter waere die schlechtere Falle als ein
    Angebot zur falschen Zeit.

    Nein in Phase 1 (Begriffe) und 2 (Fragen). Mit ``nur_phase_3`` auch nein
    ab Phase 4: das ist die Leiste NACH einem Interview
    (``biete_nach_aufnahme``) -- hat die Gruppe inzwischen zum Kernthema
    weitergeschaltet, ist "Naechste Aufnahme" dort kein Angebot mehr, sondern
    ein Rueckschritt. In der Einstiegsleiste bleibt der Knopf dagegen auch
    spaeter stehen: nachtraeglich ein Interview zu ergaenzen ist ein normaler
    Vorgang, nur eben keiner, den der Bot vorschlaegt.

    Das ist ausdruecklich nur eine Regel fuer die ANGEBOTE: ``/aufnahme`` und
    der Erkenner-Pfad (``biete_aufnahme``) bleiben phasenunabhaengig, die
    Gruppe darf jederzeit ausdruecklich aufnehmen (AGENTS.md, "Fokus, kein
    Kaefig"). Nur das unaufgeforderte Angebot richtet sich nach der
    Reihenfolge der Phasen."""
    if repo.ist_interviewmodus_an(conn, chat_id):
        return True
    jetzige = phasen.aktuelle(conn, chat_id)
    if nur_phase_3:
        return jetzige == PHASE_INTERVIEWS
    return jetzige >= PHASE_INTERVIEWS


def biete_nach_aufnahme(conn, tg, chat_id: int, text: str, kopf_id: int | None) -> int:
    """Die Knopfleiste nach einem beendeten Interview (05.09.2026, Birk:
    "ersetze am besten alle slash befehl vorschlaege mit knoepfen. und gib
    auch immer sinnvolle alternativvorschlaege").

    Der gemessene Fall (Gruppe 2, 13:59): ein Interview unter
    ``aufnahme.MINDEST_WOERTER`` endete mit einem Text, der ``/auswerten``
    empfahl; die Gruppe fragte zweimal nach, und ausgewertet wurde nie. Der
    Grund ist derselbe wie ueberall hier: ein empfohlener Slash-Befehl ist
    eine Bedienungsanleitung, ein Knopf ist der Weg.

    Drei Knoepfe, in dieser Reihenfolge -- der wahrscheinlichste zuletzt ist
    hier falsch, weil die Gruppe im Raum steht und den ersten trifft:

    * **Auswerten** -- die Verdichtung dieses Interviews in den Chat. Liegt
      sie schon vor (der Normalfall: verdichtet wird sofort, ausgespielt
      erst auf Wunsch), wird sie aus der Datenbank ausgespielt; liegt keine
      vor (Interview unter der Mindestlaenge), laeuft wortgleich das, was
      ``/auswerten`` tut. Faellt nur weg, wenn es gar kein Interview gibt
      (``kopf_id`` ist None).
    * **Naechste Aufnahme** -- derselbe Umschalter wie ``/aufnahme``, aber
      nur in Phase 3 (``_aufnahme_anbieten(nur_phase_3=True)``): ist die
      Gruppe schon weiter, waere es ein Rueckschritt statt eines Angebots.
    * **Weiter zu Phase N** -- nur, wenn ``phasen.naechste_moegliche`` es
      hergibt. Das ist die Alternative, die im Live-Fall gefehlt hat: statt
      direkt das naechste Interview zu starten, haette die Gruppe auch in die
      Auswertung gehen koennen.

    Kein Modellaufruf, alles aus der Datenbank -- wie jedes Angebot hier.
    Liefert die ``message_id`` der Angebotsnachricht."""
    knoepfe: list[tuple[str, str]] = []
    if kopf_id is not None:
        # Auch wenn schon verdichtet wurde: seit 05.09.2026 geht die
        # Verdichtung NICHT mehr von selbst in den Chat -- der Knopf ist der
        # Weg, sie zu sehen (``aufnahme.zeige_verdichtung``), nicht nur der
        # Weg, sie nachtraeglich zu erzwingen.
        knoepfe.append(
            (
                _TEXT_AUSWERTEN_KNOPF,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN, str(kopf_id))),
            )
        )
    # "Naechste Aufnahme" statt "Aufnahme starten": nach einem beendeten
    # Interview ist genau das gemeint, und der Wortlaut sagt es. Laeuft wider
    # Erwarten schon wieder eine Aufnahme (ein Knopf aus einer alten
    # Nachricht), heisst er wie ueberall "Aufnahme beenden" -- die Wirkung ist
    # in beiden Faellen der Umschalter aus ``/aufnahme``.
    #
    # Seit 05.09.2026 nur noch, wenn die Phase es hergibt
    # (``_aufnahme_anbieten``): ist die Gruppe waehrend des Interviews schon
    # auf 4 (Kernthema & Figuren) weitergegangen, ist "Naechste Aufnahme"
    # kein Angebot mehr, sondern ein Rueckschritt. "Auswerten" und "Weiter zu
    # Phase N" bleiben davon unberuehrt.
    if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
        knoepfe.append(
            (
                _TEXT_NAECHSTE_AUFNAHME_KNOPF
                if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    # Solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    # ``phasen.naechste_moegliche`` die 4 nicht her (Phase-4-Sperre) -- an
    # ihre Stelle tritt der Weg dorthin: alle offenen auswerten.
    alle = _auswerten_alle_knopf(conn, chat_id, ausser=kopf_id)
    if alle is not None:
        knoepfe.append(alle)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        knoepfe.append(phasenknopf)
    return tg.sende_mit_knoepfen(chat_id, text, knoepfe)


def biete_einstieg(conn, tg, chat_id: int, text: str) -> int:
    """Die Knopfleiste unter einer Begruessung (Erstkontakt, Wiederkehr):
    "Stand zeigen", "Hilfe" -- und, wenn die Materiallage es hergibt,
    "Weiter zu Phase N".

    "Aufnahme starten" steht seit 05.09.2026 nur noch davor, wenn die Phase
    es hergibt (``_aufnahme_anbieten``): ab Phase 3 (Interviews) oder solange
    eine Aufnahme laeuft. In Phase 1 (Begriffe) und 2 (Fragen) gibt es nichts
    aufzunehmen -- die Begriffe kommen aus dem Plenum als Text oder
    Sprachnachricht, die Fragen entstehen im Gespraech mit dem Bot. Der erste
    Knopf ist der, den die Gruppe im Raum trifft; er darf nicht zwei
    Arbeitsschritte zu weit zeigen.

    Damit steht in der Begruessung selbst kein Slash-Befehl mehr: der Weg ist
    der Knopf, ``/hilfe`` listet die Befehle weiterhin auf, wenn jemand sie
    sucht."""
    knoepfe: list[tuple[str, str]] = []
    if _aufnahme_anbieten(conn, chat_id):
        knoepfe.append(
            (
                _TEXT_AUFNAHME_STARTEN if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    knoepfe += [
        (
            _TEXT_STAND_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_STAND, None)),
        ),
        (
            _TEXT_HILFE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_HILFE, None)),
        ),
    ]
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        # Direkt hinter der Aufnahme, wenn es sie gibt -- sonst ganz vorn: der
        # Schritt in die naechste Phase ist dann die wahrscheinlichste Absicht.
        knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, phasenknopf)
    else:
        # Kein Phasenknopf, aber offene Auswertungen: dann ist DAS der
        # naechste Schritt (Phase-4-Sperre) -- an derselben Stelle.
        alle = _auswerten_alle_knopf(conn, chat_id)
        if alle is not None:
            knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, alle)
    return tg.sende_mit_knoepfen(chat_id, text, knoepfe)


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


def _speichere(conn, tg, chat_id: int, roh: str) -> str:
    """Schreibt den Wert einer Speicher-Leiste in den Arbeitsstand -- ueber
    **dieselben** ``repo``-Funktionen wie ``erkenner.wende_an``.

    Das ist die ganze Uebung: kein zweiter Schreibweg, kein zweites Feld,
    keine zweite Notiert-Zeile. Der Erkenner-Pfad bleibt daneben bestehen;
    schreibt er zuerst, ist das Feld gesetzt und die Leiste erscheint gar
    nicht mehr (``offene_art``).

    ``roh`` ist ``"<art>|<wert>"`` (siehe ``ART_SPEICHERN``). Getrennt wird
    am ERSTEN '|', damit ein Wert mit '|' darin (eine Frageliste zum
    Beispiel) die Art nicht zerlegt."""
    art, _, wert = roh.partition(TRENNER)
    art = art.strip()
    wert = wert.strip()
    if not art or not wert:
        log.error("Speicher-Knopf ohne Wert, chat_id=%s, roh=%r", chat_id, roh)
        return _TEXT_UNBEKANNT

    if art == "figuren":
        from interview_theater import vorschlag

        angelegt = []
        for name, beschreibung in vorschlag.figuren(wert):
            # Derselbe Schreibweg wie erkenner._wende_figur_an: eine Figur
            # entsteht mit Name und Beschreibung, mehr braucht Phase 4 nicht.
            repo.setze_figur(conn, chat_id, name, beschreibung)
            angelegt.append(name)
        if not angelegt:
            log.error("Figuren-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
            return _TEXT_UNBEKANNT
        repo.schreibe_journal(
            conn, chat_id, "entschieden", f"Figuren: {', '.join(angelegt)}",
            quelle="knopf",
        )
        tg.sende(chat_id, "Notiert:\n" + _figurenzeile(angelegt)
                 + "\nFalls das nicht stimmt, sagt es mir.")
        return "Figuren uebernommen"

    if art not in _NOTIERT:
        log.error("Speicher-Knopf mit unbekannter art %r, chat_id=%s", art, chat_id)
        return _TEXT_UNBEKANNT

    repo.setze_arbeitsstand(conn, chat_id, art, wert)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"{_NOTIERT[art]}: {wert}", quelle="knopf",
    )
    tg.sende(
        chat_id,
        f"Notiert:\n{_NOTIERT[art]}: {wert}\nFalls das nicht stimmt, sagt es mir.",
    )
    # Danach der Weg weiter: mit dem gesetzten Feld gibt die Materiallage
    # eine hoehere Stufe her (``phasen.voraussetzungen``) -- der Knopf sagt
    # es, statt dass jemand raten muss, was jetzt dran ist.
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        tg.sende_mit_knoepfen(chat_id, _TEXT_WEITER_FRAGE, [phasenknopf])
    return f"{_NOTIERT[art]} uebernommen"


def _figurenzeile(namen: list[str]) -> str:
    """Dieselbe Zeile, die der Erkenner baut (``erkenner._figuren_zeile``) --
    von dort geholt statt hier zweitgepflegt: die Gruppe soll nicht zwei
    Formulierungen fuer dasselbe Ereignis sehen."""
    from interview_theater import erkenner

    return erkenner._figuren_zeile(namen)


def _werte_alle_aus(conn, tg, klm, e, chat_id: int) -> str:
    """Wertet ALLE beendeten, noch nicht verdichteten Interviews aus --
    nacheinander, in einem eigenen Thread (Zusage 2: kein Modellaufruf im
    Handler selbst).

    Nacheinander und nicht parallel: Infomaniak drosselt Parallelitaet mit
    429/5xx statt mit einer Warteschlange (AGENTS.md, Falle 8). Jede fertige
    Verdichtung geht von ``aufnahme._interview_abschliessen`` aus in den
    Chat, die Gruppe sieht also den Fortschritt."""
    import threading

    from interview_theater import aufnahme

    offen = aufnahme.unausgewertete_interviews(conn, chat_id)
    if not offen:
        tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_NICHTS)
        return _TEXT_AUSWERTEN_ALLE_NICHTS
    if klm is None:
        log.error("Auswerten-alle ohne Sprachmodell, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
        return _TEXT_AUSWERTEN_UNMOEGLICH

    ids = [kopf["id"] for kopf in offen]
    tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_LAEUFT)

    def _lauf() -> None:
        for kopf_id in ids:
            try:
                aufnahme._auswerten(conn, tg, klm, e, kopf_id)
            except Exception:
                log.exception("Auswertung fehlgeschlagen, aufnahme_id=%s", kopf_id)

    threading.Thread(target=_lauf, daemon=True).start()
    return _TEXT_AUSWERTEN_ALLE_LAEUFT


def _wirke(conn, tg, klm, e, knopf, chat_id: int) -> str:
    """Fuehrt die Wirkung eines beanspruchten Knopfes aus und liefert den
    kurzen Text fuer answerCallbackQuery.

    Wird NUR aufgerufen, wenn ``repo.beanspruche_knopf`` True geliefert hat --
    die Idempotenz haengt an dieser einen Bedingung und nicht daran, dass
    jede Wirkung fuer sich wiederholbar waere."""
    art = knopf["art"]
    if art == ART_SPEICHERN:
        return _speichere(conn, tg, chat_id, str(knopf["wert"] or ""))
    if art == ART_ANDERS:
        # Kein Modellaufruf (Zusage 2): ein Satz, mehr nicht. Die naechste
        # Bot-Antwort traegt die Leiste automatisch wieder, weil der Wert
        # weiterhin leer ist (``offene_art``) -- genau das ist gemeint mit
        # "das Menue kommt nach jeder Aenderung wieder".
        tg.sende(chat_id, _TEXT_ANDERS)
        return "Neuer Vorschlag"
    if art == ART_AUSWERTEN_ALLE:
        return _werte_alle_aus(conn, tg, klm, e, chat_id)
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
    if art == ART_AUSWERTEN:
        # Zwei Faelle, beide deterministisch und ohne Modellaufruf in DIESEM
        # Handler (Zusage 2 im Moduldocstring):
        #
        # 1. Es gibt schon eine Verdichtung (der Normalfall seit 05.09.2026:
        #    verdichtet wird sofort, ausgespielt erst auf Wunsch) -- dann
        #    wird sie hier direkt aus der Datenbank in den Chat gestellt.
        #    Genau das hat im Live-Lauf gefehlt: die Gruppe fragte zweimal
        #    nach der Auswertung und bekam Text statt Inhalt.
        # 2. Es gibt keine (Interview unter ``aufnahme.MINDEST_WOERTER``) --
        #    dann laeuft wortgleich das, was ``/auswerten`` tut:
        #    ``aufnahme.starte_auswertung`` in einem eigenen Thread, und die
        #    fertige Verdichtung geht von dort in den Chat
        #    (``_interview_abschliessen`` mit ``erzwungen=True``).
        from interview_theater import aufnahme

        kopf_id = int(knopf["wert"])
        kopf = repo.hole_aufnahme(conn, kopf_id)
        if kopf is None:
            tg.sende(chat_id, _TEXT_AUSWERTEN_UNBEKANNT)
            return _TEXT_AUSWERTEN_UNBEKANNT
        name = kopf["name"] or "Das Interview"
        if aufnahme.zeige_verdichtung(conn, tg, e, kopf_id):
            return "Auswertung"
        if klm is None:
            log.error("Auswerten-Knopf ohne Sprachmodell, chat_id=%s", chat_id)
            tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
            return _TEXT_AUSWERTEN_UNMOEGLICH
        tg.sende(chat_id, f"Ich werte {name} aus.")
        aufnahme.starte_auswertung(conn, tg, klm, e, kopf_id)
        return "Auswertung laeuft"
    if art == ART_STAND:
        from interview_theater import befehle

        befehle._befehl_stand(conn, tg, chat_id, e)
        return "Stand"
    if art == ART_HILFE:
        from interview_theater import befehle

        befehle._befehl_hilfe(tg, e, chat_id)
        return "Hilfe"
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

"""Phase 3: die Knoepfe rund um eine Aufnahme.

Der Umschalter (``biete_aufnahme``), die Leiste unter jedem Teil-Transkript
(``biete_nach_teil``), die vier Knoepfe unter einer langen Sprachnachricht
ohne Interviewmodus (``biete_interview_ohne_knopf``), die Leiste nach einem
beendeten Interview (``biete_nach_aufnahme``: Zusammenfassung, Wortlaut,
naechste Aufnahme, Leitfaden, "Weiter zu Phase N") und die
Begruessungsleiste (``biete_einstieg``).

**Angebote sind phasenabhaengig** (``_aufnahme_anbieten``): "Aufnahme starten"
und "Naechste Aufnahme" erscheinen nur in Phase 3 -- in Begriffe und Fragen
gibt es nichts aufzunehmen. Ausdrueckliches Aufnehmen bleibt in jeder Phase
moeglich; eingeschraenkt ist nur das Angebot.
"""

from interview_theater import phasen, repo, sprache

from interview_theater.knoepfe.texte import (
    ART_AUFNAHME, ART_AUSWERTEN, ART_AUSWERTEN_ALLE, ART_HILFE,
    ART_INTERVIEWS_FERTIG, ART_OHNE_KNOPF_FERTIG, ART_OHNE_KNOPF_JA,
    ART_OHNE_KNOPF_NEIN, ART_OHNE_KNOPF_WEITER, ART_STAND, ART_STT_SPRACHE,
    ART_TEIL_FERTIG, ART_TEIL_WEITER, ART_TRANSKRIPT, ART_ZUSAMMENFASSUNG,
    PHASE_INTERVIEWS, STT_KNOEPFE, T, log,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _nimm_alte_leiste_ab, _phasenknopf, _sende_knoepfe,
)
from interview_theater.knoepfe.fragen import (
    _leitfaden_knopf,
)


def biete_stt_sprache(conn, tg, chat_id: int) -> bool:
    """Drei Knoepfe fuer die Interviewsprache (Karte A1, D2): Auto, English,
    Italiano. Eine feste, benannte Auswahl -- genau der Fall, fuer den es
    Knoepfe gibt. Nur, wenn das Profil Whisper selbst erkennen laesst
    (``sprache.whisper = "auto"``); Dortmund sieht sie nie.

    Kein Modellaufruf (Zusage 2). Liefert True, wenn die Leiste rausging."""
    if sprache.whisper_vorgabe() != sprache.AUTO:
        return False
    leiste = [
        (beschriftung, _daten(repo.lege_knopf_an(conn, chat_id, ART_STT_SPRACHE, wert)))
        for wert, beschriftung in STT_KNOEPFE
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, T._TEXT_STT_SPRACHE_FRAGE, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return True


def biete_aufnahme(conn, tg, chat_id: int, text: str, knopf: bool = True) -> int:
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
    gesprochene Variante am 05.09.2026 gescheitert.

    ``knopf=False`` schickt denselben Text OHNE Tastatur (05.09.2026,
    Live-Fall Gruppe 1, 14:21): unter der Startbestaetigung ("Aufnahme
    laeuft ...") hing bis dahin sofort "Aufnahme beenden" -- sieben Sekunden
    spaeter war er gedrueckt, und es entstand ein leeres Interview. Die
    Beenden-Moeglichkeit kommt seitdem erst mit dem ersten Teil-Transkript
    (``biete_nach_teil``), also dann, wenn es ueberhaupt etwas zu beenden
    gibt."""
    if not knopf:
        return tg.sende(chat_id, text)
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = T._TEXT_AUFNAHME_BEENDEN if laeuft else T._TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    return _sende_knoepfe(conn, tg, chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_nach_teil(conn, tg, chat_id: int, text: str) -> int:
    """Die Leiste unter einem Teil-Transkript: "Interview geht weiter" ·
    "Interview ist fertig" (05.09.2026, Birk nach dem Live-Lauf Gruppe 1).

    Der gemessene Fall: nach dem Echo "Interview 4, Teil 1: ..." stand das
    Transkript einfach da. Die Gruppe im Raum konnte nicht sehen, ob der Bot
    weiter aufnimmt oder ob das Interview zu Ende ist -- Birk: "das sollte
    aktiv als naechste Antwort angeboten werden nach dem Transkript, nicht
    mit Transkript einfach so stehen lassen."

    Zwei Knoepfe, beide ohne Modellaufruf: "geht weiter" nimmt nur die
    Tastatur ab und sagt einen Satz, "ist fertig" ist wortgleich derselbe
    Weg wie "Aufnahme beenden" (``befehle._befehl_aufnahme``).

    Ein neues Echo nimmt der vorherigen Leiste die Tastatur ab
    (``_nimm_alte_leiste_ab``): sonst staenden nach fuenf Sprachnachrichten
    fuenf Leisten im Chat, und ein Druck auf die von vor drei Nachrichten
    beendete das Interview, ohne dass jemand das gemeint haette.

    Liefert die ``message_id`` der Echo-Nachricht."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_WEITER)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_FERTIG)
    leiste = [
        (
            T._TEXT_TEIL_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_WEITER, None)),
        ),
        (
            T._TEXT_TEIL_FERTIG_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_FERTIG, None)),
        ),
    ]
    # **Hier NICHT ueber ``_sende_knoepfe``**: der Text ist ein
    # Teil-Transkript, und das schreibt ``aufnahme.py`` selbst mit
    # ``typ='transkript'`` mit -- sonst laege Interviewinhalt als
    # Gruppenbeitrag im Erkenner-Fenster (§ 10.6).
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def biete_interview_ohne_knopf(
    conn, tg, chat_id: int, text: str, aufnahme_id: int
) -> int:
    """Die zwei Knoepfe unter \"Das klingt nach einem Interview (M:SS)\":
    \"Ja, als Interview\" · \"Nein, war ein Beitrag\" (06.09.2026, Live-Fall
    Gruppe 1 13:32).

    Die Knopfregel ist erfuellt (AGENTS.md): es gibt etwas Fixes zu
    speichern, naemlich diese eine Aufnahme, und genau zwei benannte
    Moeglichkeiten. Die ``aufnahme.id`` steht im ``wert`` der Knopfzeile, nie
    in ``callback_data`` (Zusage 1).

    Eine aeltere, ungedrueckte Leiste derselben Art wird abgenommen: schickt
    eine Gruppe zwei lange Sprachnachrichten hintereinander, soll der Druck
    nicht die vorletzte treffen.

    Liefert die ``message_id`` der Frage."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_OHNE_KNOPF_JA)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_OHNE_KNOPF_NEIN)
    wert = str(aufnahme_id)
    leiste = [
        (
            T._TEXT_OHNE_KNOPF_JA_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_JA, wert)),
        ),
        (
            T._TEXT_OHNE_KNOPF_NEIN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_NEIN, wert)),
        ),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def biete_interview_ohne_knopf_weiter(conn, tg, chat_id: int, text: str, kopf_id: int) -> int:
    """Die Folgefrage nach \"Ja, als Interview\": \"Fertig, auswerten\" ·
    \"Es kommt noch was\" (06.09.2026).

    Ohne sie waere die Gruppe im Interviewmodus, ohne es entschieden zu
    haben -- und der Kopf bliebe offen, bis jemand zufaellig \"Interview
    beenden\" findet. Der ``wert`` traegt die Kopf-id, damit \"Fertig\" genau
    dieses Interview abschliesst."""
    wert = str(kopf_id)
    leiste = [
        (
            T._TEXT_OHNE_KNOPF_FERTIG_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_FERTIG, wert)),
        ),
        (
            T._TEXT_OHNE_KNOPF_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_OHNE_KNOPF_WEITER, wert)),
        ),
    ]
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


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
    return (T._TEXT_AUSWERTEN_ALLE_KNOPF, _daten(knopf_id))


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
    # Die Regel selbst steht in ``phasen.aufnahme_anbieten``: die
    # Web-Fussleiste (``web_daten.web_chatzustand``) fragt dieselbe.
    return phasen.aufnahme_anbieten(phasen.aktuelle(conn, chat_id), False, nur_phase_3)


def _interviewknoepfe(conn, chat_id: int, kopf_id: int) -> list[tuple[str, str]]:
    """Die beiden Knoepfe, die an EINEM beendeten Interview haengen:
    Zusammenfassung (oder "Trotzdem auswerten") und Wortlaut.

    **Kein "Auswerten" mehr** (06.09.2026, Birk 09:55): verdichtet wird seit
    dem 05.09. ohnehin sofort, und der Knopf hiess nach einer Handlung, die
    schon passiert war. An seiner Stelle stehen die beiden Wege, die die Gruppe
    wirklich braucht -- die Zusammenfassung lesen und den Wortlaut
    gegenpruefen. Die art ``ART_AUSWERTEN`` bleibt im Code: sie traegt weiter
    den Sonderfall unter ``aufnahme.MINDEST_WOERTER`` ("Trotzdem
    auswerten")."""
    if repo.verdichtung_zu_aufnahme(conn, kopf_id) is not None:
        erster = (
            T._TEXT_ZUSAMMENFASSUNG_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_ZUSAMMENFASSUNG, str(kopf_id))
            ),
        )
    else:
        # Unter der Mindestlaenge: hier gibt es nichts zu zeigen, nur
        # etwas zu erzwingen.
        erster = (
            T._TEXT_TROTZDEM_AUSWERTEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN, str(kopf_id))),
        )
    return [
        erster,
        (
            T._TEXT_TRANSKRIPT_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TRANSKRIPT, str(kopf_id))),
        ),
    ]


def biete_nach_aufnahme(conn, tg, chat_id: int, text: str, kopf_id: int | None,
                        system: bool = False) -> int:
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
    Liefert die ``message_id`` der Angebotsnachricht.

    Auf dem Web-Kanal entfaellt diese ganze Telegram-Leiste (06.10.2026,
    Phase 3 Web-UX) -- an ihre Stelle tritt EIN Knopf, "Interviews fertig"
    (02.10.2026): sobald mindestens ein Interview existiert und die Gruppe
    noch in Phase 3 steht. Seine Wirkung (``wirkung._wirkung_interviews_fertig``)
    schliesst direkt nach Phase 4 weiter, wenn alle Interviews verdichtet
    sind, oder merkt den Wunsch fuers naechste Mal
    (``arbeitsstand.interviews_fertig_wunsch_seit``). Die Web-Sperre betrifft
    **nur die Leiste** -- der Merkposten ``phase_angeboten`` wird unten
    unabhaengig vom Kanal abgeraeumt (Review-Fix: eine fruehere Fassung liess
    ihn mit einem fruehen ``return`` auf dem Web-Kanal stehen, und das
    proaktive "Weiter zu Phase N?" waere dort nach dem ersten Angebot nie
    wieder gekommen).

    ``system=True`` (Karte t_ea994c7f, nur mit ``aufnahme.fliesstext_aktiv``):
    die Zeile geht als Systemzeile raus, die Leiste haengt unveraendert
    darunter."""
    from interview_theater import aufnahme as aufnahme_modul  # lokal: Oberflaeche darf Fachlogik lesen

    ist_web = aufnahme_modul.ist_web_gruppe(conn, chat_id)

    knoepfe: list[tuple[str, str]] = []
    if not ist_web:
        if kopf_id is not None:
            knoepfe.extend(_interviewknoepfe(conn, chat_id, kopf_id))
        # "Naechste Aufnahme" statt "Aufnahme starten": nach einem beendeten
        # Interview ist genau das gemeint, und der Wortlaut sagt es. Laeuft
        # wider Erwarten schon wieder eine Aufnahme (ein Knopf aus einer
        # alten Nachricht), heisst er wie ueberall "Aufnahme beenden" -- die
        # Wirkung ist in beiden Faellen der Umschalter aus ``/aufnahme``.
        #
        # Seit 05.09.2026 nur noch, wenn die Phase es hergibt
        # (``_aufnahme_anbieten``): ist die Gruppe waehrend des Interviews
        # schon auf 4 (Kernthema & Figuren) weitergegangen, ist "Naechste
        # Aufnahme" kein Angebot mehr, sondern ein Rueckschritt. "Auswerten"
        # und "Weiter zu Phase N" bleiben davon unberuehrt.
        if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
            knoepfe.append(
                (
                    T._TEXT_NAECHSTE_AUFNAHME_KNOPF
                    if not repo.ist_interviewmodus_an(conn, chat_id)
                    else T._TEXT_AUFNAHME_BEENDEN,
                    _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
                )
            )
        # Solange ein beendetes Interview ohne Verdichtung offen ist, gibt
        # ``phasen.naechste_moegliche`` die 4 nicht her (Phase-4-Sperre) --
        # an ihre Stelle tritt der Weg dorthin: alle offenen auswerten.
        alle = _auswerten_alle_knopf(conn, chat_id, ausser=kopf_id)
        if alle is not None:
            knoepfe.append(alle)
        # Der Leitfaden, solange die Gruppe noch Interviews fuehrt: zwischen
        # zwei Gespraechen ist genau der Moment, in dem jemand nachsehen
        # will, wie der Einstieg nochmal ging (06.09.2026).
        if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
            leitfadenknopf = _leitfaden_knopf(conn, chat_id)
            if leitfadenknopf is not None:
                knoepfe.append(leitfadenknopf)
    # **Nach JEDER Auswertung kommt das Angebot erneut** (06.09.2026, Birk
    # 10:45). Der Merkposten ``phase_angeboten`` haelt sonst fest, dass die
    # Stufe schon einmal angeboten wurde, und ab dem zweiten Interview stand
    # unter der Auswertung kein Weg mehr nach vorn -- die Gruppe im Raum
    # sah nur noch "Naechstes Interview". Hier wird er deshalb abgeraeumt:
    # das Angebot haengt an der Auswertung, nicht am Merkposten. Gilt auf
    # beiden Kanaelen gleich: der Gespraechs-Prompt bietet die naechste
    # Phase unabhaengig von der hier gezeigten Leiste an.
    if kopf_id is not None and phasen.aktuelle(conn, chat_id) == PHASE_INTERVIEWS:
        phasen.vergiss_angebot(conn, chat_id)
    if ist_web:
        # Der eine Web-Knopf (02.10.2026): nur in Phase 3 und nur, wenn es
        # ueberhaupt schon ein Interview gibt -- vorher gibt es nichts
        # abzuschliessen. Die alte Leiste bleibt leer (Task 2).
        if phasen.aktuelle(conn, chat_id) == PHASE_INTERVIEWS and repo.zaehle_interviews(conn, chat_id) > 0:
            _nimm_alte_leiste_ab(conn, tg, chat_id, ART_INTERVIEWS_FERTIG)
            knopf_id = repo.lege_knopf_an(conn, chat_id, ART_INTERVIEWS_FERTIG, None)
            return _sende_knoepfe(
                conn, tg, chat_id, text,
                [(T._TEXT_INTERVIEWS_FERTIG_KNOPF, _daten(knopf_id))],
                system=system,
            )
        return _sende_knoepfe(conn, tg, chat_id, text, [], system=system)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        knoepfe.append(phasenknopf)
    return _sende_knoepfe(conn, tg, chat_id, text, knoepfe, system=system)


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
                T._TEXT_AUFNAHME_STARTEN if not repo.ist_interviewmodus_an(conn, chat_id)
                else T._TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    # Der Leitfaden steht im Einstieg der Phase 3 direkt neben dem Start:
    # wer den Bot in der Pause aufmacht, sucht genau diese zwei Dinge
    # (06.09.2026). In anderen Phasen waere er ein Angebot ins Leere.
    if phasen.aktuelle(conn, chat_id) == PHASE_INTERVIEWS:
        leitfadenknopf = _leitfaden_knopf(conn, chat_id)
        if leitfadenknopf is not None:
            knoepfe.append(leitfadenknopf)
    knoepfe += [
        (
            T._TEXT_STAND_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_STAND, None)),
        ),
        (
            T._TEXT_HILFE_KNOPF,
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
        #
        # Auf dem Web-Kanal entfaellt dieser Knopf wie jeder andere alte
        # Telegram-Interviewknopf (06.10.2026, Phase 3 Web-UX) -- der Handler
        # (ART_AUSWERTEN_ALLE) bleibt unveraendert, nur das Angebot hier.
        from interview_theater import aufnahme as aufnahme_modul  # lokal: Oberflaeche darf Fachlogik lesen

        if not aufnahme_modul.ist_web_gruppe(conn, chat_id):
            alle = _auswerten_alle_knopf(conn, chat_id)
            if alle is not None:
                knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, alle)
    return _sende_knoepfe(conn, tg, chat_id, text, knoepfe)


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
        tg.sende(chat_id, T._TEXT_AUSWERTEN_ALLE_NICHTS)
        return T._TEXT_AUSWERTEN_ALLE_NICHTS
    if klm is None:
        log.error("Auswerten-alle ohne Sprachmodell, chat_id=%s", chat_id)
        tg.sende(chat_id, T._TEXT_AUSWERTEN_UNMOEGLICH)
        return T._TEXT_AUSWERTEN_UNMOEGLICH

    ids = [kopf["id"] for kopf in offen]
    tg.sende(chat_id, T._TEXT_AUSWERTEN_ALLE_LAEUFT)

    def _lauf() -> None:
        for kopf_id in ids:
            try:
                aufnahme._auswerten(conn, tg, klm, e, kopf_id)
            except Exception:
                log.exception("Auswertung fehlgeschlagen, aufnahme_id=%s", kopf_id)

    threading.Thread(target=_lauf, daemon=True).start()
    return T._TEXT_AUSWERTEN_ALLE_LAEUFT

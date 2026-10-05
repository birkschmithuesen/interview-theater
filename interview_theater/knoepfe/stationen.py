"""Der Phasenrahmen im Chat: Eintritt, Abschluss, proaktives Angebot.

Jede Phase hat denselben Rahmen (06.09.2026, Birk): Eintritt ueber EINEN Weg
(``eintritt_in_phase`` -- Knopf, ``/phase``, Erkenner, proaktive Meldung) mit
der deterministischen Nachricht aus ``phasentexte``, Abschluss ueber
``biete_phase_proaktiv`` mit allen gesetzten Parametern und "Weiter zu
<Phase>" - "Noch etwas aendern", **einmal** je Stufe (Merkposten
``arbeitsstand.phase_angeboten``).

Der Knopf "Weiter zu Phase N" selbst steht eine Schicht tiefer
(``basis._phasenknopf``): ihn haengen auch die Aufnahme- und Szenen-Leisten
unter ihre Nachrichten.
"""

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ART_NOCH_NICHT, ART_PHASE, ART_SPEICHERN, PHASE_INTERVIEWS, PHASE_SCHAERFUNG,
    PHASE_SETTING, PHASE_STUECKPRUEFUNG, PHASE_SZENEN, T,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten, _sende_knoepfe, _starte_auftrag,
)

#: Begriffe -- die Phase, deren Einstieg ein Gespraechszug ist, kein Festtext.
PHASE_BEGRIFFE = 1
#: Fragen -- die Phase, die unter dem Profilschalter ``fragen_ab.aktiv`` den
#: isolierten KI-Fragen-Hintergrundlauf anstoesst (Aufgabe 12, Padua Phase
#: 1+2 Umbau, 03.10.2026).
PHASE_FRAGEN = 2
from interview_theater.knoepfe.interviews import biete_stt_sprache
from interview_theater.knoepfe.szenen import (
    biete_durchlauf, biete_kurzgeschichte, biete_szene_usa, starte_schaerfung,
    starte_stueckpruefung,
)


def uebergang_nach_speichern(conn, tg, klm, e, chat_id: int) -> bool:
    """Direkter Phasenwechsel nach "Ja, speichern" (02.10.2026, Birk, Padua):
    Feld fixiert, dann dieselbe Wirkung wie der Knopf "Weiter zu ..."
    (``_wirkung_phase``) -- Meldung + Eintritt. Liefert False, wenn die
    Materiallage noch keine naechste Phase hergibt; dann bleibt alles beim
    Alten."""
    nummer = phasen.naechste_moegliche(conn, chat_id)
    if nummer is None:
        return False
    phasen.merke_angebot(conn, chat_id, nummer)
    if phasen.setze(conn, chat_id, nummer, "knopf"):
        tg.sende(chat_id, phasen.meldung(nummer))
    eintritt_in_phase(conn, tg, klm, e, chat_id, nummer)
    return True


def schliesse_interviews_ab(conn, tg, klm, e, chat_id: int) -> bool:
    """Phase 4, wenn die Materiallage es hergibt (alle Interviews verdichtet)
    -- sonst False, ohne etwas zu senden. Teilt sich zwischen dem Knopf
    "Interviews fertig" (``_wirkung_interviews_fertig``) und dem
    Auto-Uebergang nach der letzten Verdichtung im Web-Kanal
    (``aufnahme._interview_abschliessen``), damit beide Wege dieselbe eine
    Nachrichtenfolge erzeugen (02.10.2026)."""
    if uebergang_nach_speichern(conn, tg, klm, e, chat_id):
        tg.sende(chat_id, T._TEXT_ARBEITSSTAND_HINWEIS)
        return True
    return False


def _speicherleiste_offen(conn, chat_id: int) -> bool:
    """Steht in dieser Phase eine ungedrueckte "Ja, speichern"-Leiste? Dann
    traegt ihr Ja den Phasenwechsel (``uebergang_nach_speichern``), und ein
    zweites Angebot "Weiter zu ... / Noch etwas aendern" waere doppelt
    (02.10.2026, Birk: beide Knoepfe gestrichen)."""
    seit = repo.hole_phase_gesetzt_am(conn, chat_id) or ""
    return any(
        (k["erstellt_am"] or "") >= seit
        for k in repo.offene_knoepfe(conn, chat_id, ART_SPEICHERN)
    )


#: Die zwei Uebergaenge, die Padua selbst vollzieht -- (aktuelle Phase,
#: angebotene Stufe) -> Profilschalter (Abschlussreview, Fix 2).
_EIGENE_SPRUENGE = {
    (5, 6): "prosa_entwurf_aktiv",
    (6, 7): "ueberarbeitung_aktiv",
}


def _springt_selbst(conn, chat_id: int, stufe: int) -> bool:
    """Vollzieht die Zustandsmaschine des Profils diesen Uebergang selbst?

    Padua springt von 5 nach 6 nach der letzten abgenommenen Prosa-Szene
    (``entwurf.bestaetige_szene``) und von 6 nach 7 nach der letzten
    abgenommenen Ueberarbeitung (``ueberarbeitung.schliesse_6_ab``). Die
    Materiallage (``phasen.voraussetzungen``) gibt die naechste Stufe aber
    schon frueher her -- Prosa je Szene steht in Phase 6 von Anfang an --,
    und das allgemeine Angebot "Phase 6 fertig -- weiter zu 7?" kaeme mitten
    in die Ueberarbeitung. Nur genau diese zwei Uebergaenge und nur mit ihrem
    Schalter; jeder andere (1->2, 3->4, 4->5, ...) und jedes andere Profil
    bleibt unveraendert."""
    from interview_theater import workshop

    schalter = _EIGENE_SPRUENGE.get((phasen.aktuelle(conn, chat_id), stufe))
    return schalter is not None and getattr(workshop, schalter)()


def biete_phase_proaktiv(conn, tg, chat_id: int) -> bool:
    """Die eigene, kurze Nachricht "<Was steht>. Weiter zu <Phase>?" -- genau
    einmal je Stufe, sofort wenn die Voraussetzungen gespeichert sind.

    Liefert ``True``, wenn eine Nachricht rausging.

    **Warum eine eigene Nachricht.** Bis zum 06.09.2026 stand das Angebot nur
    als Prompt-Hinweis (``kontext._baue_phasenhinweis``) und als Knopf am Ende
    einer Gespraechsantwort. Am Testabend wurde keiner der neun angebotenen
    Phasenknoepfe gedrueckt: das Angebot ging im Text unter, und der Bot
    redete danach weiter ueber die alte Phase. Jetzt steht es allein da, mit
    zwei Knoepfen und ohne Fliesstext drumherum.

    **Genau einmal.** Der Merkposten ist derselbe wie fuer den Prompt-Hinweis
    (``phasen.offenes_angebot`` / ``merke_angebot``,
    ``arbeitsstand.phase_angeboten``) -- deshalb verschluckt diese Nachricht
    den Prompt-Hinweis und umgekehrt: es gibt EIN Angebot je Stufe, nicht
    zwei aus zwei Kanaelen. Sagt die Gruppe "Noch nicht", bleibt es still,
    bis die naechste Stufe erreichbar wird.

    Deterministisch, kein Modellaufruf (Zusage 2)."""
    stufe = phasen.offenes_angebot(conn, chat_id)
    if stufe is None or _springt_selbst(conn, chat_id, stufe):
        return False
    if _speicherleiste_offen(conn, chat_id):
        return False
    _sende_abschluss(conn, tg, chat_id, stufe, _abschlusstext(conn, chat_id, stufe))
    return True


def _sende_abschluss(conn, tg, chat_id: int, stufe: int, text: str,
                     korrektur_art: str | None = None, zusatz=()) -> int:
    """Verschickt die Abschlussnachricht mit "Weiter zu Phase N · Titel" und
    dem Korrekturknopf -- und merkt das Angebot (``merke_angebot``).

    Der Korrekturknopf ist immer ``ART_NOCH_NICHT`` ("Noch etwas aendern");
    nennt ``korrektur_art`` das Feld, das gerade gespeichert wurde, heisst er
    danach ("Begriffe aendern" / "Change terms", ``_TEXT_AENDERN_KNOPF_FUER``).
    ``zusatz`` haengt weitere Zeilen darunter -- den Undo-Knopf eines
    Erkennerlaufs (Karte U)."""
    phasen.merke_angebot(conn, chat_id, stufe)
    weiter_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(stufe))
    noch_nicht_id = repo.lege_knopf_an(conn, chat_id, ART_NOCH_NICHT, str(stufe))
    korrektur = T._TEXT_AENDERN_KNOPF_FUER.get(
        korrektur_art or "", T._TEXT_PHASE_NOCH_NICHT_KNOPF)
    leiste = [
        (T._TEXT_WEITER_ZU_KNOPF.format(phase=phasen.bezeichnung(stufe)), _daten(weiter_id)),
        (korrektur, _daten(noch_nicht_id)),
    ] + list(zusatz)
    message_id = _sende_knoepfe(conn, tg, chat_id, text, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id


def sende_abschluss_statt_meldung(conn, tg, chat_id: int, art: str, meldung: str,
                                  nur_dieses_feld: bool = True,
                                  zusatz=()) -> tuple[int, str] | None:
    """EINE Nachricht statt zwei, wenn ein Speichern die Phase sofort
    abschliessbar macht (Padua Hotfix B5, Birk 02.10.2026).

    Der Live-Fall (Web-Kanal, Phase 1): der Erkenner speicherte die
    Begriffsliste und schickte "Noted: Terms ..." mit "Yes, save · No, change
    it again · Undo" -- und SOFORT danach "Phase 1 complete ... On to
    Questions?" mit zwei eigenen Knoepfen. Zwei Auswahlen hintereinander,
    die erste davon ueberholt, bevor jemand sie lesen konnte.

    Die eine Regel, fuer Erkenner (``erkenner._sende_meldung``) und Knopf
    (``basis._speichere``) gleich: ist nach dem Speichern ein Phasenangebot
    faellig (``phasen.offenes_angebot`` -- dieselbe Bedingung, unter der
    ``biete_phase_proaktiv`` gleich danach feuern wuerde), entfaellt die
    Notiert-/Speicherleiste. Die Abschlussnachricht traegt den Inhalt -- sie
    listet die Parameter der Phase (``phasentexte.abschluss``) -- und die
    Knoepfe: "Weiter zu Phase N · Titel", der Korrekturknopf
    ("<Feld> aendern", Wirkung ``ART_NOCH_NICHT``: das Angebot ist
    abgelehnt, und die naechste gespeicherte Aenderung holt genau diese eine
    Nachricht zurueck, ``phasen.erneuere_nach_aenderung``) und ``zusatz``
    (der Undo-Knopf -- er bleibt, Karte U).

    Die Notiert-Zeile ``meldung`` steht trotzdem oben, wenn die
    Abschlussnachricht sie nicht ersetzt: ``nur_dieses_feld`` falsch (der
    Lauf hat mehr geschrieben als dieses eine Feld) oder die Gruppe steht
    schon ueber der Zielstufe (dann gibt es nur das kurze Angebot ohne
    Werteliste, ``_abschlusstext``).

    Liefert ``(message_id, text)`` oder ``None``, wenn kein Angebot faellig
    ist -- dann bleibt alles beim bisherigen Weg. Kein Modellaufruf."""
    stufe = phasen.offenes_angebot(conn, chat_id)
    if stufe is None or _springt_selbst(conn, chat_id, stufe):
        return None
    text = _abschlusstext(conn, chat_id, stufe)
    if not nur_dieses_feld or phasen.aktuelle(conn, chat_id) >= stufe:
        text = f"{meldung}\n\n{text}"
    return _sende_abschluss(conn, tg, chat_id, stufe, text, art, zusatz), text


def _abschlusstext(conn, chat_id: int, stufe: int) -> str:
    """Die Abschlussnachricht der GERADE FERTIGEN Phase plus die Frage nach
    der naechsten (06.09.2026, Birk) -- eine Nachricht, nicht zwei.

    Welche Phase fertig ist, steht nicht in ``stufe``: das ist die Zielphase.
    Fertig ist die, in der die Gruppe gerade steht (``phasen.aktuelle``) --
    und wenn die schon ueber dem Ziel liegt (Rueckkehr aus einer hoeheren
    Phase), gibt es nichts abzuschliessen, dann bleibt es beim alten,
    kurzen Angebot."""
    from interview_theater import phasentexte

    jetzige = phasen.aktuelle(conn, chat_id)
    frage = T._TEXT_PHASE_WEITER.format(phase=phasen.bezeichnung(stufe))
    if jetzige >= stufe:
        return T._TEXT_PHASE_ANGEBOT.format(
            erledigt=T._ERLEDIGT_FUER.get(stufe, T._TEXT_ALLES_NOETIGE),
            phase=phasen.bezeichnung(stufe),
        )
    return f"{phasentexte.abschluss(conn, chat_id, jetzige)}\n\n{frage}"


def biete_proaktiv(conn, tg, chat_id: int, phase: int, vorspann: str | None = None) -> None:
    """Die **offene Frage** beim Eintritt in eine Phase.

    Bis zum 06.09.2026 standen darunter zwei Einstiegsknoepfe -- "Ja, wir
    zuerst" und "Schlag du vor". Sie sind weg (Birk, 11:10): unter einer
    OFFENEN FRAGE gibt es keine Knoepfe, weil dahinter nichts Fixes zu
    speichern ist. Der Bot fragt, die Gruppe antwortet in Sprache; sagt sie
    ausdruecklich "schlag du vor", erkennt das der Erkenner
    (``ART_SCHLAG_VOR`` bleibt als Knopf-Art fuer die Wege bestehen, die ihn
    weiterhin auslegen).

    Deterministischer Systemtext, kein Modellaufruf. ``vorspann`` ist die
    Eintrittsnachricht der Phase (``phasentexte.eintritt``): Kopfzeile,
    Einleitung, Checkliste -- in DERSELBEN Nachricht wie die Frage.

    Eine Ausnahme (Padua Phase 2, Birk 05.10.2026): mit dem A/B-Vergleich
    der Fragen (``workshop.fragen_ab_aktiv``) steht darunter der eine Knopf
    "Suggest questions" -- er erzeugt nichts, er fragt zuerst nach eigenen
    Fragen (``fragen.frage_nach_eigenen``)."""
    from interview_theater import workshop

    if phase == PHASE_FRAGEN and workshop.fragen_ab_aktiv():
        from interview_theater.knoepfe.fragen import sende_mit_vorschlagen

        sende_mit_vorschlagen(
            conn, tg, chat_id, _mit_vorspann(vorspann, T._TEXT_PROAKTIV),
            undo_behalten=True,
        )
        return
    text = _mit_vorspann(vorspann, T._TEXT_PROAKTIV)
    if phase == PHASE_INTERVIEWS and vorspann:
        # P34 Runde 2, Befund A8: im Web-Kanal (Padua) haengt an den
        # Interview-Eintritt keine offene Frage -- Phase 3 stellt keine
        # Fragen, sie zeigt den Rekorder. Telegram bleibt unveraendert.
        from interview_theater import aufnahme

        if aufnahme.ist_web_gruppe(conn, chat_id):
            text = vorspann
    message_id = tg.sende(chat_id, text)
    repo.merke_nachricht(
        conn, chat_id, message_id, None, 1, "text", text, repo._jetzt(),
    )


def _mit_vorspann(vorspann: str | None, text: str) -> str:
    """Haengt einen Text unter die Eintrittsnachricht -- oder gibt ihn allein
    zurueck, wenn es keine gibt."""
    return f"{vorspann}\n\n{text}" if vorspann else text


def _ueberarbeitung_aktiv() -> bool:
    """Padua Phasen TEIL 2: laeuft die Ueberarbeitungs-Zustandsmaschine?"""
    from interview_theater import ueberarbeitung

    return ueberarbeitung.aktiv()


def _sende_karte(tg, chat_id: int, nummer: int) -> None:
    """Die Telefon-Organisationskarte dieser Phase, VOR der Eintrittsnachricht
    (UX-Knoepfe-Karte, Abschnitt 5): wie die Telefone fuer diese Phase liegen
    sollen, als Bild mit einem Satz dazu -- bei JEDEM Eintritt, auch einem
    Wiedereintritt aus einer spaeteren Phase.

    Deterministisch, kein Modellaufruf: das Bild liegt fertig unter
    ``interview_theater/static/handys/`` (``scripts/handy_karten.py``), der
    Satz kommt aus derselben Tabelle (``interview_theater.handykarten``).

    Still bei fehlender Karte (keine Datei generiert, unbekannte Phasennummer)
    und bei einem Kanal ohne ``sende_bild`` -- die Telegram-Attrappen in
    Tests und Simulation (``simulation/attrappe.py``, ``tests/test_ablauf.py``)
    bilden sie nicht nach, und ein zweiter Mechanismus nur fuer sie lohnt
    nicht (dieselbe Abwaegung wie bei ``sende_datei`` dort)."""
    from interview_theater import handykarten

    datei = handykarten.pfad(nummer)
    satz = handykarten.satz(nummer)
    if datei is None or satz is None or not hasattr(tg, "sende_bild"):
        return
    try:
        inhalt = datei.read_bytes()
    except OSError:
        return
    tg.sende_bild(chat_id, datei.name, inhalt, satz)


def _biete_modellwahl_wenn_faellig(conn, tg, e, chat_id: int) -> None:
    """Die Modellwahl-Einwilligungsfrage, wenn sie noch faellig ist
    (``szene_claude.angebot_faellig``) -- derselbe Check-und-Frage-Schritt
    fuer jeden Aufrufer: dieselbe Spalte (``gruppe.szene_usa_bestaetigt_am``),
    derselbe Knopfweg (``ART_SZENE_USA``, ``biete_szene_usa``).

    Seit dem 03.10.2026 (Padua Phase 1+2 Karte) ruft ``eintritt_in_phase``
    diese Funktion aus PHASE_BEGRIFFE **und** PHASE_SETTING -- die Frage
    steht damit schon beim Einstieg in Phase 1. Der PHASE_SETTING-Aufruf ist
    seitdem in der Praxis ein Sicherheitsnetz (genau wie der aeltere
    PHASE_SZENEN-Zweig unten einer ist): fuer Gruppen, die Phase 1 schon vor
    diesem Umbau durchlaufen haben, liefert ``angebot_faellig`` dort noch
    True; fragt Phase 1 bereits, liefert sie danach ueberall False, und
    dieser Aufruf wird zum No-Op."""
    from interview_theater import szene_claude

    if szene_claude.angebot_faellig(e, conn, chat_id):
        repo.merke_szene_usa_angeboten(conn, chat_id)
        tg.sende(chat_id, T._TEXT_ANGEBOT_MODELLWAHL)
        biete_szene_usa(conn, tg, chat_id)


def eintritt_in_phase(conn, tg, klm, e, chat_id: int, nummer: int) -> None:
    """Was beim Eintritt in eine Phase passiert -- fuer ALLE sieben gleich
    aufgebaut (06.09.2026, Birk).

    Eine deterministische Nachricht (``phasentexte.eintritt``: Kopfzeile
    "▶️ Phase N von 7 · Name", zwei bis vier Saetze Einleitung, die
    Parameter-Checkliste aus dem Arbeitsstand) und darunter die Knoepfe, die
    zum Einstieg DIESER Phase gehoeren. Neu erfunden wird dabei nichts: es
    sind dieselben Wege wie bisher -- die Eintritt-Frage mit "Ja, wir
    zuerst · Schlag du vor", in Phase 3 der Leitfaden, in 5 die Schaerfung,
    in 7 die Szenenfolge mit der Pruefung des Stuecks.

    **Kein Modellaufruf** (Zusage 2): alles kommt aus der Datenbank, und was
    ein Modell braucht (Schaerfung), geht in einen eigenen Thread.

    Ein Aufrufweg fuer alle vier Eintrittswege -- Knopf "Weiter zu ...",
    ``/phase N``, Erkenner-art ``phase_setzen`` und die proaktive
    Phasenmeldung: die Gruppe soll denselben Rahmen sehen, egal wie sie
    hergekommen ist."""
    from interview_theater import phasentexte

    _sende_karte(tg, chat_id, nummer)
    if nummer == PHASE_BEGRIFFE:
        # Modellwahl-Karte, Padua Phase 1+2 (03.10.2026): die
        # Einwilligungsfrage steht jetzt schon HIER, beim Einstieg in
        # Phase 1 -- nicht mehr erst beim Uebergang 3 -> 4. Dieselbe Spalte
        # (gruppe.szene_usa_bestaetigt_am), derselbe Knopfweg (ART_SZENE_USA,
        # biete_szene_usa): eine Antwort hier gilt fuer das ganze weitere
        # Gespraech UND die Szene, keine zweite Frage spaeter. Der Einstieg
        # wird NICHT auf die Antwort verzoegert: er geht sofort weiter, bis
        # zur Antwort laeuft jeder Gespraechszug auf Kimi
        # (``modellwahl.konversation_ueber_claude``).
        _biete_modellwahl_wenn_faellig(conn, tg, e, chat_id)
    if nummer == PHASE_SETTING:
        # Sicherheitsnetz fuer Gruppen, die den Eintritt in Phase 1 schon vor
        # diesem Umbau durchlaufen haben (``angebot_faellig`` liefert dann
        # noch True) -- wie der PHASE_SZENEN-Zweig weiter unten greift das
        # im Normalfall nicht mehr, sobald Phase 1 schon gefragt hat.
        _biete_modellwahl_wenn_faellig(conn, tg, e, chat_id)
    if nummer == PHASE_BEGRIFFE and klm is not None:
        # **Derselbe Einstieg wie beim Erstkontakt** (02.10.2026, Birk,
        # Padua): keine Kopfzeile, kein fester Satz -- der erste Impuls kommt
        # von der Gruppe, und eine deterministische Zeile geht nicht auf sie
        # ein. Ein Gespraechszug mit der ERSTKONTAKT-Anweisung, im Thread
        # (Zusage 2). Ohne Modell (Tests, Skripte) bleibt der feste Rahmen.
        from interview_theater import kontext

        if _starte_auftrag(
            conn, tg, klm, e, chat_id, kontext.einstieg_begriffe(conn, chat_id, e),
        ):
            return
    if nummer == PHASE_BEGRIFFE:
        # Karte t_4517d4ad (D10): der deterministische Einstiegssatz zum
        # Mithoeren -- seit 05.10.2026 (Birk, Live-Test) nur noch ohne den
        # modellgeschriebenen Einstieg: der erklaert die zwei Handys selbst
        # (``kontext.ERSTKONTAKT_DISKUSSION``), der Satz kaeme sonst doppelt.
        # Ohne Profil ``diskussion.aktiv`` sendet er nichts.
        from interview_theater import begriffsboard

        begriffsboard.sende_einstieg(conn, tg, e, chat_id)
    if nummer == PHASE_SETTING and klm is not None:
        # Padua-Brainstorming-Umbau (02.10.2026): derselbe Mechanismus wie
        # oben fuer Phase 1 -- kein fester Text, eine Anweisung, das Modell
        # schreibt den Einstieg selbst. Gilt fuer Erst- UND Wiedereintritt
        # (``kontext.einstieg_setting``). Ohne Modell bleibt der
        # deterministische Rahmen (Tests, Skripte).
        from interview_theater import kontext

        if _starte_auftrag(
            conn, tg, klm, e, chat_id, kontext.einstieg_setting(conn, chat_id, e),
        ):
            return
    if nummer == PHASE_FRAGEN:
        # Padua Phase 1+2 Umbau, Aufgabe 12 (03.10.2026): die KI-Fragen
        # entstehen im Hintergrund, BEVOR die Gruppe eine einzige eigene
        # Frage geschrieben hat -- nur unter dem Profilschalter
        # ``fragen_ab.aktiv`` (sonst bleibt Phase 2 unveraendert, auch ohne
        # Modell). Rein additiv: die bestehende ``else``-Faellthrough unten
        # (``biete_proaktiv``) laeuft unveraendert weiter.
        from interview_theater import fragen_ki, workshop

        if workshop.fragen_ab_aktiv():
            fragen_ki.starte(conn, tg, klm, e, chat_id)
    kopf = phasentexte.eintritt(conn, chat_id, nummer)
    if nummer == PHASE_INTERVIEWS:
        # Der Schritt in die Interviews ist der Moment, in dem die Gruppe
        # den Leitfaden braucht -- gleich geht sie damit auf fremde
        # Menschen zu. Einmal ungefragt (``sende_einmal``), danach nur
        # noch ueber den Knopf: deterministisch, kein Modellaufruf.
        from interview_theater import leitfaden

        biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)
        leitfaden.sende_einmal(conn, tg, chat_id, e=e)
        # Die Interviewsprache (Karte A1): nur, wo das Profil sie offen
        # laesst. Nach dem Leitfaden, weil er die erste Frage ist, die sich
        # die Gruppe vor dem Losgehen stellt.
        biete_stt_sprache(conn, tg, chat_id)
    elif nummer == PHASE_STUECKPRUEFUNG and _ueberarbeitung_aktiv():
        # Padua Phasen TEIL 2 (Phase 7, Stage Version): nur die Einleitung,
        # dann der EINE Schrittweg -- Formen, Sprechweisen, Szene fuer Szene.
        # KEIN Durchlauf-Menue und KEINE Stueckpruefung beim Eintritt: die
        # Pruefung des Stuecks kommt am Ende (``ueberarbeitung.starte_schluss``).
        from interview_theater import ueberarbeitung

        message_id = tg.sende(chat_id, kopf)
        repo.merke_bot_zeile(conn, chat_id, message_id, e, kopf)
        ueberarbeitung.weiter_7(conn, tg, klm, e, chat_id, aus_eintritt=True)
    elif nummer == PHASE_STUECKPRUEFUNG:
        # Die Schaerfung des Stuecks (06.09.2026, Birk): das komplette
        # Textbuch geht EINMAL beim Eintritt an den Stueck-Judge, im Thread
        # (Zusage 2: kein Modellaufruf in diesem Handler). Bis der Befund da
        # ist, steht die Szenenfolge mit Status und den Knoepfen "Szene N
        # ansehen" / "Textbuch als Datei" -- alles aus der Datenbank.
        tg.sende(chat_id, kopf)
        biete_durchlauf(conn, tg, chat_id, e)
        starte_stueckpruefung(conn, tg, klm, e, chat_id)
    elif nummer == PHASE_SCHAERFUNG:
        # Die Schaerfung fragt nicht nach Ideen: sie legt die Geschichte
        # neben die Interviews. Das Mapping laeuft automatisch beim
        # Eintritt, im Thread (Zusage 2).
        from interview_theater import entwurf, workshop

        tg.sende(chat_id, kopf)
        # Padua Phasen TEIL 1 (03.10.2026): nur unter dem Profilschalter
        # ``[prosa_entwurf] aktiv`` startet nach dem Mapping zusaetzlich die
        # Stufe-A-Uebersicht -- Dortmund (und jedes Profil ohne die Zeile)
        # bleibt beim bisherigen Weg, ``danach`` bleibt dort ``None``.
        danach = None
        if workshop.prosa_entwurf_aktiv():
            def danach():
                entwurf.starte_uebersicht(conn, tg, klm, e, chat_id)
        starte_schaerfung(conn, tg, klm, e, chat_id, danach=danach)
    else:
        # Beim Eintritt in eine Phase fragt der Bot zuerst die Gruppe,
        # statt sofort vorzuschlagen (Zusage: proaktiv, aber nicht
        # vorlaut).
        from interview_theater import ueberarbeitung

        padua_6 = nummer == PHASE_SZENEN and ueberarbeitung.aktiv()
        if padua_6:
            # Padua Phasen TEIL 2 (Phase 6, Rewrite): nur die Einleitung --
            # die offene Frage "habt ihr selbst schon Ideen?" passt nicht
            # vor eine Geschichte, die schon dasteht und gleich geprueft
            # wird.
            message_id = tg.sende(chat_id, kopf)
            repo.merke_bot_zeile(conn, chat_id, message_id, e, kopf)
        else:
            biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)
        if nummer == PHASE_SZENEN:
            # **Die USA-Frage steht beim EINTRITT** (06.09.2026, Birk
            # 12:25), als eigene Nachricht direkt nach der Einleitung und
            # VOR dem ersten Prosa-Lauf. Bis dahin kam sie mitten aus dem
            # Szenenlauf heraus, wenn die Gruppe schon wartete -- und der
            # Lauf brach dafuer ab. Einmal je Gruppe: steht die Antwort
            # oder wurde schon gefragt, passiert nichts.
            from interview_theater import szene_claude

            if szene_claude.angebot_faellig(e, conn, chat_id):
                from interview_theater import szene as szene_modul

                repo.merke_szene_usa_angeboten(conn, chat_id)
                tg.sende(chat_id, szene_modul.T._TEXT_ANGEBOT_USA)
                biete_szene_usa(conn, tg, chat_id)
            else:
                # Die Frage ist beantwortet (oder es gibt kein US-Modell):
                # dann steht hier gleich der Knopf, aus dem der Lauf startet.
                # In Padua: die vorhandene Prosa pruefen statt neu schreiben
                # (``ueberarbeitung.weiter_6``, Rueckfall dort: der Knopf).
                if padua_6:
                    ueberarbeitung.weiter_6(conn, tg, klm, e, chat_id,
                                            aus_eintritt=True)
                else:
                    biete_kurzgeschichte(conn, tg, chat_id, T._TEXT_KURZGESCHICHTE_BEREIT)

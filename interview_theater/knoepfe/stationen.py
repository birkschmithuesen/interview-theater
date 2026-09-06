"""Der Phasenrahmen im Chat: Eintritt, Abschluss, proaktives Angebot.

Jede Phase hat denselben Rahmen (06.09.2026, Birk): Eintritt ueber EINEN Weg
(``eintritt_in_phase`` -- Knopf, ``/phase``, Erkenner, proaktive Meldung) mit
der deterministischen Nachricht aus ``phasentexte``, Abschluss ueber
``biete_phase_proaktiv`` mit allen gesetzten Parametern und "Weiter zu
<Phase>" · "Noch etwas aendern", **einmal** je Stufe (Merkposten
``arbeitsstand.phase_angeboten``).

Der Knopf "Weiter zu Phase N" selbst steht eine Schicht tiefer
(``basis._phasenknopf``): ihn haengen auch die Aufnahme- und Szenen-Leisten
unter ihre Nachrichten.
"""

from interview_theater import phasen, repo

from interview_theater.knoepfe.texte import (
    ART_NOCH_NICHT, ART_PHASE, ART_SCHLAG_VOR, ART_WIR_ZUERST,
    PHASE_INTERVIEWS, PHASE_SCHAERFUNG, PHASE_STUECKPRUEFUNG,
    _TEXT_PHASE_ANGEBOT, _TEXT_PHASE_NOCH_NICHT_KNOPF, _TEXT_PHASE_WEITER,
    _TEXT_PROAKTIV, _TEXT_SCHLAG_VOR_KNOPF, _TEXT_WIR_ZUERST_KNOPF,
)
from interview_theater.knoepfe.basis import (
    _daten, _id_aus_daten,
)
from interview_theater.knoepfe.szenen import (
    biete_durchlauf, starte_schaerfung, starte_stueckpruefung,
)


#: Was je Zielphase erledigt ist -- der halbe Satz vor "Weiter zu ...".
#: Kurz und konkret, damit die Gruppe sieht, WORAUF sich das Angebot stuetzt,
#: ohne dass der Bot den Arbeitsstand nacherzaehlt.
_ERLEDIGT_FUER = {
    2: "Eure Begriffe",
    3: "Eure Fragen",
    4: "Die Interviews sind ausgewertet und",
    5: "Setting, Figuren und Geschichte",
    6: "Geschichte und Szenenfolge",
    7: "Alle Szenentexte",
}


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
    if stufe is None:
        return False
    phasen.merke_angebot(conn, chat_id, stufe)
    weiter_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(stufe))
    noch_nicht_id = repo.lege_knopf_an(conn, chat_id, ART_NOCH_NICHT, str(stufe))
    leiste = [
        (f"Weiter zu {phasen.knopfbezeichnung(stufe)}", _daten(weiter_id)),
        (_TEXT_PHASE_NOCH_NICHT_KNOPF, _daten(noch_nicht_id)),
    ]
    text = _abschlusstext(conn, chat_id, stufe)
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return True


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
    frage = _TEXT_PHASE_WEITER.format(phase=phasen.knopfbezeichnung(stufe))
    if jetzige >= stufe:
        return _TEXT_PHASE_ANGEBOT.format(
            erledigt=_ERLEDIGT_FUER.get(stufe, "Alles Noetige"),
            phase=phasen.knopfbezeichnung(stufe),
        )
    return f"{phasentexte.abschluss(conn, chat_id, jetzige)}\n\n{frage}"


def biete_proaktiv(conn, tg, chat_id: int, phase: int, vorspann: str | None = None) -> None:
    """Die Frage beim Eintritt in eine Phase (05.09.2026 abends, Birk):
    "Bevor ich vorschlage: habt ihr selbst schon Ideen?" mit zwei Knoepfen.

    Deterministischer Systemtext, kein Modellaufruf. Der Grund ist einer aus
    dem Raum: ein Bot, der beim Phasenwechsel sofort drei Vorschlaege
    hinlegt, nimmt der Gruppe den Moment, in dem sie selbst etwas hat -- und
    genau der ist die Arbeit. "Schlag du vor" holt den Vorschlag dann in
    einem eigenen Thread (``ablauf.starte_auftrag``).

    ``vorspann`` ist seit dem 06.09.2026 die Eintrittsnachricht der Phase
    (``phasentexte.eintritt``): Kopfzeile, Einleitung, Checkliste. Sie steht
    in DERSELBEN Nachricht wie die Frage und die Knoepfe -- der Testabend hat
    gezeigt, was passiert, wenn eine Frage in einer eigenen Nachricht unter
    einem Text haengt (neun Phasenknoepfe, null Druecke)."""
    leiste = [
        (_TEXT_WIR_ZUERST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_WIR_ZUERST, str(phase)))),
        (_TEXT_SCHLAG_VOR_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHLAG_VOR, str(phase)))),
    ]
    message_id = tg.sende_mit_knoepfen(chat_id, _mit_vorspann(vorspann, _TEXT_PROAKTIV), leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)


def _mit_vorspann(vorspann: str | None, text: str) -> str:
    """Haengt einen Text unter die Eintrittsnachricht -- oder gibt ihn allein
    zurueck, wenn es keine gibt."""
    return f"{vorspann}\n\n{text}" if vorspann else text


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

    kopf = phasentexte.eintritt(conn, chat_id, nummer)
    if nummer == PHASE_INTERVIEWS:
        # Der Schritt in die Interviews ist der Moment, in dem die Gruppe
        # den Leitfaden braucht -- gleich geht sie damit auf fremde
        # Menschen zu. Einmal ungefragt (``sende_einmal``), danach nur
        # noch ueber den Knopf: deterministisch, kein Modellaufruf.
        from interview_theater import leitfaden

        biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)
        leitfaden.sende_einmal(conn, tg, chat_id)
    elif nummer == PHASE_STUECKPRUEFUNG:
        # Die Schaerfung des Stuecks (06.09.2026, Birk): das komplette
        # Textbuch geht EINMAL beim Eintritt an den Stueck-Judge, im Thread
        # (Zusage 2: kein Modellaufruf in diesem Handler). Bis der Befund da
        # ist, steht die Szenenfolge mit Status und den Knoepfen "Szene N
        # ansehen" / "Textbuch als Datei" -- alles aus der Datenbank.
        tg.sende(chat_id, kopf)
        biete_durchlauf(conn, tg, chat_id)
        starte_stueckpruefung(conn, tg, klm, e, chat_id)
    elif nummer == PHASE_SCHAERFUNG:
        # Die Schaerfung fragt nicht nach Ideen: sie legt die Geschichte
        # neben die Interviews. Das Mapping laeuft automatisch beim
        # Eintritt, im Thread (Zusage 2).
        tg.sende(chat_id, kopf)
        starte_schaerfung(conn, tg, klm, e, chat_id)
    else:
        # Beim Eintritt in eine Phase fragt der Bot zuerst die Gruppe,
        # statt sofort vorzuschlagen (Zusage: proaktiv, aber nicht
        # vorlaut).
        biete_proaktiv(conn, tg, chat_id, nummer, vorspann=kopf)


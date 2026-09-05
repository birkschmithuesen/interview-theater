"""Absichtserkenner (SPEC-kontext-architektur.md § 4.3, § 4.3a).

Schliesst die Luecke, die Teil A offen liess: ``kontext.py`` liest
``arbeitsstand``, ``figur`` und ``journal`` in den Prompt, aber vor Teil B
schrieb sie niemand. ``erkenne()`` erkennt Aenderungsabsichten im Gespraech,
``wende_an()`` schreibt sie in Arbeitsstand, Figuren, Journal und Schalter
(Aufgabe 3), ``baue_meldung()`` fasst die tatsaechlich wirksamen Aenderungen
zu hoechstens einer Nachricht je Lauf zusammen (Aufgabe 4), und ``laufe()``
kapselt alle drei Schritte fuer den Aufrufer aus dem Hintergrund-Pool.

Laeuft nachgelagert, nachdem die Bot-Antwort in der Gruppe steht. Niemand
wartet darauf (SPEC § 4.3): Modell ``google/gemma-4-31B-it``, erzwungenes
Schema, ``reasoning_effort: "none"`` (Vorgabe von ``LLM.schema``, hier nicht
extra gesetzt), ``temperature: 0.2``. Gemessen: 0 Falsch-Positive bei 25
Negativfaellen, 30/30 Treffer, 0,75 s -- Kimi (das Gespraechsmodell) verpasste
``interview_beenden`` in 3 von 3 Faellen, Nemotron-Nano fiel mit 6/27
Falsch-Positiven durch und darf deshalb nirgends als Vorgabewert auftauchen.

**Kontext:** aktueller Arbeitsstand + die neuen Nachrichten seit
``gruppe.letzte_extrahierte_message_id`` (``repo.unextrahierte``). Nicht das
Journal, nicht die Transkripte -- das Journal wird hier nur GESCHRIEBEN
(spaeter, in ``wende_an``), nie mitgelesen, und Transkripte gehoeren zum
Gespraechs-, nicht zum Erkenner-Kontext.

**Schema, bewusst flach** (global-constraints.md 'Schema'): ein Array aus
Objekten mit zwei Feldern, keine Verschachtelung tiefer als
``array > object > string``. Kein Objekt mit elf meist leeren Feldern --
strikte Modi kennen keine optionalen Felder, das Modell muesste jedes Mal
alle ausfuellen, und ein Feld, das befuellt werden *will*, ist ein
Halluzinationsanreiz. Die leere Liste ist die natuerliche Form von "nichts
gefunden". Kein ``maxItems`` im Schema (von strikten Modi oft nicht
unterstuetzt) -- die Fuenf-Obergrenze steht im Prompttext UND wird unten in
``erkenne()`` hart durchgesetzt.

**Fehlerhaltung** (global-constraints.md, SPEC § 4.3): Bei Erfolg rueckt das
Wasserzeichen vor, erkannte Aenderungen werden zurueckgegeben. Bei Fehlschlag
bleibt das Wasserzeichen STEHEN (kostenloser Wiederholungsversuch beim
naechsten Lauf), ein ``vorfall`` wird geschrieben, der Gruppe wird nichts
gemeldet, leere Liste zurueck. Ueber dem Token-Deckel FENSTER_DECKEL wird das
Wasserzeichen dagegen TROTZDEM vorgerueckt (sonst wuerde ein einmal zu
grosses Fenster den Erkenner dauerhaft lahmlegen) und ein ``vorfall``
``fenster_verworfen`` geschrieben.
"""

import logging
import re

from interview_theater import kontext, phasen, repo

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: interview_theater/prompts/erkenner.md fuer die vollstaendige Anweisung samt
#: der fuenf Few-Shot-Beispiele).
from interview_theater import anweisungen


def prompt() -> str:
    """Heiss nachgeladen (interview_theater.anweisungen)."""
    return anweisungen.hole("erkenner")

#: Alle erkennbaren Aenderungsarten, in derselben Reihenfolge wie im Prompt
#: aufgelistet (SPEC § 4.3, teil-b.md Aufgabe 2). Auch die Schema-Enum unten
#: verwendet diese Liste, damit beide Stellen nie auseinanderlaufen.
ARTEN = (
    "interview_starten",
    "interview_beenden",
    "interview_benennen",
    # Seit 05.09.2026 (N5): ein Hoerfehler von Whisper wird ueberall dort
    # ersetzt, wo er steht -- Transkripte, Zusammenfassungen, Belegzitate.
    # Keine Neuverdichtung: die Ergebnisse der Gruppe bleiben stehen.
    "transkript_korrigieren",
    "begriffe_setzen",
    # Seit 04.09.2026 abends: die Frageliste aus Phase 2 ist ein eigenes Feld
    # (arbeitsstand.fragen). Fragen formulieren und Interviews fuehren sind
    # zwei Arbeiten, also braucht die erste auch ein eigenes Ergebnis.
    "fragen_setzen",
    "kernthema_setzen",
    # Seit 05.09.2026: Phase 5 heisst "Format & Rahmen" (interview_theater/
    # phasen.py). ``format_setzen`` haelt fest, WAS entsteht und welche Formen
    # vorkommen duerfen ("Musical: Dialog, Lied, Rap"), ``rahmen_setzen``,
    # WORIN es spielt (Ort, Zeit, Anlass, roter Faden).
    "format_setzen",
    "rahmen_setzen",
    # Bleibt -- aber als OPTIONALES Feld: ein durchgehender Konflikt ist eine
    # Rahmen-Entscheidung, keine Pflicht (Birk 05.09.2026).
    "hauptkonflikt_setzen",
    "figur_setzen",
    # Seit 05.09.2026: aus welchem Interview eine Figur spricht. Der Bot
    # schlaegt die Zuordnung im Gespraech vor, die Gruppe nickt sie ab --
    # danach laeuft EIN Sprachprofil-Aufruf (interview_theater/sprachprofil.py).
    "figur_quelle_setzen",
    "wortlaut_an",
    "wortlaut_aus",
    "verworfen",
    "entschieden",
    # Seit 05.09.2026: eine Szene wird zuerst GEPLANT und erst danach
    # geschrieben. Diese art traegt die Felder nach (form, ort, zeit, anlass,
    # figuren, was_passiert, was_anders, kernsaetze, ton) -- einzeln, so dass
    # ein spaeterer Lauf ergaenzen kann, ohne Frueheres zu ueberschreiben.
    "szene_planen",
    # Faellt aus der Reihe: die einzige art, die keinen Arbeitsstand
    # veraendert, sondern eine Handlung anstoesst (interview_theater/szene.py).
    # Deshalb hat sie in _wende_eine_an bewusst keinen Schreibpfad und wird
    # erst in laufe() ausgewertet.
    "szene_schreiben",
    # Seit 05.09.2026 frueh (Birk): die Antwort der Gruppe auf das Angebot,
    # Szenentexte von einem US-Modell schreiben zu lassen. wert "ja" oder
    # "nein". Gilt nur, wenn der Bot das Angebot gestellt hat (die Frage
    # steht dann im Vorlauf); sonst nie.
    "szene_usa",
    # Seit 04.09.2026: die Arbeitsphase ist ein gespeichertes Feld, und die
    # Gruppe setzt sie im Gespraech (interview_theater/phasen.py). Auch der
    # Widerspruch gegen einen automatischen Sprung landet hier.
    "phase_setzen",
    # Weiches Loeschen (NACHTRAG-weboberflaeche-und-sprache.md N3): die
    # einzige art, die etwas WEGNIMMT. Material -- Aufnahmen, Transkripte,
    # Verdichtungen -- ist davon ausgenommen und bleibt unentfernbar.
    "entfernen",
    # Seit 05.09.2026 (N4): die einzige art, die nur aus einer AUFNAHME
    # kommt. Sie schreibt nichts in den Arbeitsstand, sondern sagt, dass diese
    # Sprachnachricht an den Bot gerichtet war und nicht an die interviewte
    # Person -- aufnahme._teil_abschliessen zweigt sie daraufhin aus dem
    # Interview ab (repo.loese_aus_interview).
    "an_den_bot",
)

#: Die einzigen Arten, die aus dem Transkript einer Sprachnachricht im
#: Interviewmodus ueberhaupt gelten (Nachtrag N1, 05.09.2026). Alles andere
#: wird verworfen, bevor es angewendet werden kann -- **im Code**, nicht nur
#: im Prompt: was eine interviewte Person erzaehlt, ist Material und nie eine
#: Absicht der Gruppe (Korpusfaelle n12/n26, "das ist mein Kernthema" sagt
#: die Befragte). Der Live-Fall dahinter: eine Gruppe sagte "so, das
#: Interview ist fertig" in die Aufnahme hinein statt in den Chat, und der
#: Bot zeichnete weiter auf, weil das Transkript-Echo in keinem
#: Erkenner-Fenster steht (repo.TYP_TRANSKRIPT).
ARTEN_IN_AUFNAHME = (
    "interview_beenden",
    "interview_benennen",
    # N4, 05.09.2026: die dritte -- und die einzige, die es NUR hier gibt.
    # Eine Sprachnachricht im Interviewmodus muss nicht Interviewmaterial
    # sein: die Gruppe spricht auch den Bot an ("zeig mir die Verdichtungen",
    # "was war nochmal die zweite Frage"). Ohne diesen Weg landete das im
    # Interviewtranskript und in der Verdichtung -- und beantwortet wuerde es
    # nie.
    "an_den_bot",
)

#: Obergrenze fuer Aenderungen je Lauf -- im Prompttext UND hier im Code
#: durchgesetzt (global-constraints.md 'Schema': kein maxItems im Schema
#: selbst, weil strikte Modi das oft nicht unterstuetzen).
MAX_AENDERUNGEN = 5

#: Sampling-Temperatur des Erkenneraufrufs (SPEC § 4.3, § 4.3a) -- niedrig,
#: gegen Formulierungsvarianz und (bei mehrsprachigen Modellen)
#: Sprachdrift. Bewusst ein eigener Wert, nicht die des Gespraechsaufrufs.
TEMPERATURE = 0.2

#: Ab dieser geschaetzten Tokenzahl (kontext.schaetze -- Zeichen // 3, kein
#: Tokenizer) wird das Fenster verworfen statt gesendet (SPEC § 4.3
#: 'Deckel'): das Wasserzeichen rueckt trotzdem vor, ein vorfall
#: 'fenster_verworfen' wird geschrieben. Verhindert, dass ein einmal
#: aussergewoehnlich grosses Fenster (z. B. ein sehr langer Gespraechsstau)
#: den Erkenner auf Dauer blockiert.
FENSTER_DECKEL = 12000

#: Jedes Objekt braucht additionalProperties: false und ein required mit
#: allen Eigenschaften, sonst lehnt der Anbieter den erzwungenen Modus ab
#: (global-constraints.md § 4). Absichtlich flach: array > object > string,
#: keine tiefere Verschachtelung (die bricht bei kleineren Modellen wie
#: gemma/Apertus).
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["aenderungen"],
    "properties": {
        "aenderungen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["art", "wert"],
                "properties": {
                    "art": {"type": "string", "enum": list(ARTEN)},
                    "wert": {"type": "string"},
                },
            },
        },
    },
}


def _arbeitsstand_text(conn, chat_id: int) -> str:
    """Formatiert den aktuellen Arbeitsstand (Begriffe, Kernthema,
    Hauptkonflikt, Figuren) fuer den Erkenner-Kontext -- eine eigene,
    schlanke Formatierung statt der privaten ``kontext._baue_arbeitsstand``,
    weil der Erkenner den Stand nur als Eingabe braucht, nicht in der vollen
    Anzeigeform des Gespraechs-Prompts (dort zusaetzlich mit
    Kernthema-Begruendung)."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)

    zeilen = []
    if stand:
        if stand["begriffe"]:
            zeilen.append(f"Begriffe: {stand['begriffe']}")
        if stand["fragen"]:
            zeilen.append(f"Fragen: {stand['fragen']}")
        if stand["kernthema"]:
            zeilen.append(f"Kernthema: {stand['kernthema']}")
        if stand["format"]:
            zeilen.append(f"Format: {stand['format']}")
        if stand["rahmen"]:
            zeilen.append(f"Rahmen: {stand['rahmen']}")
        if stand["hauptkonflikt"]:
            zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(f"Figur {figur['name']}{beschreibung}")

    if not zeilen:
        return ""
    return "Arbeitsstand:\n" + "\n".join(zeilen)


def _nachrichten_text(nachrichten, vorlauf=None) -> str:
    zeilen = [kontext.sprecherzeile(n) for n in nachrichten]
    text = "Neue Nachrichten:\n" + "\n".join(zeilen)
    if vorlauf is not None:
        text = (
            "Vorlauf (die letzte Bot-Nachricht davor -- schon verarbeitet, nur "
            "damit du siehst, worauf sich eine Zustimmung bezieht):\n"
            + kontext.sprecherzeile(vorlauf) + "\n\n" + text
        )
    return text


def _baue_nutzertext(conn, chat_id: int, nachrichten, vorlauf=None) -> str:
    """Baut den Nutzertext des Erkenneraufrufs: aktueller Arbeitsstand plus
    die neuen Nachrichten seit dem Wasserzeichen -- nicht das Journal, nicht
    die Transkripte (SPEC § 4.3). Seit 05.09. mit Vorlauf (letzte
    Bot-Nachricht vor dem Fenster), siehe ``erkenne``."""
    bloecke = [b for b in (_arbeitsstand_text(conn, chat_id), _nachrichten_text(nachrichten, vorlauf)) if b]
    return "\n\n".join(bloecke)


def erkenne(klm, conn, e, chat_id: int) -> list[dict]:
    """Erkennt Aenderungsabsichten im Gespraech seit der letzten Erkennung.

    ``klm`` ist ein Objekt mit einer ``.schema(chat_id, system, nutzer,
    schema, art, modell=None, temperature=None) -> dict``-Methode (in
    Produktion ``interview_theater.llm.LLM``, in Tests eine Attrappe).

    Liefert eine Liste von ``{"art": ..., "wert": ...}``-Dicts, hoechstens
    ``MAX_AENDERUNGEN`` lang, nur mit bekannten ``art``-Werten. Wendet
    NICHTS auf die Datenbank an -- das ist eine spaetere Aufgabe
    (``wende_an``)."""
    neue = repo.unextrahierte(conn, chat_id)
    if not neue:
        # Kein Aufruf ins Leere: ohne neue Nachrichten gibt es nichts zu
        # erkennen, und ein Aufruf waere reine Latenz- und Kostenlast ohne
        # jeden Nutzen.
        return []

    letzte_message_id = max(n["message_id"] for n in neue)
    # Vorlauf (05.09. 04:40, dreimal belegt: Live Nachricht 69/90, Simulation
    # set1 und --set birk S11): der Bot schlaegt Figuren vor, der Erkenner
    # laeuft nach diesem Zug und rueckt das Wasserzeichen UEBER den Vorschlag.
    # Die Zustimmung im naechsten Zug ("namen nehme ich so") kommt dann ohne
    # den Vorschlag an -- der Erkenner sieht "nehme ich so" und weiss nicht,
    # was. Der Korpus hat das nie gezeigt, weil dort Vorschlag und Zustimmung
    # immer im selben Abschnitt liegen. Deshalb: die letzte Bot-Nachricht vor
    # dem Fenster wird als Vorlauf mitgegeben, mit Markierung -- sie ist
    # Kontext, keine neue Aenderung, und das Wasserzeichen kennt sie schon.
    vorlauf = repo.letzte_bot_nachricht_vor(conn, chat_id, neue[0]["message_id"])
    nutzer = _baue_nutzertext(conn, chat_id, neue, vorlauf)

    if kontext.schaetze(nutzer) > FENSTER_DECKEL:
        # Deckel (SPEC § 4.3): das Wasserzeichen rueckt TROTZDEM vor, sonst
        # bliebe der Erkenner an einem einmal zu grossen Fenster haengen und
        # wuerde bei jedem weiteren Lauf erneut daran scheitern.
        repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "fenster_verworfen",
            f"Absichtserkenner-Fenster ueber {FENSTER_DECKEL} geschaetzten Token "
            "verworfen, ohne Sprachmodell-Aufruf",
        )
        return []

    try:
        ergebnis = klm.schema(
            chat_id, prompt(), nutzer, SCHEMA, "erkenner",
            modell=e.erkenner_modell, temperature=TEMPERATURE,
        )
    except Exception:
        # Fehlschlag: das Wasserzeichen bleibt STEHEN -- ein kostenloser
        # Wiederholungsversuch beim naechsten Lauf, ohne eigene
        # Retry-Logik hier (SPEC § 4.3). Der Gruppe wird nichts gemeldet,
        # sie kann den Fehler weder beheben noch wartet sie darauf
        # (global-constraints.md 'Fehlerhaltung').
        log.exception("Absichtserkennung fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "extraktor_fehler",
            "Absichtserkenner-Aufruf fehlgeschlagen",
        )
        return []

    aenderungen = []
    for eintrag in ergebnis.get("aenderungen", []):
        art = eintrag.get("art")
        if art not in ARTEN:
            # Unbekannte art wird verworfen statt zu krachen -- ein
            # strikt erzwungenes Schema garantiert zwar den Enum-Wert,
            # aber die Attrappe in Tests (und ein kuenftiger Anbieterwechsel)
            # koennen trotzdem einen unbekannten Wert liefern.
            continue
        aenderungen.append({"art": art, "wert": eintrag.get("wert", "")})
        if len(aenderungen) >= MAX_AENDERUNGEN:
            break

    repo.setze_extrahiert_bis(conn, chat_id, letzte_message_id)
    return aenderungen


#: Kopfzeile des Nutzertexts, wenn nicht ein Gespraechsabschnitt geprueft
#: wird, sondern die Transkription EINER Sprachnachricht aus einem laufenden
#: Interview (N1). Der Prompt hat dazu einen eigenen Abschnitt -- ohne die
#: Kennzeichnung saehe das Modell nur einen Text ohne Sprecher und ohne
#: Zusammenhang.
_AUFNAHME_KOPF = (
    "Eine Sprachnachricht aus einem laufenden Interview, gerade transkribiert:"
)


def baue_aufnahme_nutzertext(transkript: str) -> str:
    """Der Nutzertext des Aufnahme-Laufs: die Kennzeichnung und das
    Transkript, sonst nichts -- kein Arbeitsstand, kein Verlauf.

    Oeffentlich, damit ``scripts/pruefe_prompts.py`` denselben Text baut wie
    der Betrieb (dieselbe Ueberlegung wie bei
    ``verdichter.baue_nutzertext``)."""
    return f"{_AUFNAHME_KOPF}\n{(transkript or '').strip()}"


def erkenne_in_aufnahme(klm, conn, e, chat_id: int, transkript: str) -> list[dict]:
    """Laesst den Erkenner ueber das Transkript einer einzelnen
    Sprachnachricht laufen, die waehrend eines Interviews eintraf (N1).

    Warum ueberhaupt: die Gruppe sagt "so, das Interview ist fertig" oft in
    die Aufnahme hinein, nicht in den Chat -- und das Transkript-Echo steht
    in keinem Erkenner-Fenster (``repo.TYP_TRANSKRIPT``, aus gutem Grund).
    Ohne diesen Lauf zeichnet der Bot danach weiter auf, und die Gruppe haelt
    ihn fuer kaputt.

    Beruehrt **kein** Wasserzeichen: dieser Lauf haengt an einer Aufnahme,
    nicht am Gespraechsverlauf, und darf den naechsten regulaeren Lauf
    (``erkenne``) nicht um seine Nachrichten bringen. Liefert nur Arten aus
    ``ARTEN_IN_AUFNAHME``; ein Fehlschlag liefert eine leere Liste (die
    Aufnahme bleibt dann eben Material, das ist der harmlose Ausgang)."""
    text = (transkript or "").strip()
    if not text:
        return []
    try:
        ergebnis = klm.schema(
            chat_id, prompt(), baue_aufnahme_nutzertext(text), SCHEMA, "erkenner",
            modell=e.erkenner_modell, temperature=TEMPERATURE,
        )
    except Exception:
        log.exception("Absichtserkennung in einer Aufnahme fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "extraktor_fehler",
            "Absichtserkenner-Aufruf ueber ein Teil-Transkript fehlgeschlagen",
        )
        return []

    aenderungen = []
    for eintrag in ergebnis.get("aenderungen", []):
        if eintrag.get("art") not in ARTEN_IN_AUFNAHME:
            continue
        aenderungen.append({"art": eintrag["art"], "wert": eintrag.get("wert", "")})
    return aenderungen[:MAX_AENDERUNGEN]


def wende_aus_aufnahme_an(klm, tg, conn, e, chat_id: int, aenderungen: list[dict]) -> None:
    """Wendet an, was ``erkenne_in_aufnahme`` gefunden hat -- derselbe Weg
    wie am Ende von ``laufe()``: schreiben, den Moduswechsel bestaetigen, das
    beendete Interview zusammenfuegen und verdichten lassen.

    Aufgerufen wird das erst, NACHDEM der Teil selbst auf 'fertig' steht:
    sonst faende ``aufnahme.schliesse_ab`` einen offenen Teil und verschoebe
    den Abschluss um ein Nachhol-Intervall. Der Teil bleibt Teil des
    Interviews -- der Satz "so, das Interview ist fertig" ist mit
    aufgenommen worden und steht harmlos am Ende des Transkripts.

    Die Aenderungsmeldung (``baue_meldung``) faellt hier weg: die beiden
    erlaubten Arten sind darin ohnehin still, und die Bestaetigung "Aufnahme
    beendet." samt Verdichtung ist die Rueckmeldung, die zaehlt."""
    if not aenderungen:
        return
    wirkliche = wende_an(conn, e, chat_id, aenderungen)
    _melde_interviewmodus(tg, conn, e, chat_id, wirkliche)
    _schliesse_interview_ab(klm, tg, conn, e, wirkliche)


#: art -> Arbeitsstand-Feld fuer die Aenderungsarten, die ein einzelnes
#: Feld ueberschreiben (SPEC § 4.3 'Ueberschreiben ist der Normalfall').
_ARBEITSSTAND_ARTEN = {
    "begriffe_setzen": "begriffe",
    "fragen_setzen": "fragen",
    "kernthema_setzen": "kernthema",
    "format_setzen": "format",
    "rahmen_setzen": "rahmen",
    "hauptkonflikt_setzen": "hauptkonflikt",
}


def _wende_arbeitsstand_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Ueberschreibt ein Arbeitsstand-Feld -- aber nur, wenn sich der Wert
    tatsaechlich aendert (die wichtigste Regel aus Aufgabe 3: derselbe Wert
    ist keine Aenderung, sonst meldete Aufgabe 4 bei jedem Zug dasselbe
    Kernthema erneut)."""
    wert = wert.strip()
    if not wert:
        return None
    feld = _ARBEITSSTAND_ARTEN[art]
    stand = repo.hole_arbeitsstand(conn, chat_id)
    aktuell = stand[feld] if stand else None
    if aktuell == wert:
        return None
    repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    return {"art": art, "wert": wert}


def _wende_figur_an(conn, chat_id: int, wert: str) -> dict | None:
    """Trennt ``wert`` am ersten Doppelpunkt in Name und Beschreibung (SPEC
    § 4.3: 'ein String, den der Code am ersten Doppelpunkt trennt'). Ohne
    Doppelpunkt liefert ``str.partition`` eine leere Beschreibung statt zu
    krachen. Existiert der Name schon (getrimmt, Kleinschreibung -- siehe
    repo.setze_figur), wird nur bei tatsaechlich geaenderter Beschreibung
    geschrieben.

    Korrektur (2026-09-04): nennt das Modell beilaeufig einen schon
    bekannten Namen ohne Doppelpunkt (z. B. nur "Peter"), ist ``beschreibung``
    leer -- das darf die vorhandene Beschreibung NICHT loeschen. Ohne diese
    Pruefung ueberschrieb ein blosser Namenstreffer die vorhandene
    Beschreibung mit einem leeren String und die Meldung bestaetigte das
    sogar noch als 'Notiert', ohne dass jemand merkt, dass die Beschreibung
    weg ist -- echter, stiller Datenverlust. Bei einem NEUEN Namen bleibt das
    Verhalten unveraendert: eine leere Beschreibung ist dort kein Fehler,
    sondern der Normalfall (der Name allein ist schon eine Aenderung)."""
    wert = wert.strip()
    if not wert:
        return None
    name, _, beschreibung = wert.partition(":")
    name = name.strip()
    beschreibung = beschreibung.strip()
    if not name:
        return None

    vorhandene = repo.figuren(conn, chat_id)
    treffer = next(
        (f for f in vorhandene if f["name"].strip().lower() == name.lower()), None
    )
    if treffer is not None and not beschreibung:
        # Name bekannt, aber kein neuer Beschreibungsteil mitgeliefert --
        # die vorhandene Beschreibung bleibt unangetastet und gilt nicht als
        # Aenderung.
        return None
    if treffer is not None and (treffer["beschreibung"] or "").strip() == beschreibung:
        return None

    repo.setze_figur(conn, chat_id, name, beschreibung)
    return {"art": "figur_setzen", "wert": name}


#: Trennt in einer Korrektur das falsche vom richtigen Wort. Beide
#: Schreibweisen, weil das Modell mal die eine und mal die andere liefert.
_KORREKTUR_PFEILE = ("->", "→")

#: Mehrere Korrekturen in einem Wert.
_KORREKTUR_TRENNER = "|"


def _wende_transkript_korrektur_an(conn, chat_id: int, wert: str) -> dict | None:
    """Wendet eine (oder mehrere) Transkriptkorrekturen an (art
    ``transkript_korrigieren``, wert ``"gepoekt -> gepogt"``, mehrere mit
    ``|`` getrennt).

    Der Live-Fall (Probelauf, Nachrichten 41-50): Whisper hoerte "im Auto"
    statt "im autonomen Zentrum" und "gepoekt" statt "gepogt". Der Bot
    antwortete dreimal "korrigiere ich" -- und in der Datenbank aenderte sich
    nichts. Jetzt aendert sich etwas, und die Notiert-Zeile sagt was.

    Liefert None, wenn nichts ersetzt wurde: eine Korrektur, die nichts
    trifft, ist keine Aenderung und bekommt keine Meldung."""
    paare = []
    for stueck in (wert or "").split(_KORREKTUR_TRENNER):
        for pfeil in _KORREKTUR_PFEILE:
            falsch, trenner, richtig = stueck.partition(pfeil)
            if trenner and falsch.strip() and richtig.strip():
                paare.append((falsch.strip(), richtig.strip()))
                break
    if not paare:
        return None

    gewirkt = []
    for falsch, richtig in paare:
        if repo.korrigiere_transkripte(conn, chat_id, falsch, richtig):
            gewirkt.append(f"{falsch} -> {richtig}")
    if not gewirkt:
        return None
    text = ", ".join(gewirkt)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Transkript korrigiert: {text}",
        quelle="erkenner",
    )
    return {"art": "transkript_korrigieren", "wert": text}


def _wende_figur_quelle_an(conn, chat_id: int, wert: str) -> dict | None:
    """Ordnet einer Figur das Interview zu, aus dem sie spricht (art
    ``figur_quelle_setzen``, wert ``"Pola: Interview 2"``).

    Getrennt wird am ersten Doppelpunkt, wie bei ``figur_setzen``. Beide
    Seiten muessen etwas treffen, das es gibt: eine Figur aus dem Arbeitsstand
    und ein Interview dieser Gruppe (``aufnahme.finde_interview``, tolerant
    gegen Nummer und Namensteil). Trifft eine Seite nicht, wird nichts
    geschrieben -- eine falsche Zuordnung praegte sonst ueber das Sprachprofil
    die Stimme einer Figur in jedem weiteren Szenenlauf.

    Der Rueckgabewert traegt die ``figur_id`` mit: ``laufe()`` stoesst damit
    den Sprachprofil-Aufruf an (wie bei ``interview_beenden`` die
    ``aufnahme_id``) -- hier wird nur geschrieben, nie gerufen und nie
    gesendet."""
    from interview_theater import aufnahme  # spaeter Import, haelt den Modulkopf frei

    name, _, bezeichnung = (wert or "").partition(":")
    figur = repo.hole_figur(conn, chat_id, name)
    if figur is None:
        return None
    kopf = aufnahme.finde_interview(conn, chat_id, bezeichnung.strip())
    if kopf is None:
        return None
    if figur["quelle_aufnahme_id"] == kopf["id"] and figur["sprachprofil"]:
        # Dieselbe Quelle, und das Profil steht schon: kein zweiter bezahlter
        # Aufruf fuer dasselbe Ergebnis (dieselbe Regel wie ueberall -- ein
        # unveraenderter Wert ist keine Aenderung).
        return None
    repo.setze_figur_quelle(conn, figur["id"], kopf["id"])
    return {
        "art": "figur_quelle_setzen",
        "wert": f"{figur['name']}: {kopf['name'] or 'Interview'}",
        "figur_id": figur["id"],
    }


def _figuren_aus_namen(conn, chat_id: int, namen: str) -> list[int]:
    """Uebersetzt "Mira, Pola, Pal" in Figur-ids -- **nur Figuren aus dem
    Arbeitsstand** (Birk 05.09.2026: "wenn Figuren fehlen, darf die Szene gar
    nicht erstellt werden").

    Ein unbekannter Name wird stillschweigend uebergangen und nicht angelegt:
    eine Figur entsteht im Gespraech (``figur_setzen``), mit Beschreibung und
    Sprachprofil. Eine, die nur in einer Szenenzeile vorkaeme, haette weder
    das eine noch das andere -- und genau daraus sind im Probelauf NINA und
    MORITZ geworden.

    Namensvergleich wie in ``repo.setze_figur``: getrimmt, kleingeschrieben,
    kein Teiltreffer."""
    vorhandene = {f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)}
    ids = []
    for name in (namen or "").split(","):
        figur_id = vorhandene.get(name.strip(" .;").lower())
        if figur_id is not None:
            ids.append(figur_id)
    return ids


def _wende_szene_planen_an(conn, chat_id: int, wert: str) -> dict | None:
    """Traegt die genannten Szenenfelder ein (art ``szene_planen``,
    05.09.2026).

    **Feld fuer Feld, nie als Ganzes**: was der Abschnitt nicht nennt, bleibt
    stehen. Die Gruppe entscheidet eine Szene selten in einem Satz -- erst der
    Ort, dann wer dabei ist, zwei Nachrichten spaeter ein Kernsatz --, und
    jeder dieser Schritte soll den vorigen ergaenzen statt ihn zu loeschen.

    Ohne genannte Nummer trifft es die zuletzt bearbeitete Szene
    (``hole_letzte_szene``, dieselbe Regel wie im Gespraechs-Prompt: das ist
    die, um die es gerade geht); gibt es noch keine, entsteht Szene 1.

    Liefert None, wenn nichts Verwertbares dastand -- dann wurde nichts
    geschrieben und nichts gemeldet."""
    from interview_theater import szene  # spaeter Import, haelt den Modulkopf frei

    nummer, felder = szene.zerlege_planung(wert)
    if not felder and nummer is None:
        return None

    if nummer is None:
        letzte = repo.hole_letzte_szene(conn, chat_id)
        nummer = letzte["nummer"] if letzte is not None and letzte["nummer"] else 1
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)

    geaendert = []
    for feld, neuer_wert in felder.items():
        if feld == "figuren":
            ids = _figuren_aus_namen(conn, chat_id, neuer_wert)
            # Keine bekannte Figur getroffen: die Besetzung bleibt, wie sie
            # war. Sie zu leeren waere die schlechtere Fehlerrichtung -- die
            # Sperre (szene.fehlendes) meldet eine leere Besetzung ohnehin.
            if not ids:
                continue
            vorher = [f["id"] for f in repo.szene_figuren(conn, szene_id)]
            if vorher == ids:
                continue
            repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
            geaendert.append("figuren")
            continue
        if (repo.hole_szene(conn, szene_id)[feld] or "") == neuer_wert:
            continue
        repo.setze_szenenfeld(conn, szene_id, feld, neuer_wert)
        geaendert.append(feld)

    if not geaendert:
        return None
    return {
        "art": "szene_planen",
        "wert": szene.planungszeile(conn, repo.hole_szene(conn, szene_id)),
    }


def _wende_journal_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """``verworfen``/``entschieden`` haengen eine Journalzeile an -- nie in
    den Arbeitsstand (SPEC § 4.3: 'Journaleintraege fallen hier mit ab').
    Das Journal ist nur-anhaengend, ein Dubletten-Check waere hier sachfremd:
    zwei getrennte Aeusserungen mit demselben Wortlaut sind zwei Ereignisse."""
    wert = wert.strip()
    if not wert:
        return None
    repo.schreibe_journal(conn, chat_id, art, wert, quelle="erkenner")
    return {"art": art, "wert": wert}


def _wende_wortlaut_an(conn, chat_id: int, wert: str) -> dict | None:
    """``wortlaut_an``: Name im ``wert``, leer bedeutet 'alle' (``'*'``)."""
    name = wert.strip() or "*"
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["wortlaut_modus"] == name:
        return None
    repo.setze_wortlaut_modus(conn, chat_id, name)
    return {"art": "wortlaut_an", "wert": name}


def _wende_wortlaut_aus_an(conn, chat_id: int) -> dict | None:
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["wortlaut_modus"] is None:
        return None
    repo.setze_wortlaut_modus(conn, chat_id, None)
    return {"art": "wortlaut_aus", "wert": ""}


def _wende_interview_starten_an(conn, chat_id: int) -> dict | None:
    """Ein angekuendigtes Interview **startet nichts mehr** (05.09.2026,
    Birk nach dem Live-Lauf Gruppe 3, 16:36) -- es loest nur noch das
    ANGEBOT aus: die Ablauf-Erklaerung (``knoepfe.TEXT_ABLAUF``) mit dem
    Knopf "Interview starten" darunter (``_melde_interviewmodus``).

    Der gemessene Fall: die Gruppe sagte "Wir wollen ein Interview machen",
    der Gespraechs-Bot schrieb dazu eine eigene Bedienungsanleitung ("tippt
    auf Aufnahme starten"), und gleichzeitig schaltete diese Funktion den
    Modus schon an -- die Systemzeile trug dann den Knopf "Aufnahme
    beenden". Text und Knopf widersprachen sich, und die Gruppe hatte eine
    laufende Aufnahme, die niemand gestartet hatte.

    Eingeschaltet wird seitdem nur noch **durch eine Handlung**: der Knopf,
    ``/aufnahme`` oder ``/interview``. Der Rueckweg
    (``_wende_interview_beenden_an``, das gesprochene "fertig" aus der
    Aufnahme) bleibt unveraendert -- dort laeuft schon etwas, das man
    beenden kann, und es steht kein zweiter Weg daneben.

    Laeuft schon eine Aufnahme, ist das keine Aenderung: dann braucht
    niemand ein Angebot, den Modus einzuschalten."""
    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is not None and gruppe["interviewmodus_seit"] is not None:
        return None
    return {"art": "interview_starten", "wert": ""}


def _wende_interview_beenden_an(conn, chat_id: int) -> dict | None:
    """Schaltet den Interviewmodus aus und stempelt das laufende Interview als
    beendet -- spiegelbildlich zu _wende_interview_starten_an.

    Das Zusammenfuegen und die eine Verdichtung (§ 10.6) passieren hier
    ausdruecklich NICHT: ``wende_an`` schreibt nur in die Datenbank und
    schickt nie etwas, und die Verdichtung ist ein Sprachmodell-Aufruf mit
    einer Nachricht am Ende. Die ``aufnahme_id`` im Rueckgabewert reicht sie
    an ``laufe()`` weiter, wo es tg und klm gibt (wie bei ``szene_schreiben``,
    nur ueber den Rueckgabewert statt ueber die erkannte Aenderung -- hier
    braucht der Aufrufer eine id, die erst beim Anwenden feststeht)."""
    from interview_theater import aufnahme  # spaeter Import, haelt den Modulkopf frei

    gruppe = repo.hole_gruppe(conn, chat_id)
    if gruppe is None or gruppe["interviewmodus_seit"] is None:
        return None
    kopf_id = aufnahme.beende_interview(conn, chat_id)
    return {"art": "interview_beenden", "wert": "", "aufnahme_id": kopf_id}


def _wende_interview_benennen_an(conn, chat_id: int, wert: str) -> dict | None:
    """Benennt das letzte (juengste) Interview dieser Gruppe um. Ohne
    vorhandenes Interview gibt es nichts umzubenennen -- ein stilles No-Op,
    kein Fehler.

    Nur Interviews (``klasse='lang'``, § 10.6): "das war Marias Interview"
    meint das Interview, auch wenn dazwischen jemand einen Zuruf
    eingesprochen hat -- und erst recht nicht eine einzelne der fuenf
    Sprachnachrichten, aus denen es besteht (die stehen in ``transkripte``
    ohnehin nicht)."""
    wert = wert.strip()
    if not wert:
        return None
    aufnahmen = [a for a in repo.transkripte(conn, chat_id) if a["klasse"] == "lang"]
    if not aufnahmen:
        return None
    letzte = aufnahmen[-1]
    if letzte["name"] == wert:
        return None
    repo.setze_aufnahme_name(conn, letzte["id"], wert)
    return {"art": "interview_benennen", "wert": wert}


def _wende_phase_an(conn, chat_id: int, wert: str) -> dict | None:
    """Setzt die Arbeitsphase, die die Gruppe genannt hat (art
    ``phase_setzen``, interview_theater/phasen.py).

    ``wert`` ist eine Nummer oder ein Kurzname; ``phasen.nummer_fuer``
    uebersetzt tolerant. Laesst er sich nicht zuordnen, wird nichts
    geschrieben -- lieber keine Aenderung als die falsche Phase. Ein
    Ruecksprung (von 8 nach 5) ist ausdruecklich erlaubt: die Gruppe darf
    jederzeit zurueck, und genau so widerspricht sie auch einem
    automatischen Sprung."""
    nummer = phasen.nummer_fuer(wert)
    if nummer is None:
        return None
    if not phasen.setze(conn, chat_id, nummer, "erkenner"):
        return None
    return {"art": "phase_setzen", "wert": str(nummer)}


#: Die Zielarten des weichen Loeschens, am ERSTEN Wort von ``wert`` erkannt
#: (NACHTRAG-weboberflaeche-und-sprache.md N3).
#:
#: **``interview`` ist am 05.09.2026 dazugekommen (N5).** Die alte Regel
#: ("Material ist nie entfernbar") galt fuer Aufnahmen der Gruppe, die Inhalt
#: tragen -- ein Interview, das aus einer vier Sekunden langen
#: Sprachnachricht halluziniert wurde, traegt keinen, und die Gruppe musste
#: es im Probelauf trotzdem stehen lassen. Weich bleibt es trotzdem: die
#: Audiodatei liegt weiter auf der Platte, den vollstaendigen Loeschweg geht
#: nach wie vor allein ``scripts/loeschen.py``, von Hand, mit Rueckfrage.
_ENTFERNEN_ZIELE = (
    "figur", "kernthema", "format", "rahmen", "hauptkonflikt", "begriffe",
    "fragen", "szene", "journal", "interview", "aufnahme",
)

#: Journalzeile, die eine Entfernung festhaelt -- der Weg soll sichtbar
#: bleiben, auch wenn das Entfernte es nicht mehr ist.
_JOURNAL_ENTFERNT = "Entfernt: {was}"
_JOURNAL_ZURUECK = "Zurueckgenommen: {text}"

#: Szenennummer aus "Szene 2", "szene nr. 2", "2".
_SZENENNUMMER = re.compile(r"(\d{1,3})")


def _zerlege_entfernen(wert: str) -> tuple[str, str] | None:
    """Trennt ``wert`` am ersten Wort in Zielart und Rest ("Figur Peter" ->
    ``("figur", "Peter")``, "Journal: Kindheitsfragen" -> ``("journal",
    "Kindheitsfragen")``, "Kernthema" -> ``("kernthema", "")``).

    Tolerant gegen Doppelpunkt und Gross-/Kleinschreibung. Ist das erste Wort
    keine bekannte Zielart, liefert die Funktion None -- und der Aufrufer
    aendert nichts. Genau das faengt auch den Materialfall ab ("die Aufnahme
    von Meryem"), falls der Erkenner ihn entgegen seiner Anweisung doch
    einmal liefert: es gibt keinen Schreibpfad dorthin."""
    text = (wert or "").strip()
    if not text:
        return None
    erstes, _, rest = text.partition(" ")
    ziel = erstes.strip(" :,.").lower()
    if ziel not in _ENTFERNEN_ZIELE:
        return None
    return ziel, rest.strip(" :,")


#: art -> Arbeitsstandfeld fuer die vier Ziele, die schlicht auf NULL gesetzt
#: werden. Ein Zeitstempel waere hier sinnlos: das Feld hat genau einen Wert.
#: ``fragen`` ist ohne eigenen Befehl dazugekommen -- das weiche Loeschen
#: laeuft ueber dieselbe Zerlegung wie alles andere ("Fragen" als erstes Wort).
_ENTFERNEN_ARBEITSSTAND = {
    "kernthema": ("kernthema", "Kernthema"),
    "format": ("format", "Format"),
    "rahmen": ("rahmen", "Rahmen"),
    "hauptkonflikt": ("hauptkonflikt", "Hauptkonflikt"),
    "begriffe": ("begriffe", "Begriffe"),
    "fragen": ("fragen", "Fragen"),
}


def _entferne_arbeitsstandfeld(conn, chat_id: int, ziel: str) -> str | None:
    """Leert ein Arbeitsstandfeld und liefert seine Anzeigebezeichnung, oder
    None, wenn es ohnehin leer war (dann ist nichts passiert und nichts zu
    melden).

    Mit dem Kernthema faellt seine Begruendung: sie erklaert ein Thema, das
    es nicht mehr gibt, und wuerde sonst als Waise im Arbeitsstand stehen."""
    feld, bezeichnung = _ENTFERNEN_ARBEITSSTAND[ziel]
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not (stand and stand[feld]):
        return None
    repo.setze_arbeitsstand(conn, chat_id, feld, None)
    if feld == "kernthema":
        repo.setze_arbeitsstand(conn, chat_id, "kernthema_begruendung", None)
    return bezeichnung


def entferne(conn, chat_id: int, wert: str, quelle: str = "erkenner") -> dict | None:
    """Entfernt weich, was ``wert`` benennt (art ``entfernen``, NACHTRAG N3).

    Liefert ``{"art": "entfernen", "wert": "Figur Peter"}``, wenn wirklich
    etwas entfernt wurde, sonst None. **Nicht gefunden ist kein Fehler**:
    keine Aenderung, kein Journaleintrag, keine Meldung -- die Gruppe soll
    fuer einen beilaeufig genannten Namen keine Fehlermeldung bekommen, und
    ein "das gibt es nicht" waere ohnehin nur dann richtig, wenn der Erkenner
    den Namen exakt getroffen hat.

    Jede wirksame Entfernung bekommt eine Journalzeile: der Weg soll
    sichtbar bleiben. Bei einem Journaleintrag selbst wird nichts geloescht
    -- der alte Eintrag bekommt ``entfernt_am``, ein neuer haelt fest, dass
    er zurueckgenommen wurde.

    ``quelle`` unterscheidet im Journal den Erkenner vom Befehl
    (``befehle.py`` ruft dieselbe Funktion auf, damit es fuer beide Wege nur
    eine Wahrheit gibt)."""
    zerlegt = _zerlege_entfernen(wert)
    if zerlegt is None:
        return None
    ziel, rest = zerlegt

    if ziel == "journal":
        alter_text = repo.entferne_journal(conn, chat_id, rest)
        if alter_text is None:
            return None
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            _JOURNAL_ZURUECK.format(text=alter_text), quelle=quelle,
        )
        return {"art": "entfernen", "wert": f"Journal: {alter_text}"}

    if ziel in _ENTFERNEN_ARBEITSSTAND:
        bezeichnung = _entferne_arbeitsstandfeld(conn, chat_id, ziel)
    elif ziel == "figur":
        name = repo.entferne_figur(conn, chat_id, rest) if rest else None
        bezeichnung = f"Figur {name}" if name else None
    elif ziel in ("interview", "aufnahme"):
        # Ohne Angabe wird NICHT geraten: "loesch das Interview" ohne Nummer
        # oder Namen koennte jedes von fuenfen meinen, und weggenommen wird
        # hier Material (N5).
        from interview_theater import aufnahme  # spaeter Import

        kopf = aufnahme.finde_interview(conn, chat_id, rest) if rest else None
        name = repo.entferne_aufnahme(conn, chat_id, kopf["id"]) if kopf else None
        bezeichnung = name if name else None
    else:  # szene
        treffer = _SZENENNUMMER.search(rest or "")
        nummer = repo.entferne_szene(conn, chat_id, int(treffer.group(1))) if treffer else None
        bezeichnung = f"Szene {nummer}" if nummer is not None else None

    if bezeichnung is None:
        return None
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        _JOURNAL_ENTFERNT.format(was=bezeichnung), quelle=quelle,
    )
    return {"art": "entfernen", "wert": bezeichnung}


def _wende_eine_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Wendet genau eine Aenderung an und liefert das angewendete
    ``{"art": ..., "wert": ...}`` zurueck, oder ``None`` wenn nichts
    geschrieben wurde (leerer Wert oder Wert bereits so in der Datenbank)."""
    if art == "interview_starten":
        return _wende_interview_starten_an(conn, chat_id)
    if art == "interview_beenden":
        return _wende_interview_beenden_an(conn, chat_id)
    if art in _ARBEITSSTAND_ARTEN:
        return _wende_arbeitsstand_an(conn, chat_id, art, wert)
    if art == "figur_setzen":
        return _wende_figur_an(conn, chat_id, wert)
    if art == "transkript_korrigieren":
        return _wende_transkript_korrektur_an(conn, chat_id, wert)
    if art == "figur_quelle_setzen":
        return _wende_figur_quelle_an(conn, chat_id, wert)
    if art == "szene_planen":
        return _wende_szene_planen_an(conn, chat_id, wert)
    if art in ("verworfen", "entschieden"):
        return _wende_journal_an(conn, chat_id, art, wert)
    if art == "wortlaut_an":
        return _wende_wortlaut_an(conn, chat_id, wert)
    if art == "wortlaut_aus":
        return _wende_wortlaut_aus_an(conn, chat_id)
    if art == "interview_benennen":
        return _wende_interview_benennen_an(conn, chat_id, wert)
    if art == "phase_setzen":
        return _wende_phase_an(conn, chat_id, wert)
    if art == "szene_usa":
        # Nur, wenn das Angebot gestellt wurde -- sonst ist ein "ja" im Chat
        # kein Ja zum US-Modell, sondern zu irgendwas anderem.
        if repo.szene_usa_stand(conn, chat_id) != "offen":
            return None
        g = repo.hole_gruppe(conn, chat_id)
        if not g or not g["szene_usa_angeboten_am"]:
            return None
        w = (wert or "").strip().lower()
        if w not in ("ja", "nein"):
            return None
        repo.setze_szene_usa(conn, chat_id, w == "ja")
        return {"art": art, "wert": w}
    if art == "entfernen":
        return entferne(conn, chat_id, wert)
    if art == "an_den_bot":
        # Kein Schreibpfad, wie szene_schreiben: diese art aendert nichts,
        # sie ordnet eine Aufnahme anders ein. Das tut aufnahme.py, wo die
        # Aufnahme bekannt ist (N4).
        return None
    if art == "szene_schreiben":
        # Kein Schreibpfad: eine Szene ist kein Arbeitsstandfeld, das sich
        # ueberschreiben liesse, sondern ein eigener, minutenlanger
        # Sprachmodell-Aufruf. Den stoesst laufe() an -- dort gibt es tg und
        # klm, die wende_an() bewusst nicht bekommt (es schreibt nur in die
        # Datenbank und schickt nie etwas).
        return None
    # Unbekannte art sollte erkenne() bereits herausgefiltert haben; bei
    # direktem Aufruf von wende_an() (z. B. in Tests) einfach ignorieren
    # statt zu krachen.
    return None


def wende_an(conn, e, chat_id: int, aenderungen: list[dict]) -> list[dict]:
    """Schreibt erkannte Aenderungen in Arbeitsstand, Figuren, Journal und
    Schalter (SPEC § 4.3, teil-b.md Aufgabe 3).

    Liefert nur die Aenderungen zurueck, die tatsaechlich etwas verschoben
    haben -- Grundlage fuer die Meldung in Aufgabe 4 (``baue_meldung``).

    Robustheit: jede Aenderung laeuft in ihrem eigenen try/except. Eine
    fehlerhafte Aenderung (z. B. ein unerwarteter Werttyp) darf die anderen
    im selben Lauf nicht mitreissen -- sie wird geloggt und als ``vorfall``
    vermerkt, der Lauf macht mit der naechsten Aenderung weiter."""
    wirkliche = []
    for aenderung in aenderungen:
        art = None
        try:
            art = aenderung.get("art")
            wert = aenderung.get("wert") or ""
            ergebnis = _wende_eine_an(conn, chat_id, art, wert)
        except Exception:
            log.exception(
                "Anwenden einer Erkenner-Aenderung fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, art,
            )
            repo.merke_vorfall(
                conn,
                chat_id,
                getattr(e, "bot_name", None),
                "erkenner_anwenden_fehler",
                f"Aenderung art={art!r} konnte nicht angewendet werden",
            )
            continue
        if ergebnis is not None:
            wirkliche.append(ergebnis)
    return wirkliche


#: Zahlwoerter fuer die zusammenfassende Figuren-Zeile der Meldung (Aufgabe
#: 4) -- reicht bis MAX_AENDERUNGEN, weil in einem einzelnen Erkennerlauf nie
#: mehr als fuenf Aenderungen (und damit hoechstens fuenf figur_setzen)
#: vorkommen koennen.
_FIGUREN_ZAHLWORT = {2: "zwei", 3: "drei", 4: "vier", 5: "fuenf"}


def _figuren_zeile(namen: list[str]) -> str:
    liste = ", ".join(namen)
    if len(namen) == 1:
        return f"eine Figur: {liste}"
    zahlwort = _FIGUREN_ZAHLWORT.get(len(namen), str(len(namen)))
    return f"{zahlwort} Figuren: {liste}"


def baue_meldung(wirkliche_aenderungen: list[dict]) -> str | None:
    """Baut die eine Meldung je Erkennerlauf (SPEC § 4.3, teil-b.md Aufgabe
    4) -- nicht eine je Aenderung.

    Kernthema, Format, Rahmen und Hauptkonflikt bekommen je eine eigene Zeile
    im Wortlaut, Figuren eine zusammenfassende Zeile mit Namen, Begriffe und
    Fragen je eine Zeile.
    Journaleintraege (``verworfen``/``entschieden``) sowie Schalter,
    Interviewmodus und Umbenennungen bleiben still -- sonst waere der Chat
    zugespammt und die Meldungen wuerden ueberlesen. Gab es keine Aenderung
    am Arbeitsstand, gibt es keine Meldung: ``None``.

    Eine Entfernung (art ``entfernen``, NACHTRAG N3) bekommt eine Zeile mit
    eigenem Verb ("Entfernt: Figur Peter"): sie steht in derselben Meldung
    wie der Rest, weil eine Nachricht je Lauf die Regel ist, muss aber als
    Wegnahme lesbar sein und nicht als Zuwachs.

    Eine Phasenaenderung bekommt ihre eigene Zeile -- und sie kommt seit dem
    05.09.2026 nur noch aus einer Quelle: der Gruppe (art ``phase_setzen``).
    Den automatischen Sprung des Bots gab es einmal; er ist verworfen, weil
    ein Datenstand keine Absicht ist (interview_theater/phasen.py)."""
    kernthema = None
    formatwert = None
    rahmen = None
    hauptkonflikt = None
    begriffe = None
    fragen = None
    figuren_namen = []
    geplant = []
    korrigiert = []
    phase_gesetzt = None
    entfernt = []
    usa = None
    for aenderung in wirkliche_aenderungen:
        art = aenderung.get("art")
        wert = aenderung.get("wert", "")
        if art == "szene_usa":
            usa = wert
        elif art == "kernthema_setzen":
            kernthema = wert
        elif art == "format_setzen":
            formatwert = wert
        elif art == "rahmen_setzen":
            rahmen = wert
        elif art == "hauptkonflikt_setzen":
            hauptkonflikt = wert
        elif art == "begriffe_setzen":
            begriffe = wert
        elif art == "fragen_setzen":
            fragen = wert
        elif art == "figur_setzen":
            figuren_namen.append(wert)
        elif art == "szene_planen":
            geplant.append(wert)
        elif art == "transkript_korrigieren":
            korrigiert.append(wert)
        elif art == "phase_setzen":
            phase_gesetzt = phasen.nummer_fuer(wert)
        elif art == "entfernen":
            entfernt.append(wert)
        # verworfen/entschieden/wortlaut_an/wortlaut_aus/interview_benennen:
        # bewusst ignoriert, bleiben still (Aufgabe 4). szene_schreiben
        # ebenfalls -- es meldet sich selbst, mit einer Ankuendigung und
        # spaeter der fertigen Szene (interview_theater/szene.py). Und
        # figur_quelle_setzen aus demselben Grund: die Zeile, die zaehlt, ist
        # "Sprachprofil fuer Pola aus Interview 2: ..." und die kommt aus
        # interview_theater/sprachprofil.py, wenn das Profil wirklich steht.

    zeilen = []
    if kernthema:
        zeilen.append(f"Kernthema: {kernthema}")
    if formatwert:
        zeilen.append(f"Format: {formatwert}")
    if rahmen:
        zeilen.append(f"Rahmen: {rahmen}")
    if hauptkonflikt:
        zeilen.append(f"Hauptkonflikt: {hauptkonflikt}")
    if figuren_namen:
        zeilen.append(_figuren_zeile(figuren_namen))
    if begriffe:
        zeilen.append(f"Begriffe: {begriffe}")
    if fragen:
        zeilen.append(f"Fragen: {fragen}")
    # Eine geplante Szene bekommt ihre Kurzzeile ("Szene 1 · Dialog ·
    # Polizeikessel · Mira, Pola"): die Gruppe soll sehen, welche Szene
    # gemeint ist, ohne die ganze Planung noch einmal zu lesen.
    for zeile in geplant:
        zeilen.append(zeile)
    # Eine Transkriptkorrektur bekommt ihr eigenes Verb (N5): "Korrigiert:
    # gepoekt -> gepogt". Sie ist der Beleg dafuer, dass wirklich etwas
    # passiert ist -- im Probelauf sagte der Bot dreimal "korrigiere ich",
    # und in der Datenbank aenderte sich nichts.
    for zeile in korrigiert:
        zeilen.append(f"Korrigiert: {zeile}")
    # Entfernungen stehen in derselben Meldung wie alles andere -- eine
    # Nachricht je Erkennerlauf bleibt die Regel (SPEC § 4.3). Sie tragen ihr
    # eigenes Verb, damit niemand "Notiert:" liest und denkt, es sei etwas
    # dazugekommen.
    for was in entfernt:
        zeilen.append(f"Entfernt: {was}")
    if phase_gesetzt is not None:
        zeilen.append(f"Wir sind jetzt bei {phasen.bezeichnung(phase_gesetzt)}.")
    if usa == "ja":
        zeilen.append("Szenentexte kommen ab jetzt vom US-Modell (Anthropic). Ich sage es vor jeder Szene nochmal.")
    elif usa == "nein":
        zeilen.append("Szenentexte bleiben in der Schweiz. Ich frage nicht wieder.")

    if not zeilen:
        return None

    zeilen.append("Falls das nicht stimmt, sagt es mir.")
    return "Notiert:\n" + "\n".join(zeilen)


def _interviewmodus_texte() -> dict[str, str]:
    """art -> Wortlaut der Interviewmodus-Bestaetigung (teil-b.md Aufgabe 5,
    § 10.1) -- die EINE Ausnahme von "nur Arbeitsstandaenderungen werden
    gemeldet": der Modus muss sichtbar sein, sonst weiss die Gruppe nicht, ob
    sie gerade aufnimmt. Bewusst getrennt von baue_meldung()/der
    Aenderungsmeldung, nicht mit ihr vermischt -- zwei kurze Nachrichten sind
    hier klarer als eine.

    Der Wortlaut ist seit dem 05.09.2026 **derselbe wie bei ``/aufnahme``**
    (``befehle._TEXT_INTERVIEW_AN``/``_AUS``) und wird von dort geholt statt
    hier zweitgepflegt: gesprochene Absicht und getippter Befehl schalten
    denselben Modus -- sie duerfen nicht verschieden aussehen, sonst wirkt es
    fuer die Gruppe wie zwei verschiedene Zustaende.

    Spaeter Import (in der Funktion, nicht im Modulkopf): ``befehle``
    importiert ``erkenner``, ein Modulimport hier waere ein Zyklus."""
    from interview_theater import befehle

    from interview_theater import knoepfe

    # ``interview_starten`` traegt seit 05.09.2026 NICHT mehr die
    # Startbestaetigung (der Modus laeuft ja noch gar nicht), sondern die
    # Ablauf-Erklaerung vor dem Start -- der Knopf darunter schaltet ein.
    return {
        "interview_starten": knoepfe.TEXT_ABLAUF,
        "interview_beenden": befehle._TEXT_INTERVIEW_AUS,
    }


def _melde_interviewmodus(tg, conn, e, chat_id: int, wirkliche: list[dict]) -> None:
    """Bestaetigt jeden tatsaechlich wirksamen Moduswechsel einzeln und
    sofort (Aufgabe 5) -- unabhaengig von und vor baue_meldung(), das diese
    beiden Arten weiterhin bewusst still haelt.

    **Mit Knopf, seit 05.09.2026** (Birk, nach dem Live-Lauf 13:42): "der
    Knopf soll direkt kommen, ohne Slash-Befehl". Sagt die Gruppe "ich will
    noch eine Aufnahme machen", hing bis dahin nur Text im Chat -- den
    Umschalter gab es erst nach ``/aufnahme``. Die Bestaetigung geht deshalb
    ueber ``knoepfe.biete_aufnahme`` und nicht mehr ueber ``tg.sende``:
    derselbe Text, derselbe Umschalter, egal ob getippt oder gesprochen.

    Die Beschriftung richtet sich nach dem Zustand JETZT -- ``wende_an`` hat
    schon geschrieben, wenn wir hier ankommen, also steht nach einem
    ``interview_starten`` "Aufnahme beenden" auf dem Knopf. Genau richtig:
    der naechste Druck ist der, den die Gruppe als naechstes braucht.

    **Beim Start ist es kein Vollzug, sondern ein Angebot** (05.09.2026,
    Birk nach Gruppe 3): ``_wende_interview_starten_an`` schaltet nichts
    mehr ein, hier steht deshalb die Ablauf-Erklaerung
    (``knoepfe.TEXT_ABLAUF``) mit dem Knopf "Interview starten" darunter --
    erst sein Druck schaltet den Modus an. Beim Ende bleibt es beim
    bisherigen Weg: "Aufnahme beendet." mit dem Umschalter darunter."""
    from interview_theater import knoepfe  # spaeter Import, haelt den Modulkopf frei

    texte = _interviewmodus_texte()
    for aenderung in wirkliche:
        art = aenderung.get("art")
        text = texte.get(art)
        if text is None:
            continue
        try:
            message_id = knoepfe.biete_aufnahme(conn, tg, chat_id, text)
            repo.merke_nachricht(
                conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
                text, repo._jetzt(),
            )
        except Exception:
            log.exception(
                "Interviewmodus-Bestaetigung fehlgeschlagen, chat_id=%s, art=%s",
                chat_id, art,
            )


def _starte_szene(klm, tg, conn, e, chat_id: int, aenderungen: list[dict], wirkliche: list[dict] | None = None) -> None:
    """Stoesst den Szenen-Aufruf an, wenn der Erkenner einen Schreibauftrag
    gefunden hat (art ``szene_schreiben``, interview_theater/szene.py).

    Nicht in ``wende_an``, weil dort nur in die Datenbank geschrieben wird:
    hier faellt eine Nachricht in die Gruppe an und ein Sprachmodell-Aufruf,
    der Minuten dauert. ``szene.starte`` gibt ihn sofort an einen eigenen
    Thread ab -- der Erkenner-Nachlauf haengt nicht daran.

    Hoechstens EINE Szene je Lauf, auch wenn das Modell zwei Auftraege
    gefunden haben sollte: der zweite liefe ohnehin in die Sperre je chat_id
    und wuerde nur mit 'ich schreibe gerade noch' abgewiesen -- zwei
    Nachrichten fuer nichts."""
    from interview_theater import szene  # spaeter Import, haelt den Modulkopf frei

    auftrag = next(
        (a.get("wert") for a in aenderungen if a.get("art") == "szene_schreiben"), None
    )
    if not auftrag:
        # Die Gruppe hat auf das US-Angebot geantwortet (ja oder nein): der
        # Auftrag, der auf die Antwort gewartet hat, wird jetzt ausgefuehrt --
        # ueber den Weg, den die Antwort festgelegt hat. Nur, wenn die Antwort
        # WIRKSAM war (wirkliche), sonst zieht ein beliebiges "ja" im Chat
        # einen fremden Auftrag.
        if any(a.get("art") == "szene_usa" for a in (wirkliche or [])):
            auftrag = repo.hole_und_loesche_offenen_szenenauftrag(conn, chat_id)
    if not auftrag:
        return
    szene.starte(conn, tg, klm, e, chat_id, auftrag)


def _starte_sprachprofil(klm, tg, conn, e, chat_id: int, wirkliche: list[dict]) -> None:
    """Stoesst je bestaetigter Interview-Zuordnung einen Sprachprofil-Aufruf
    an (art ``figur_quelle_setzen``, interview_theater/sprachprofil.py).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``: dort
    wird nur in die Datenbank geschrieben, hier faellt ein
    Sprachmodell-Aufruf an und eine Nachricht in die Gruppe.
    ``sprachprofil.starte`` gibt beides sofort an einen eigenen Thread ab.

    Aus den **wirksamen** Aenderungen, nicht aus den erkannten: nur eine
    Zuordnung, die auch wirklich eine Figur und ein Interview getroffen hat,
    traegt eine ``figur_id`` -- und nur die soll einen bezahlten Aufruf
    ausloesen."""
    from interview_theater import sprachprofil  # spaeter Import, haelt den Modulkopf frei

    figur_ids = [
        a["figur_id"] for a in wirkliche
        if a.get("art") == "figur_quelle_setzen" and a.get("figur_id")
    ]
    if not figur_ids:
        return
    try:
        sprachprofil.starte(conn, tg, klm, e, chat_id, figur_ids)
    except Exception:
        log.exception("Sprachprofil konnte nicht gestartet werden, chat_id=%s", chat_id)


def _schliesse_interview_ab(klm, tg, conn, e, wirkliche: list[dict]) -> None:
    """Stoesst nach einem erkannten "fertig" das Zusammenfuegen und die eine
    Verdichtung des Interviews an (§ 10.6, ``aufnahme.starte_abschluss``).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``: dort
    wird nur in die Datenbank geschrieben, hier faellt ein
    Sprachmodell-Aufruf an und eine Nachricht in die Gruppe. Der Aufruf geht
    sofort an einen eigenen Thread -- der Erkenner-Nachlauf haengt nicht
    daran, und die Bestaetigung "Aufnahme beendet." steht laengst im Chat.

    Ein Fehlschlag hier darf die Meldung nicht mitreissen: der Modus ist schon
    aus, und der Nachhol-Arbeiter greift ein liegengebliebenes Interview beim
    naechsten Durchlauf ohnehin auf."""
    from interview_theater import aufnahme  # spaeter Import, haelt den Modulkopf frei

    kopf_id = next(
        (
            a.get("aufnahme_id")
            for a in wirkliche
            if a.get("art") == "interview_beenden" and a.get("aufnahme_id")
        ),
        None,
    )
    if kopf_id is None:
        return
    try:
        aufnahme.starte_abschluss(conn, tg, klm, e, kopf_id)
    except Exception:
        log.exception("Interviewabschluss konnte nicht gestartet werden, id=%s", kopf_id)


def laufe(klm, tg, conn, e, chat_id: int) -> None:
    """Kapselt den ganzen Absichtserkenner-Nachlauf: erkennen, anwenden,
    melden (teil-b.md Aufgabe 4), Interviewmodus bestaetigen (Aufgabe 5),
    beendetes Interview verdichten lassen (§ 10.6), Szenen-Auftrag anstossen
    (szene.py).

    Was hier seit dem 05.09.2026 NICHT mehr passiert: die Phase umschalten.
    Der automatische Sprung ist verworfen (Birk, nach dem Probelauf) --
    Datenstand ist nicht Absicht, und ein gesetztes Kernthema sagt nicht,
    dass die Gruppe mit dem Kernthema fertig ist. Die Phase setzt jetzt nur
    noch die Gruppe (``phase_setzen``, ``/phase``); erlaubt die Materiallage
    mehr, fragt der Bot im Gespraech danach (``phasen.offenes_angebot``).

    Laeuft nachgelagert, nachdem die Bot-Antwort in der Gruppe steht (SPEC
    § 4.3) -- niemand wartet darauf, und ein Fehlschlag bleibt fuer die
    Gruppe unsichtbar, genau wie ``ablauf.antworte`` es fuer den
    Gespraechszug haelt: geloggt und als ``vorfall`` vermerkt, nie eine
    zusaetzliche Fehlermeldung im Chat."""
    try:
        aenderungen = erkenne(klm, conn, e, chat_id)
        if not aenderungen:
            return
        wirkliche = wende_an(conn, e, chat_id, aenderungen)
        _melde_interviewmodus(tg, conn, e, chat_id, wirkliche)
        # Nach der Bestaetigung "Aufnahme beendet.": das Interview
        # zusammenfuegen und einmal verdichten (§ 10.6).
        _schliesse_interview_ab(klm, tg, conn, e, wirkliche)
        # Eine bestaetigte Interview-Zuordnung loest den einen
        # Sprachprofil-Aufruf aus (05.09.2026) -- in einem eigenen Thread.
        _starte_sprachprofil(klm, tg, conn, e, chat_id, wirkliche)
        # Aus den erkannten, nicht aus den wirksamen Aenderungen: ein
        # Szenenauftrag schreibt nichts in den Arbeitsstand und taucht in
        # ``wirkliche`` deshalb nie auf.
        _starte_szene(klm, tg, conn, e, chat_id, aenderungen, wirkliche)
        text = baue_meldung(wirkliche)
        if text is None:
            return
        message_id = tg.sende(chat_id, text)
        # Wie ablauf.antworte: die gesendete Meldung wird als Bot-Nachricht
        # mitgeschrieben, damit sie im naechsten Verlaufsfenster steht.
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Erkenner-Nachlauf fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "erkenner_nachlauf_fehler",
            "Erkenner-Nachlauf (anwenden/melden) fehlgeschlagen",
        )

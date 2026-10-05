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
from datetime import datetime, timezone

from interview_theater import kontext, phasen, repo, ruecknahme

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
    # Seit dem Umbau vom 05.09.2026 nachts: die Geschichte im Groben (Bogen
    # und Ende, Phase 5). Der Regelweg dorthin ist der Vorschlagsblock mit
    # seinen Knoepfen (``knoepfe._speichere_geschichte``) -- diese Art ist
    # der zweite, freie Weg: sagt die Gruppe die Geschichte einfach, wird sie
    # notiert wie jedes andere Arbeitsstandfeld.
    "geschichte_setzen",
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
    # Seit 30.09.2026 (Massnahme C10 aus
    # docs/analyse-phase5-chaos-2026-09-06.md): "mach das kuerzer". Wie
    # ``szene_schreiben`` ohne Schreibpfad -- sie stoesst eine Handlung an
    # (interview_theater/kuerzung.py) -- aber mit einem anderen Ziel: derselbe
    # Text wird KUERZER, er wird nicht neu.
    #
    # Der gemessene Anlass: am 06.09. gab es diesen Weg nicht, die
    # Kuerzungsbitte lief in den Gespraechszug, das Gespraechsmodell
    # antwortete mit einer neuen Szenenliste, und der Erkenner las sie als
    # ``szene_planen``. Aus drei Szenen wurden sechs.
    #
    # ``wert``: die Szenennummer als Zahl, oder leer -- dann ist die ganze
    # Kurzgeschichte gemeint. Auf "im Zweifel kein Eintrag" kalibriert wie
    # ``szene_schreiben``: es kostet einen minutenlangen, bezahlten Lauf.
    "szene_kuerzen",
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
    # Seit 06.09.2026 (docs/analyse-phase4-datenverlust-2026-09-06.md): die
    # Auffangart. Eine sachliche Festlegung, die in KEIN bestehendes Feld
    # passt, aber fuer Text oder Inszenierung zaehlt -- Gruppenzugehoerigkeit
    # einer Figur, ihre Herkunft, "nur eine Szene, erste Folge einer Serie",
    # eine Laengenvorgabe fuer Szenentexte. Bis dahin landete so etwas
    # hoechstens als ``entschieden``/``vorgeschlagen`` im Journal und fiel
    # nach acht weiteren Zeilen aus dem Prompt: von 42 Festlegungen einer
    # Gruppe in Phase 4 waren 22 faktisch verloren.
    "festlegung_setzen",
    # Padua-Brainstorming-Umbau (02.10.2026): die Anzahl Szenen ist ein
    # eigenes Arbeitsstandfeld (``arbeitsstand.szenen_anzahl``) und ein
    # fixes Feld von Phase 4 -- die Gruppe nennt die Zahl, der Bot schlaegt
    # sie nie vor (siehe ``prompts/phasen/4.md``).
    "szenenanzahl_setzen",
    # Padua Phasen TEIL 1 (03.10.2026): Rueckmeldung zur generierten
    # Geschichts-Uebersicht in Stufe A von Phase 5 (Prose Draft,
    # entwurf.py) -- "mach das Ende trauriger", "nochmal, anders", "die
    # Spannungskurve ist mir zu flach". Gilt NUR in Phase 5
    # (PHASEN_SPEZIFISCHE_ARTEN) und nur, solange die Uebersicht noch nicht
    # fixiert ist -- das prueft ``erkenner._starte_entwurf_uebersicht``
    # selbst (Final-Review-Fund, 03.10.2026: vorher stand das nur in diesem
    # Kommentar, ``entwurf.py`` hat ``geschichte_uebersicht_fixiert_am``
    # nirgends gelesen).
    # wert: die gewuenschte Richtung, oder leer ("") bei einem reinen
    # "nochmal"/"anders" ohne eigene Angabe.
    "uebersicht_aendern",
    # Padua Phasen TEIL 2 (03.10.2026, Flow-Audit B1/B2): "Chat wirkt, wo
    # Knoepfe wirken". Alle fuenf nur mit ``workshop.ueberarbeitung_aktiv()``
    # (PROFILSCHALTER_DER_ARTEN) und phasengebunden (PHASEN_SPEZIFISCHE_ARTEN);
    # beschrieben nur im englischen Prompt (Punkte 27-31).
    # Rueckmeldung zum gezeigten Text (6/7) -> ueberarbeitung.ueberarbeite.
    "text_ueberarbeiten",
    # "yes, save" im Chat -> dieselbe Funktion wie der Knopf (ueberarbeitung.nimm_ab).
    "fassung_abnehmen",
    # Die Antwort auf die Formwahl-Liste (7): schreibt szene.form je Nummer.
    "formen_setzen",
    # Eine Sprechweise je Figur (7): schreibt figur.sprachstil.
    "sprechweise_setzen",
    # Entscheidung zu einem Schaerfungs-Vorschlag (5), wie die Schaerfungs-Knoepfe.
    "schaerfung_entscheidung",
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

#: Welche Phase eine ART tatsaechlich wirken laesst -- als Tabelle, nicht als
#: verstreute if/elif-Kette (Padua Phasen TEIL 1, 03.10.2026). Eine ART, die
#: hier NICHT auftaucht, gilt wie bisher in jeder Phase (alle 23 arts, die es
#: vor diesem Umbau schon gab, bleiben unveraendert phasenfrei). Dieser Platz
#: ist fuer kuenftige Karten gedacht -- z. B. eine Phase-7-spezifische
#: Revisions-art aus dem Flow-Audit (``git show feat/flow-audit:docs/
#: flow-audit/vorlagen.md``) wuerde hier einen weiteren Eintrag bekommen,
#: nicht einen weiteren Codepfad.
PHASEN_SPEZIFISCHE_ARTEN: dict[str, tuple[int, ...]] = {
    # Padua Phasen TEIL 1: die Uebersicht in Stufe A von Phase 5 (Prose
    # Draft) darf nur dort geaendert werden -- ausserhalb der Phase, oder
    # nachdem sie fixiert ist, ist ein "aendere die Uebersicht" etwas
    # anderes gemeint (siehe entwurf.py).
    "uebersicht_aendern": (5,),
    # Padua Phasen TEIL 2 (03.10.2026)
    "text_ueberarbeiten": (6, 7),
    "fassung_abnehmen": (5, 6, 7),
    "formen_setzen": (7,),
    "sprechweise_setzen": (7,),
    "schaerfung_entscheidung": (5,),
}

#: Welcher Profilschalter eine ART ueberhaupt erst freischaltet -- dieselbe
#: Tabelle, eine zweite Spalte. Eine ART ohne Eintrag ist profilfrei. Ohne
#: Schalter steht die ART auch nicht im Schema (``arten_fuer_schema``):
#: Dortmund sieht dieselbe Enum-Liste wie vor TEIL 2.
PROFILSCHALTER_DER_ARTEN: dict[str, str] = {
    "text_ueberarbeiten": "ueberarbeitung",
    "fassung_abnehmen": "ueberarbeitung",
    "formen_setzen": "ueberarbeitung",
    "sprechweise_setzen": "ueberarbeitung",
    "schaerfung_entscheidung": "ueberarbeitung",
    # Padua Modellwahl-Nachtrag (04.10.2026): das GEGENSTUECK zu den
    # ueberarbeitung-Arten oben -- dort ist die Vorgabe AUS (Dortmund/
    # Vorgabe sieht nichts), hier ist die Vorgabe AN (die Einwilligungsfrage
    # wird gestellt, Dortmund/Vorgabe unveraendert). Padua schaltet sie AUS:
    # ohne Einwilligungsfrage gibt es auch nichts mehr zu beantworten.
    "szene_usa": "einwilligung",
}


def _ueberarbeitung_an() -> bool:
    from interview_theater import workshop

    return workshop.ueberarbeitung_aktiv()


def _einwilligung_an() -> bool:
    from interview_theater import workshop

    return workshop.modellwahl_einwilligung_aktiv()


_SCHALTER = {
    "ueberarbeitung": _ueberarbeitung_an,
    "einwilligung": _einwilligung_an,
}


def _schalter_an(art: str) -> bool:
    """Ist der Profilschalter dieser ART an? Ohne Eintrag: immer."""
    name = PROFILSCHALTER_DER_ARTEN.get(art)
    return name is None or _SCHALTER[name]()


def arten_fuer_schema() -> list[str]:
    """Die Arten im Schema-Enum des Erkenneraufrufs -- je Profil, bei jedem
    Aufruf frisch (zwei Profile in einem Prozess, D.5 der Profil-Analyse)."""
    return [a for a in ARTEN if _schalter_an(a)]


def _ist_phasenpassend(conn, chat_id: int, art: str) -> bool:
    """True, wenn diese art in der aktuellen Phase ueberhaupt wirken darf.

    Reine Tabellen-Abfrage (``PHASEN_SPEZIFISCHE_ARTEN``), kein
    Modellaufruf, kein eigenes SQL -- wie jede andere Wache in diesem Modul
    (``waechter_filter``). Eine art, die nicht in der Tabelle steht, ist
    ueberall erlaubt: das ist der unveraenderte Normalfall. Seit TEIL 2
    zusaetzlich: ohne ihren Profilschalter wirkt eine art nirgends."""
    if not _schalter_an(art):
        return False
    phasen_liste = PHASEN_SPEZIFISCHE_ARTEN.get(art)
    if phasen_liste is None:
        return True
    return phasen.aktuelle(conn, chat_id) in phasen_liste


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
def _baue_schema(arten) -> dict:
    return {
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
                        "art": {"type": "string", "enum": list(arten)},
                        "wert": {"type": "string"},
                    },
                },
            },
        },
    }


#: Das Schema ohne profilgebundene Arten -- unveraendert der Wert von vor
#: TEIL 2 (die 27 profilfreien Arten). Der Erkenneraufruf selbst nimmt
#: ``schema()``, das je Profil die freigeschalteten Arten dazunimmt.
SCHEMA = _baue_schema(a for a in ARTEN if a not in PROFILSCHALTER_DER_ARTEN)


def schema() -> dict:
    """Das Schema des Erkenneraufrufs im aktiven Profil (TEIL 2): ohne
    Schalter gleich ``SCHEMA``."""
    return _baue_schema(arten_fuer_schema())


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
        beschriftung = T._STAND_BESCHRIFTUNG
        for feld in beschriftung:
            if stand[feld]:
                zeilen.append(f"{beschriftung[feld]}: {stand[feld]}")
    for figur in figuren:
        beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
        zeilen.append(T._STAND_FIGUR_ZEILE.format(name=figur["name"], beschreibung=beschreibung))

    if not zeilen:
        return ""
    return T._ARBEITSSTAND_KOPF + "\n".join(zeilen)


#: Die Koepfe des Nutzertexts (W3: ein englischer Systemprompt mit deutschem
#: Nutzertext liesse das Modell deutsch antworten). ``_STAND_BESCHRIFTUNG``:
#: Arbeitsstandfeld -> Beschriftung, in dieser Reihenfolge; die Schluessel
#: sind Spaltennamen (Protokoll), uebersetzt werden nur die Werte.
_STAND_BESCHRIFTUNG = {
    "begriffe": "Begriffe",
    "fragen": "Fragen",
    "kernthema": "Kernthema",
    "rahmen": "Rahmen",
    "hauptkonflikt": "Hauptkonflikt",
}
_STAND_FIGUR_ZEILE = "Figur {name}{beschreibung}"
_ARBEITSSTAND_KOPF = "Arbeitsstand:\n"
_NACHRICHTEN_KOPF = "Neue Nachrichten:\n"
_VORLAUF_KOPF = (
    "Vorlauf (die letzte Bot-Nachricht davor -- schon verarbeitet, nur "
    "damit du siehst, worauf sich eine Zustimmung bezieht):\n"
)


def _nachrichten_text(nachrichten, vorlauf=None, namen=None) -> str:
    """``namen``: Pseudonyme aus ``kontext.pseudonyme`` (E8), ``None`` =
    Vornamen wie bisher."""
    zeilen = [kontext.sprecherzeile(n, namen) for n in nachrichten]
    text = T._NACHRICHTEN_KOPF + "\n".join(zeilen)
    if vorlauf is not None:
        text = T._VORLAUF_KOPF + kontext.sprecherzeile(vorlauf, namen) + "\n\n" + text
    return text


def _baue_nutzertext(conn, chat_id: int, nachrichten, vorlauf=None) -> str:
    """Baut den Nutzertext des Erkenneraufrufs: aktueller Arbeitsstand plus
    die neuen Nachrichten seit dem Wasserzeichen -- nicht das Journal, nicht
    die Transkripte (SPEC § 4.3). Seit 05.09. mit Vorlauf (letzte
    Bot-Nachricht vor dem Fenster), siehe ``erkenne``."""
    namen = kontext.pseudonyme(
        conn, chat_id, list(nachrichten) + ([vorlauf] if vorlauf is not None else [])
    )
    bloecke = [b for b in (_arbeitsstand_text(conn, chat_id),
                           _nachrichten_text(nachrichten, vorlauf, namen)) if b]
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
            chat_id, prompt(), nutzer, schema(), "erkenner",
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
    return f"{T._AUFNAHME_KOPF}\n{(transkript or '').strip()}"


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
            chat_id, prompt(), baue_aufnahme_nutzertext(text), schema(), "erkenner",
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


def wende_aus_aufnahme_an(klm, tg, conn, e, chat_id: int, aenderungen: list[dict]) -> int | None:
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
    beendet." samt Verdichtung ist die Rueckmeldung, die zaehlt.

    Liefert die ``aufnahme_id`` des Interviews, dessen Abschluss hier
    angestossen wurde, sonst None -- damit ``aufnahme._teil_abschliessen``
    denselben Abschluss nicht ein zweites Mal ruft."""
    if not aenderungen:
        return None
    wirkliche = wende_an(conn, e, chat_id, aenderungen)
    _melde_interviewmodus(tg, conn, e, chat_id, wirkliche)
    return _schliesse_interview_ab(klm, tg, conn, e, wirkliche)


#: art -> Arbeitsstand-Feld fuer die Aenderungsarten, die ein einzelnes
#: Feld ueberschreiben (SPEC § 4.3 'Ueberschreiben ist der Normalfall').
_ARBEITSSTAND_ARTEN = {
    "begriffe_setzen": "begriffe",
    "fragen_setzen": "fragen",
    "kernthema_setzen": "kernthema",
    "format_setzen": "format",
    "rahmen_setzen": "rahmen",
    "geschichte_setzen": "geschichte",
    "hauptkonflikt_setzen": "hauptkonflikt",
}


#: Woran ein Handlungstext erkennbar ist, der faelschlich als Setting
#: (``rahmen``) gespeichert werden soll (06.09.2026, Birk 11:42). Zwei
#: Merkmale, beide aus dem Live-Fall: eine ausdrueckliche Ende-Angabe und
#: schiere Laenge -- ein Setting ist "Ort, Zeit, Anlass", kein Absatz.
_GESCHICHTE_MARKER = re.compile(
    r"\bEnde\s*:|\bam Ende\b|\bzum Schluss\b|\bdann\b.*\bdann\b", re.IGNORECASE
)
#: Dasselbe auf Englisch (Karte A1, K5) -- gelesen wird die Vereinigung.
_GESCHICHTE_MARKER_EN = re.compile(
    r"\bEnd(?:ing)?\s*:|\bin the end\b|\bthen\b.*\bthen\b", re.IGNORECASE
)
#: Ab hier ist es kein Setting mehr, sondern eine Erzaehlung.
RAHMEN_HOECHSTLAENGE = 300


def _ist_geschichte(wert: str) -> bool:
    """Sieht dieser Text nach der Handlung aus statt nach dem Setting?"""
    roh = (wert or "").strip()
    return (len(roh) > RAHMEN_HOECHSTLAENGE
            or _GESCHICHTE_MARKER.search(roh) is not None
            or _GESCHICHTE_MARKER_EN.search(roh) is not None)


def _wende_arbeitsstand_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Ueberschreibt ein Arbeitsstand-Feld -- aber nur, wenn sich der Wert
    tatsaechlich aendert (die wichtigste Regel aus Aufgabe 3: derselbe Wert
    ist keine Aenderung, sonst meldete Aufgabe 4 bei jedem Zug dasselbe
    Kernthema erneut)."""
    wert = wert.strip()
    if not wert:
        return None
    feld = _ARBEITSSTAND_ARTEN[art]
    if feld == "fragen":
        # Waehrend die Stufe "Fragen einzeln durchgehen" laeuft (Fund
        # 02.10.2026, Padua-Live, web_post 73/74, aufnahme 70): der
        # Erkenner-Lauf, der nach einer Schaerfung (oder irgendeinem
        # Modellzug waehrend ``fragen_aktuell`` gesetzt ist) anlaeuft, darf
        # ``fragen`` NICHT schreiben -- fragen.knoepfe._schliesse_fragen_ab
        # ist die einzige Stelle, die dieses Feld setzt, und sie tut es erst
        # NACH der letzten Entscheidung. Ein ``fragen_setzen`` aus dem
        # Erkenner waehrend dieser Stufe wuerde die ganze Liste durch eine
        # einzelne VORSCHLAG-FRAGE-Zeile ersetzen (genau der Live-Befund).
        from interview_theater import knoepfe

        if knoepfe.einzeln_aktiv(conn, chat_id):
            log.info(
                "fragen_setzen waehrend 'Fragen einzeln durchgehen' "
                "verworfen, chat_id=%s", chat_id,
            )
            return None
        if _fragen_sammeln(conn, chat_id):
            return _haenge_fragen_an(conn, chat_id, art, wert)
    if feld == "rahmen" and _ist_geschichte(wert):
        # **Der Rahmen ist das SETTING, nicht die Handlung** (06.09.2026,
        # Birk 11:42, live gemessen: der Erkenner schrieb einen
        # Geschichte-Vorschlag in ``rahmen``, und das Setting war um die
        # ganze Handlung erweitert). Abgefangen wird das hier in der
        # Auswertung und nicht im Prompt -- ``erkenner.md`` ist ohne
        # Korpuslauf nicht anzufassen.
        log.info("rahmen_setzen sah nach Handlung aus, verworfen: %r", wert[:80])
        repo.merke_vorfall(
            conn, chat_id, None, "rahmen_war_geschichte",
            "Ein Geschichte-Text sollte in den Rahmen geschrieben werden",
        )
        return None
    stand = repo.hole_arbeitsstand(conn, chat_id)
    aktuell = stand[feld] if stand else None
    if aktuell == wert:
        return None
    repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    if feld == "begriffe":
        # Karte t_4517d4ad (D7): je Begriff die Zeile des Begriffsboards.
        from interview_theater import begriffsboard

        begriffsboard.schreibe_detail(conn, chat_id, wert)
    return {"art": art, "wert": wert}


def _fragen_sammeln(conn, chat_id: int) -> bool:
    """Padua Phase 1/2 (``workshop.autosave_phase1_2_aktiv``): ein
    ``fragen_setzen`` haengt an statt zu ueberschreiben (Live-Befund
    05.10.2026, Gruppe 2: zwei bestaetigte Fragen nacheinander, im Feld stand
    nur die zweite). Dort bestaetigt die Gruppe Frage fuer Frage, und jede
    📌-Zeile meint EINE Frage, nicht die ganze Liste. Dortmund und das
    Vorgabeprofil ueberschreiben wie bisher."""
    from interview_theater import phasen, workshop

    return (
        workshop.autosave_phase1_2_aktiv()
        and phasen.aktuelle(conn, chat_id) in (1, 2)
    )


def _fragen_teile(zeile: str) -> tuple[str, str | None, str]:
    """Zerlegt eine Fragezeile in (ganze Zeile, Thema oder None, Frage),
    jeweils normalisiert (Gross-/Kleinschreibung und Leerraum egal). Ein
    Doppelpunkt, vor dem schon ein Fragezeichen steht, trennt kein Thema ab."""
    def normal(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()

    ganz = normal(zeile)
    thema, trenner, frage = zeile.partition(":")
    if trenner and "?" not in thema and normal(thema) and normal(frage):
        return ganz, normal(thema), normal(frage)
    return ganz, None, ganz


def _ist_fragen_dublette(neu: tuple, alt: tuple) -> bool:
    """Ist die Zeile ``neu`` dieselbe Frage wie ``alt`` (beide aus
    ``_fragen_teile``)?

    P2-H3 (T10, 05.10.2026): nach "Questions saved" las der Erkenner die
    Liste im Verlauf erneut und schrieb dieselbe Frage unter einem anderen
    Themenwort ("Mars: ..." statt "Living on mars: ...") oder ganz ohne. Der
    Abgleich ueber die ganze Zeile hielt sie fuer neu, haengte sie doppelt an
    und schickte den "Noted:"-Block ein zweites Mal.

    T10-Review: dieselbe Frage unter einem FREMDEN Begriff ("Robots: How
    would that feel for you?" / "Mars: How would that feel for you?") ist
    eine eigene Frage. Die Frage allein zaehlt deshalb nur, wenn einer Seite
    das Thema fehlt oder die Themen verwandt sind (eines steckt im anderen,
    "mars" in "living on mars")."""
    if neu[0] == alt[0]:
        return True
    if neu[2] != alt[2]:
        return False
    if neu[1] is None or alt[1] is None:
        return True
    return neu[1] in alt[1] or alt[1] in neu[1]


def _haenge_fragen_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """Haengt jede Zeile von ``wert``, die noch nicht in ``fragen`` steht
    (Gross-/Kleinschreibung und Leerraum egal), als eigene Zeile an.

    Gemeldet wird nur das Neue -- die 📌-Zeile nennt die eine bestaetigte
    Frage, nicht die ganze Liste. Undo braucht keinen eigenen Weg: der
    Schnappschuss um ``wende_an`` stellt genau den Stand vor diesem Lauf
    wieder her, also faellt genau die zuletzt angehaengte Frage weg."""
    from interview_theater import vorschlag

    stand = repo.hole_arbeitsstand(conn, chat_id)
    bisher = vorschlag.zeilen((stand["fragen"] if stand else None) or "")
    gesehen = [_fragen_teile(z) for z in bisher]
    neu = []
    for zeile in vorschlag.zeilen(wert):
        teile = _fragen_teile(zeile)
        if any(_ist_fragen_dublette(teile, alt) for alt in gesehen):
            continue
        gesehen.append(teile)
        neu.append(zeile)
    if not neu:
        return None
    repo.setze_arbeitsstand(conn, chat_id, "fragen", "\n".join(bisher + neu))
    return {"art": art, "wert": "\n".join(neu)}


#: Anzahl Szenen: vernuenftige Grenzen fuer einen Workshop-Abend.
SZENENANZAHL_MIN = 1
SZENENANZAHL_MAX = 20


def _wende_szenenanzahl_an(conn, chat_id: int, wert: str) -> dict | None:
    """Padua-Brainstorming-Umbau (02.10.2026): die Gruppe nennt die Anzahl
    Szenen selbst, der Bot schlaegt sie nie vor (``prompts/phasen/4.md``).
    Gespeichert wird die blanke Zahl als Text, wie jedes andere
    Arbeitsstandfeld. Steht keine plausible Zahl im Wert, wird nichts
    geschrieben -- geraten wird nicht."""
    treffer = re.search(r"\d+", wert or "")
    if treffer is None:
        return None
    zahl = int(treffer.group())
    if not (SZENENANZAHL_MIN <= zahl <= SZENENANZAHL_MAX):
        return None
    stand = repo.hole_arbeitsstand(conn, chat_id)
    aktuell = stand["szenen_anzahl"] if stand else None
    if aktuell == str(zahl):
        return None
    repo.setze_arbeitsstand(conn, chat_id, "szenen_anzahl", str(zahl))
    return {"art": "szenenanzahl_setzen", "wert": str(zahl)}


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
    if treffer is None:
        _schmelze_platzhalter_ein(conn, chat_id, name, beschreibung)
    return {"art": "figur_setzen", "wert": name}


def _schmelze_platzhalter_ein(
    conn, chat_id: int, name: str, beschreibung: str
) -> None:
    """Wurde hier gerade ein Platzhalter NACHBENANNT? Dann verschmelzen die
    beiden Zeilen (06.09.2026, B3 der Phase-4-Analyse).

    Das Signal ist die **wortgleiche Beschreibung**: der Bot legt den
    Platzhalter mit einem Merkmalssatz an ("laesst sich nichts gefallen,
    redet zurueck"), die Gruppe liefert spaeter den Namen dazu, und der
    Erkenner traegt beides zusammen ein -- Name aus dem Chat, Beschreibung
    aus dem Vorschlag. Live entstanden so drei Paare mit identischer
    Beschreibung, und die Arbeit (der Sprachstil) blieb am Platzhalter
    haengen.

    **Nur ein Platzhalter wird eingeschmolzen** (``ist_platzhaltername``),
    nie zwei benannte Figuren: zwei Namen mit zufaellig gleicher
    Beschreibung sind zwei Figuren, und sie zu verschmelzen waere derselbe
    stille Verlust in der anderen Richtung. Ohne Beschreibung passiert gar
    nichts -- dann gibt es kein Signal, und geraten wird hier nicht."""
    beschreibung = " ".join((beschreibung or "").split()).lower()
    if not beschreibung:
        return
    neu = repo.hole_figur(conn, chat_id, name)
    if neu is None:
        return
    platzhalter = next(
        (
            f for f in repo.figuren(conn, chat_id)
            if f["id"] != neu["id"]
            and repo.ist_platzhaltername(f["name"])
            and " ".join((f["beschreibung"] or "").split()).lower() == beschreibung
        ),
        None,
    )
    if platzhalter is None:
        return
    alter_name = repo.fuehre_figur_zusammen(conn, chat_id, platzhalter["id"], neu["id"])
    if alter_name is None:
        return
    log.info("Platzhalter %r in %r eingeschmolzen, chat_id=%s",
             alter_name, neu["name"], chat_id)
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        T._JOURNAL_ZUSAMMENGEFUEHRT.format(alt=alter_name, neu=neu["name"]),
        quelle="erkenner",
    )


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
        conn, chat_id, "entschieden", T._JOURNAL_KORRIGIERT.format(text=text),
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
        # E8: die Notiert-Zeile kommt als Bot-Zeile zurueck in die Fenster
        # von Erkenner und Journal -- in Padua deshalb "Interview N".
        "wert": f"{figur['name']}: {aufnahme.anzeigename(conn, kopf, 'Interview')}",
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
        if feld == "form":
            # **Die Form ist ein Vorschlag, keine Vorentscheidung** (Birk,
            # 06.09.2026: "Die Form Monolog habe ich niemals eingegeben und
            # aktiv bestaetigt"). ``szene.form`` schreibt allein der
            # Form-Knopf (``knoepfe`` ART_SZENENFORM). Was der Erkenner in
            # einem Planungssatz hoert, geht deshalb nach
            # ``form_vorschlag`` -- die Gruppe bestaetigt sie danach Szene
            # fuer Szene.
            #
            # Gemessen 06.09. im Lauf tag1-gruppe2: vier Szenen bekamen ihre
            # Form ueber diesen Pfad gesetzt, keine einzige wurde bestaetigt
            # (Kennzahl ``form_bestaetigt`` 0/4). Der Knopf war gebaut und
            # kam nie zum Zug, weil das Feld schon voll war.
            feld = "form_vorschlag"
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


#: Die Arbeitsstandfelder, gegen die eine Festlegung auf Redundanz geprueft
#: wird (Analyse § 4.4 Risiko 2, "Doppelte Wahrheit"). Ein Fakt hat genau
#: eine Stelle im Prompt -- steht er an zweien, ist eine davon zu loeschen
#: (docs/agents/entscheidungen.md, "Prompts werden nicht gelesen, sondern erzeugt und gemessen").
_FESTLEGUNG_GEGENPROBE = (
    "rahmen", "geschichte", "kernthema", "hauptkonflikt", "format",
    "begriffe", "fragen",
)


def _steht_schon_in_einem_feld(conn, chat_id: int, text: str) -> bool:
    """Traegt ein Arbeitsstandfeld diesen Text schon?

    Verglichen wird auf Teilzeichenkette nach Normalisierung, und nur in
    einer Richtung: die Festlegung steckt im Feld. Andersherum -- das Feld
    steckt in der laengeren Festlegung -- ist sie eine Ergaenzung und
    gehoert genau hierher."""
    nadel = " ".join((text or "").lower().split())
    if not nadel:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return False
    schluessel = set(stand.keys())
    return any(
        nadel in " ".join((stand[feld] or "").lower().split())
        for feld in _FESTLEGUNG_GEGENPROBE
        if feld in schluessel and stand[feld]
    )


def _zerlege_festlegung(wert: str) -> tuple[str, str | None, str]:
    """``"figur/Kassandra: 19 Jahre"`` -> ``("figur", "Kassandra", "19 Jahre")``.

    Ohne Doppelpunkt gibt es keinen Bereich, und das ist kein Fehler,
    sondern der haeufigste Fall von "passt in kein Fach": der ganze Wert
    wird der Text, der Bereich ``sonstiges``. Lieber im falschen Fach als
    verloren -- genau darum geht es bei dieser Tabelle."""
    roh = (wert or "").strip()
    kopf, trenner, text = roh.partition(":")
    if not trenner:
        return "sonstiges", None, roh
    if not text.strip():
        # Ein Kopf ohne Text ist keine Festlegung, sondern eine angefangene:
        # der Aufrufer schreibt bei leerem Text nichts.
        return "sonstiges", None, ""
    bereich, _, bezug = kopf.partition("/")
    return (
        repo.normiere_bereich(bereich),
        bezug.strip() or None,
        text.strip(),
    )


#: Woerter, die eine Festlegung ohne eigenen Inhalt tragen kann, ohne dass
#: ihr Fehlen etwas beweist: Fuellwoerter, Zaehlwoerter und die generischen
#: Sammelbegriffe, mit denen ein Modell eine blosse Zugehoerigkeit umschreibt
#: ("eine der beiden Gruppen", "(no description)"). Bleibt nach Abzug dieser
#: Woerter UND des Bezugsnamens nichts mehr stehen, war die Zeile reine
#: Wiederholung (02.10.2026, Fall fl03 -- der Prompt allein hielt das trotz
#: Gegenbeispiel nicht, siehe erkenner.md "keine Zeile ohne Inhalt").
_FESTLEGUNG_FUELLWOERTER = {
    "ist", "sind", "die", "der", "das", "von", "fuer", "und", "ein", "eine",
    "einer", "andere", "anderen", "zweite", "dritte", "erste", "letzte",
    "beiden", "zwei", "drei", "vier", "fuenf", "sechs",
    "gruppe", "gruppen", "lager", "fraktion", "fraktionen",
    "keine", "beschreibung", "unbekannt", "the", "is", "are", "of", "one",
    "other", "two", "three", "four", "five", "group", "groups", "no",
    "description", "n", "a",
}


def _ohne_eigenen_inhalt(text: str, bezug: str | None) -> bool:
    """Bleibt nichts als Fuellwoerter und der Bezugsname selbst, ist die
    Zeile eine reine Wiederholung ("die Stillen: eine der beiden Gruppen"),
    kein eigener Fakt. Eng gefasst, damit eine knappe aber echte Angabe
    ("Markenklamotten") nicht mitgerissen wird."""
    woerter = re.findall(r"[^\W\d]+", (text or "").lower(), re.UNICODE)
    bezugsworte = set(re.findall(r"[^\W\d]+", (bezug or "").lower(), re.UNICODE))
    rest = [
        w for w in woerter
        if w not in _FESTLEGUNG_FUELLWOERTER and w not in bezugsworte
    ]
    return bool(woerter) and not rest


def _wende_festlegung_an(conn, chat_id: int, wert: str) -> dict | None:
    """Legt eine Festlegung in der Auffangtabelle ab (art
    ``festlegung_setzen``, 06.09.2026).

    Drei Faelle schreiben nichts: ein leerer Text, einer, der in einem
    Arbeitsstandfeld ohnehin schon steht, und einer ohne eigenen Inhalt
    (``_ohne_eigenen_inhalt``). Der zweite ist das Gegenstueck zu
    ``_ist_geschichte`` weiter oben, nur in der anderen Richtung: dort wird
    eine Handlung aus dem Setting-Feld herausgehalten, hier ein Setting aus
    der Auffangtabelle. Alle drei Pruefungen stehen in der Auswertung und
    nicht im Prompt, weil ``erkenner.md`` ohne Korpuslauf nicht anzufassen
    ist -- und weil ein Prompt bittet, wo Code durchsetzt."""
    bereich, bezug, text = _zerlege_festlegung(wert)
    text = " ".join((text or "").split())
    if not text:
        return None
    if _steht_schon_in_einem_feld(conn, chat_id, text):
        log.info("Festlegung stand schon in einem Feld, verworfen: %r", text[:80])
        repo.merke_vorfall(
            conn, chat_id, None, "festlegung_stand_schon_im_feld",
            "Eine Festlegung wiederholte ein gesetztes Arbeitsstandfeld",
        )
        return None
    if _ohne_eigenen_inhalt(text, bezug):
        log.info("Festlegung ohne eigenen Inhalt, verworfen: %r", text[:80])
        repo.merke_vorfall(
            conn, chat_id, None, "festlegung_ohne_inhalt",
            "Eine Festlegung wiederholte nur die Zugehoerigkeit, ohne eigenen Fakt",
        )
        return None
    if repo.schreibe_festlegung(conn, chat_id, bereich, text, bezug=bezug) is None:
        return None
    return {
        "art": "festlegung_setzen",
        "wert": repo.festlegungszeile(bereich, bezug, text),
        "bereich": bereich,
        "bezug": bezug,
        "text": text,
    }


#: Zahlwoerter, die die Gruppe statt einer Ziffer sagt. Bis zwoelf, weil der
#: Knopf (``knoepfe.FIGURENZAHLEN``) nicht weiter geht -- eine Zahl darueber
#: ist keine Figurenliste mehr, sondern ein Missverstaendnis.
_ZAHLWOERTER = {
    "eine": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fuenf": 5,
    "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwoelf": 12, "zwölf": 12,
}

#: Eine Figurenzahl in einer Journalzeile: eine Zahl (oder eine Spanne "10
#: bis 12") vor dem Wort "Figuren".
#:
#: **Nicht** vor "Hauptfiguren" oder "Nebenfiguren": live wurden beide
#: getrennt gezaehlt ("2 bis 3 Hauptfiguren", "5 Nebenfiguren"), und eine
#: Teilzahl als Gesamtzahl waere schlechter als gar keine. Der negative
#: Lookahead sitzt deshalb vor dem Wortstamm.
_FIGURENZAHL = re.compile(
    r"\b(\d{1,2}|" + "|".join(_ZAHLWOERTER) + r")\b"
    r"(?:\s*(?:bis|-|–|—)\s*(\d{1,2}|" + "|".join(_ZAHLWOERTER) + r")\b)?"
    r"[^.,;]{0,20}?\s(?!haupt|neben)figuren\b",
    re.IGNORECASE,
)

#: Die andere Richtung: "Die Figurenanzahl ist 6".
_FIGURENZAHL_UMGEKEHRT = re.compile(
    r"\bfigurenanzahl\b[^\d]{0,20}(\d{1,2})\b", re.IGNORECASE
)

#: Dasselbe auf Englisch (Karte A1, K5): "three characters", "four to five
#: characters", "number of characters is 6". Das Ergebnis bleibt im
#: deutschen Format ("4 bis 5") -- Protokoll zum Arbeitsstand.
_ZAHLWOERTER_EN = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
#: Statt des Lookaheads vor dem Wortstamm ("Hauptfiguren" ist ein Wort)
#: stehen im Englischen Lookbehinds vor dem Leerzeichen: "2 main characters"
#: sind zwei Woerter, und eine Teilzahl als Gesamtzahl waere falsch.
_FIGURENZAHL_EN = re.compile(
    r"\b(\d{1,2}|" + "|".join(_ZAHLWOERTER_EN) + r")\b"
    r"(?:\s*(?:to|-|–|—)\s*(\d{1,2}|" + "|".join(_ZAHLWOERTER_EN) + r")\b)?"
    r"[^.,;]{0,20}?(?<!main)(?<!side)(?<!minor)(?<!supporting)\scharacters?\b",
    re.IGNORECASE,
)
_FIGURENZAHL_UMGEKEHRT_EN = re.compile(
    r"\bnumber of characters\b[^\d]{0,20}(\d{1,2})\b", re.IGNORECASE
)


def _zahl(wort: str) -> int | None:
    wort = (wort or "").strip().lower()
    if wort.isdigit():
        return int(wort)
    zahl = _ZAHLWOERTER.get(wort)
    return zahl if zahl is not None else _ZAHLWOERTER_EN.get(wort)


def figurenzahl_aus(text: str) -> str | None:
    """Liest eine Gesamt-Figurenzahl aus einem Satz, oder ``None``.

    Liefert sie in der Form, in der ``arbeitsstand.figuren_anzahl`` sie
    traegt: ``"8"`` oder ``"10 bis 12"``. Rein deterministisch, kein
    Modellaufruf -- der Satz liegt schon vor."""
    roh = text or ""
    # Deutsch zuerst (beide Richtungen), dann Englisch (Karte A1, K5).
    for vorwaerts, umgekehrt in ((_FIGURENZAHL, _FIGURENZAHL_UMGEKEHRT),
                                 (_FIGURENZAHL_EN, _FIGURENZAHL_UMGEKEHRT_EN)):
        treffer = vorwaerts.search(roh)
        if treffer is not None:
            erste = _zahl(treffer.group(1))
            zweite = _zahl(treffer.group(2)) if treffer.group(2) else None
            if erste is None or not 1 <= erste <= 12:
                return None
            if zweite is not None and 1 <= zweite <= 12 and zweite != erste:
                return f"{erste} bis {zweite}"
            return str(erste)
        treffer = umgekehrt.search(roh)
        if treffer is not None and 1 <= int(treffer.group(1)) <= 12:
            return treffer.group(1)
    return None


def _wende_journal_an(conn, chat_id: int, art: str, wert: str) -> dict | None:
    """``verworfen``/``entschieden`` haengen eine Journalzeile an -- nie in
    den Arbeitsstand (SPEC § 4.3: 'Journaleintraege fallen hier mit ab').
    Das Journal ist nur-anhaengend, ein Dubletten-Check waere hier sachfremd:
    zwei getrennte Aeusserungen mit demselben Wortlaut sind zwei Ereignisse.

    **Die eine Ausnahme: die Figurenanzahl** (06.09.2026, B4 der
    Phase-4-Analyse). Live hat die Gruppe sie zweimal festgelegt, und beide
    Male landete sie nur hier -- ``journal`` #27, art ``entschieden``, 77
    Zeichen --, waehrend ``arbeitsstand.figuren_anzahl`` NULL blieb. Gesetzt
    wurde das Feld bis dahin ausschliesslich vom Knopf; sagt die Gruppe die
    Zahl einfach, gab es keinen Weg hinein.

    Der Weg ist deterministisch (``figurenzahl_aus``, ein Regulaerausdruck
    ueber einen Satz, der schon dasteht) und nicht eine neue Erkenner-art:
    eine neue art kostet einen Korpuslauf, dieser Griff kostet nichts und
    fasst genau den gemessenen Fall. Der Journaleintrag bleibt daneben
    stehen -- er ist die Chronik, das Feld ist der Stand."""
    wert = wert.strip()
    if not wert:
        return None
    repo.schreibe_journal(conn, chat_id, art, wert, quelle="erkenner")
    ergebnis = {"art": art, "wert": wert}
    if art == "entschieden":
        anzahl = figurenzahl_aus(wert)
        stand = repo.hole_arbeitsstand(conn, chat_id)
        alt = (stand["figuren_anzahl"] if stand else None) or None
        if anzahl is not None and anzahl != alt:
            repo.setze_arbeitsstand(conn, chat_id, "figuren_anzahl", anzahl)
            ergebnis["figuren_anzahl"] = anzahl
    return ergebnis


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
    nummer = phasen.nummer_fuer(wert, jetzige=phasen.aktuelle(conn, chat_id))
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
#: \"setting\" steht neben \"rahmen\": seit dem Umbau vom 05.09.2026 nachts
#: heisst dasselbe Feld in der Gruppe Setting, und wer \"Setting entfernen\"
#: sagt, meint genau das (``_ENTFERNEN_ARBEITSSTAND``).
#: \"festlegung\" ist am 06.09.2026 dazugekommen. Ohne diesen Weg erbte die
#: neue Auffangtabelle den Fehler, den sie beheben soll: im Live-Fall stand
#: elf Minuten NACH der Ruecknahme des zweiten Spielorts noch ein Eintrag
#: darueber in der Datenbank, ``entfernt_am`` NULL, und kein Mechanismus
#: raeumte ihn ab.
_ENTFERNEN_ZIELE = (
    "figur", "kernthema", "format", "rahmen", "setting", "geschichte",
    "hauptkonflikt", "begriffe",
    "fragen", "szene", "journal", "festlegung", "interview", "aufnahme",
)

#: Dieselben Ziele auf Englisch (Karte A1, K5) -> die deutschen Ziele. Der
#: englische Erkenner-Prompt laesst die deutschen Woerter liefern; das hier
#: ist der Zusatz fuer ein Modell, das trotzdem englisch labelt.
_ENTFERNEN_ZIELE_EN = {
    "character": "figur",
    "core theme": "kernthema",
    "setting": "rahmen",
    "story": "geschichte",
    "terms": "begriffe",
    "questions": "fragen",
    "scene": "szene",
    "agreement": "festlegung",
    "interview": "interview",
    "recording": "aufnahme",
}

#: Die englischen Antworten auf die USA-Frage -> die deutschen Protokollwerte.
_USA_EN = {"yes": "ja", "no": "nein"}

#: Journalzeile, die eine Entfernung festhaelt -- der Weg soll sichtbar
#: bleiben, auch wenn das Entfernte es nicht mehr ist.
_JOURNAL_ENTFERNT = "Entfernt: {was}"
_JOURNAL_ZURUECK = "Zurueckgenommen: {text}"
#: Wie ein Entferntes in Meldung und Journal heisst ("Entfernt: Figur Peter").
_BEZEICHNUNG_JOURNAL = "Journal: {text}"
_BEZEICHNUNG_FESTLEGUNG = "Festlegung: {text}"
_BEZEICHNUNG_FIGUR = "Figur {name}"
_BEZEICHNUNG_SZENE = "Szene {nummer}"

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
    if ziel in _ENTFERNEN_ZIELE:
        return ziel, rest.strip(" :,")
    # Englisch erst danach (Karte A1, K5); "core theme" hat zwei Woerter,
    # deshalb am Textanfang mit Wortgrenze statt am ersten Wort.
    for wort, ziel in _ENTFERNEN_ZIELE_EN.items():
        treffer = re.match(re.escape(wort) + r"\b[\s:,.]*", text, re.IGNORECASE)
        if treffer:
            return ziel, text[treffer.end():].strip(" :,")
    return None


#: art -> Arbeitsstandfeld fuer die vier Ziele, die schlicht auf NULL gesetzt
#: werden. Ein Zeitstempel waere hier sinnlos: das Feld hat genau einen Wert.
#: ``fragen`` ist ohne eigenen Befehl dazugekommen -- das weiche Loeschen
#: laeuft ueber dieselbe Zerlegung wie alles andere ("Fragen" als erstes Wort).
_ENTFERNEN_ARBEITSSTAND = {
    "kernthema": ("kernthema", "Kernthema"),
    "format": ("format", "Format"),
    "rahmen": ("rahmen", "Setting"),
    "setting": ("rahmen", "Setting"),
    "geschichte": ("geschichte", "Geschichte"),
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
    if feld == "begriffe":
        from interview_theater import begriffsboard

        begriffsboard.schreibe_detail(conn, chat_id, None)
    return T._FELD_BESCHRIFTUNG.get(feld, bezeichnung)


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
            T._JOURNAL_ZURUECK.format(text=alter_text), quelle=quelle,
        )
        return {"art": "entfernen", "wert": T._BEZEICHNUNG_JOURNAL.format(text=alter_text)}

    if ziel == "festlegung":
        alter_text = repo.entferne_festlegung(conn, chat_id, rest)
        if alter_text is None:
            return None
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            T._JOURNAL_ZURUECK.format(text=alter_text), quelle=quelle,
        )
        return {"art": "entfernen", "wert": T._BEZEICHNUNG_FESTLEGUNG.format(text=alter_text)}

    if ziel in _ENTFERNEN_ARBEITSSTAND:
        bezeichnung = _entferne_arbeitsstandfeld(conn, chat_id, ziel)
    elif ziel == "figur":
        name = repo.entferne_figur(conn, chat_id, rest) if rest else None
        bezeichnung = T._BEZEICHNUNG_FIGUR.format(name=name) if name else None
    elif ziel in ("interview", "aufnahme"):
        # Ohne Angabe wird NICHT geraten: "loesch das Interview" ohne Nummer
        # oder Namen koennte jedes von fuenfen meinen, und weggenommen wird
        # hier Material (N5).
        from interview_theater import aufnahme  # spaeter Import

        kopf = aufnahme.finde_interview(conn, chat_id, rest) if rest else None
        # E8: die Bezeichnung VOR dem Entfernen bilden -- danach zaehlt die
        # Nummer das entfernte Interview nicht mehr mit. Sie geht ins Journal
        # (jeder Gespraechs-Prompt) und in die Bot-Zeile.
        anzeige = (aufnahme.anzeigename(conn, kopf, "Interview")
                   if kopf and sprache.pseudonyme() else None)
        name = repo.entferne_aufnahme(conn, chat_id, kopf["id"]) if kopf else None
        bezeichnung = (anzeige or name) if name else None
    else:  # szene
        treffer = _SZENENNUMMER.search(rest or "")
        nummer = repo.entferne_szene(conn, chat_id, int(treffer.group(1))) if treffer else None
        bezeichnung = T._BEZEICHNUNG_SZENE.format(nummer=nummer) if nummer is not None else None

    if bezeichnung is None:
        return None
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        T._JOURNAL_ENTFERNT.format(was=bezeichnung), quelle=quelle,
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
    if art == "festlegung_setzen":
        return _wende_festlegung_an(conn, chat_id, wert)
    if art == "szenenanzahl_setzen":
        return _wende_szenenanzahl_an(conn, chat_id, wert)
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
        # Englisch zusaetzlich (Karte A1, K5): gespeichert und quittiert wird
        # der deutsche Protokollwert.
        w = _USA_EN.get(w, w)
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
    if art == "szene_kuerzen":
        # Kein Schreibpfad, aus demselben Grund wie szene_schreiben: eine
        # Kuerzung ist kein Arbeitsstandfeld, sondern ein Lauf. Den stoesst
        # laufe() an (dort gibt es tg und klm).
        return None
    if art == "uebersicht_aendern":
        # Kein Schreibpfad, wie szene_schreiben: diese art stoesst eine
        # Neugenerierung an (entwurf.py), die laufe() auswertet.
        return None
    if art == "formen_setzen":
        # Padua Phasen TEIL 2: schreibt ``szene.form`` -- die WAHL der Gruppe,
        # nicht ``form_vorschlag``. docs/agents/was-bewusst-fehlt.md, "Eine Menuezeile ist keine
        # Geschichte": "die Regel haelt den Vorschlag eines Modells aus dem
        # Feld heraus, nicht die Wahl der Gruppe". Die Gruppe hat die Form im
        # Chat genannt, als Antwort auf die Formwahl-Liste.
        from interview_theater import ueberarbeitung

        zeilen = ueberarbeitung._wende_formen_an(conn, chat_id, wert)
        return {"art": art, "wert": wert, "zeilen": zeilen} if zeilen else None
    if art == "sprechweise_setzen":
        from interview_theater import sprechweise

        zeilen = sprechweise.wende_an(conn, chat_id, wert)
        return {"art": art, "wert": wert, "zeilen": zeilen} if zeilen else None
    if art in ("text_ueberarbeiten", "fassung_abnehmen", "schaerfung_entscheidung"):
        # Kein Schreibpfad, wie szene_schreiben: diese Arten stossen einen
        # Weg an, den laufe() auswertet (``_starte_teil2``) -- derselbe, den
        # der passende Knopf nimmt.
        return None
    # Unbekannte art sollte erkenne() bereits herausgefiltert haben; bei
    # direktem Aufruf von wende_an() (z. B. in Tests) einfach ignorieren
    # statt zu krachen.
    return None


def _ohne_figur_festlegung_neben_figur_setzen(aenderungen: list[dict]) -> list[dict]:
    """Eine ``festlegung_setzen`` mit Bereich ``figur`` faellt weg, wenn
    derselbe Lauf auch ``figur_setzen`` oder ``figur_quelle_setzen`` (Fall
    en-e15) fuer diese Figur liefert (02.10.2026, Fall z04: neben
    drei ``figur_setzen`` kam zusaetzlich "figur: die Zuordnung der Figuren
    ist nur fuer die Gruppe" -- ein Metakommentar zum Festhalten selbst, kein
    eigener Fakt UEBER eine Figur). Mit Bezug auf einen der gerade gesetzten
    Namen ist es dieselbe Figur doppelt erfasst; ohne Bezug ist es eine
    allgemeine Bemerkung zum Vorgang -- beides gehoert nicht in die
    Auffangtabelle, wenn die Figuren im selben Atemzug gesetzt werden."""
    try:
        figuren_namen = {
            str(a.get("wert") or "").split(":", 1)[0].strip().lower()
            for a in aenderungen
            if a.get("art") in ("figur_setzen", "figur_quelle_setzen")
        }
    except Exception:
        # Defensiv wie wende_an() selbst: eine fehlerhafte Aenderung (z. B.
        # ein nicht-String-Wert) soll diesen Vorfilter nicht zum Absturz
        # bringen -- der eigentliche Fehler wird ohnehin gleich darauf im
        # try/except der Schleife unten gefangen und vermerkt.
        return aenderungen
    if not figuren_namen:
        return aenderungen
    ergebnis = []
    for a in aenderungen:
        if a.get("art") == "festlegung_setzen":
            try:
                bereich, bezug, _ = _zerlege_festlegung(a.get("wert") or "")
            except Exception:
                ergebnis.append(a)
                continue
            if bereich == "figur" and (
                bezug is None or bezug.strip().lower() in figuren_namen
            ):
                continue
        ergebnis.append(a)
    return ergebnis


def _ohne_interview_starten_neben_ruecksprung(aenderungen: list[dict]) -> list[dict]:
    """``interview_starten`` faellt weg, wenn derselbe Lauf in die
    Interview-Phase (3) springt (02.10.2026, Korpusfall p05: \"zurueck zu den
    Interviews, wir fragen Hatice nochmal\" -- ein Plan, keine Aufnahme). Der
    Phaseneintritt bietet den Aufnahmeknopf ohnehin an, ein zweites Angebot
    daneben waere doppelt; und ``interview_starten`` startet seit 05.09.
    nichts mehr, sondern bietet nur an (``_wende_interview_starten_an``)."""
    springt_in_drei = False
    for a in aenderungen:
        if a.get("art") == "phase_setzen":
            try:
                springt_in_drei = phasen.nummer_fuer(str(a.get("wert") or "")) == 3
            except Exception:
                springt_in_drei = False
            if springt_in_drei:
                break
    if not springt_in_drei:
        return aenderungen
    return [a for a in aenderungen if a.get("art") != "interview_starten"]


def waechter_filter(aenderungen: list[dict]) -> list[dict]:
    """Die rein deterministischen Waechter, die ``wende_an`` vor dem Schreiben
    anwendet -- ohne Datenbank, damit der Korpuslauf (``scripts/
    pruefe_prompts.py``) genau dasselbe herausfiltert wie der Betrieb:
    doppelte Figuren-Festlegungen und Festlegungen ohne eigenen Inhalt. Die
    datenbankabhaengige Pruefung (``_steht_schon_in_einem_feld``) bleibt in
    ``_wende_festlegung_an``."""
    aenderungen = _ohne_interview_starten_neben_ruecksprung(aenderungen)
    ergebnis = []
    for a in _ohne_figur_festlegung_neben_figur_setzen(aenderungen):
        if a.get("art") == "festlegung_setzen":
            try:
                _, bezug, text = _zerlege_festlegung(a.get("wert") or "")
            except Exception:
                ergebnis.append(a)
                continue
            text = " ".join((text or "").split())
            if not text or _ohne_eigenen_inhalt(text, bezug):
                continue
        ergebnis.append(a)
    return ergebnis


def wende_an(conn, e, chat_id: int, aenderungen: list[dict]) -> list[dict]:
    """Schreibt erkannte Aenderungen in Arbeitsstand, Figuren, Journal und
    Schalter (SPEC § 4.3, teil-b.md Aufgabe 3).

    Liefert nur die Aenderungen zurueck, die tatsaechlich etwas verschoben
    haben -- Grundlage fuer die Meldung in Aufgabe 4 (``baue_meldung``).

    Robustheit: jede Aenderung laeuft in ihrem eigenen try/except. Eine
    fehlerhafte Aenderung (z. B. ein unerwarteter Werttyp) darf die anderen
    im selben Lauf nicht mitreissen -- sie wird geloggt und als ``vorfall``
    vermerkt, der Lauf macht mit der naechsten Aenderung weiter."""
    # Dieselben Listen-Waechter wie im Korpuslauf (``waechter_filter``); die
    # Inhaltspruefung laeuft hier in ``_wende_festlegung_an``, weil sie dort
    # einen Vorfall vermerkt -- das Ergebnis ist dasselbe.
    aenderungen = _ohne_figur_festlegung_neben_figur_setzen(
        _ohne_interview_starten_neben_ruecksprung(aenderungen)
    )
    aenderungen = [
        a for a in aenderungen
        if _ist_phasenpassend(conn, chat_id, a.get("art"))
    ]
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
_ZEILE_EINE_FIGUR = "eine Figur: {liste}"
_ZEILE_FIGUREN = "{zahlwort} Figuren: {liste}"

#: Journalzeilen fuer das Zusammenfuehren eines Platzhalters und fuer eine
#: Transkriptkorrektur.
_JOURNAL_ZUSAMMENGEFUEHRT = (
    "Aus {alt} wurde {neu} -- Sprachstil und Szenenbesetzung sind mitgewandert."
)
_JOURNAL_KORRIGIERT = "Transkript korrigiert: {text}"


def _figuren_zeile(namen: list[str]) -> str:
    liste = ", ".join(namen)
    if len(namen) == 1:
        return T._ZEILE_EINE_FIGUR.format(liste=liste)
    zahlwort = T._FIGUREN_ZAHLWORT.get(len(namen), str(len(namen)))
    return T._ZEILE_FIGUREN.format(zahlwort=zahlwort, liste=liste)


#: Wie weit zurueck geschaut wird, ob eine Notiert-Meldung schon dasteht.
#: Drei Bot-Nachrichten sind das Fenster, das die Gruppe auf dem Telefon noch
#: im Blick hat -- dieselbe Zahl wie in der system.md-Regel "wiederhole
#: nichts, was in deinen letzten drei Nachrichten steht".
MELDUNG_RUECKSCHAU = 3


def _steht_schon_da(conn, chat_id: int, text: str) -> bool:
    """Stand diese Notiert-Meldung wortgleich schon in einer der letzten
    ``MELDUNG_RUECKSCHAU`` Bot-Nachrichten? (06.09.2026)

    Wortgleich und nicht aehnlich: eine Notiert-Zeile ist deterministisch
    aufgebaut (``baue_meldung``), zwei Laeufe ueber denselben Stand liefern
    denselben String. Ein unscharfes Mass wuerde hier eine echte zweite
    Aenderung verschlucken -- "Rahmen: A" und "Rahmen: B" teilen fast alle
    Woerter."""
    letzte = [
        (zeile["text"] or "").strip()
        for zeile in repo.letzte_nachrichten(conn, chat_id, 30)
        if zeile["ist_bot"]
    ]
    return text.strip() in letzte[-MELDUNG_RUECKSCHAU:]


def _biete_phase_an(conn, tg, chat_id: int) -> None:
    """Die proaktive Phasenmeldung nach einem Speichern -- weich, damit ein
    Fehlschlag hier die Notiert-Zeile nicht mitreisst (06.09.2026).

    Spaeter Import wie ueberall: ``knoepfe`` greift seinerseits auf den
    Erkenner zu."""
    try:
        from interview_theater import knoepfe

        knoepfe.biete_phase_proaktiv(conn, tg, chat_id)
    except Exception:
        log.exception("Phasenangebot nach dem Erkennerlauf fehlgeschlagen, chat_id=%s", chat_id)


def _erneuere_angebot_auf_bitte(conn, chat_id: int, aenderungen: list[dict]) -> bool:
    """Eine Bitte der Gruppe erneuert das Phasenangebot (06.09.2026,
    Nacht-Simulation Punkt 6). Liefert True, wenn der Merkposten abgeraeumt
    wurde.

    Der gemessene Fall: die Gruppe sagt \"weiter\", \"naechste Phase\" oder \"wir
    sind fertig hier\". Der Erkenner macht daraus ein ``phase_setzen`` -- ohne
    Nummer, weil in dem Satz keine steht (``phasen.nummer_fuer`` liefert
    None), oder mit der Nummer der Phase, in der die Gruppe ohnehin schon
    steht. Beides schreibt nichts, taucht in ``wirkliche`` also nie auf, und
    bis heute passierte danach: nichts. Der Knopf \"Weiter zu <Phase>\" war
    einmal dagewesen und kam nie wieder.

    Deterministisch und ohne eigenen Modellaufruf: gelesen wird nur, was der
    Erkennerlauf ohnehin geliefert hat (Zusage 2). Abgeraeumt wird nur, wenn
    es ueberhaupt etwas anzubieten gibt -- sonst waere es ein Angebot ins
    Leere."""
    jetzige = phasen.aktuelle(conn, chat_id)
    bitten = [
        a for a in aenderungen
        if a.get("art") == "phase_setzen"
        and (phasen.nummer_fuer(a.get("wert"), jetzige=jetzige) or 0) <= jetzige
    ]
    if not bitten:
        return False
    naechste = phasen.naechste_moegliche(conn, chat_id)
    if naechste is None or naechste <= jetzige:
        return False
    phasen.vergiss_angebot(conn, chat_id)
    return True


#: Nach einem ausdruecklichen Wechsel nach Phase 1 liest dieser Weg kein
#: "weiter" (Live Padua 05.10.2026, G3 Pingpong 1<->2).
ZURUECK_SPERRE_S = 120


def _weiter_aus_phase_1(conn, chat_id: int, aenderungen: list[dict]) -> list[dict]:
    """"Let's move on" in Phase 1 geht in Phase 2 (Birk 05.10.2026, Brief
    "p1-bleiben"). Eine gespeicherte Begriffs-Korrektur wechselt dort die
    Phase nie; die Gruppe hat danach die Frage "Move on?" vor sich
    (``knoepfe.basis.biete_begriffe_aktualisiert``). Liest der Erkenner ihre
    Antwort als ``phase_setzen`` ohne wirksame Nummer ("next", "1") -- was
    sonst nur das Angebot erneuert (``_erneuere_angebot_auf_bitte``) --, ist
    das Ziel hier eindeutig: die Fragen. Nur unter dem Padua-Autosave
    (``knoepfe.basis.begriffe_bleiben_in_phase_1``) und nur, wenn Phase 2
    erreichbar ist (Begriffe gespeichert). Liefert die eine
    ``phase_setzen``-Aenderung fuer ``wirkliche`` -- daran haengen Meldung
    und Phaseneintritt (``_eintritt_nach_phasenwechsel``)."""
    from interview_theater.knoepfe import basis

    if not basis.begriffe_bleiben_in_phase_1(conn, chat_id):
        return []
    bitte = any(
        a.get("art") == "phase_setzen"
        and (phasen.nummer_fuer(a.get("wert"), jetzige=1) or 1) <= 1
        for a in aenderungen
    )
    if not bitte or phasen.naechste_moegliche(conn, chat_id) != 2:
        return []
    # Live Padua 05.10.2026 (G3, dreimal 15:02-15:08): die Gruppe klickte in
    # der Phasenleiste zurueck auf "1 · Terms" (``/phaseklick 1``); der
    # Erkenner las den Zug als ``phase_setzen`` "1", und dieser Weg machte
    # daraus "weiter" -- die Gruppe flog sofort wieder in Phase 2. Wer gerade
    # ausdruecklich nach Phase 1 gewechselt ist, will dort bleiben.
    gesetzt = repo.hole_phase_gesetzt_am(conn, chat_id)
    if gesetzt:
        try:
            alter = (datetime.now(timezone.utc) - datetime.fromisoformat(gesetzt)).total_seconds()
        except ValueError:
            alter = None
        if alter is not None and alter < ZURUECK_SPERRE_S:
            return []
    if not phasen.setze(conn, chat_id, 2, "erkenner"):
        return []
    return [{"art": "phase_setzen", "wert": "2"}]


def baue_meldung(
    wirkliche_aenderungen: list[dict], conn=None, chat_id: int | None = None,
) -> str | None:
    """Baut die eine Meldung je Erkennerlauf (SPEC § 4.3, teil-b.md Aufgabe
    4) -- nicht eine je Aenderung.

    ``conn``/``chat_id`` sind optional (Padua, 02.10.2026): stehen beide zur
    Verfuegung, bekommen die Zeilen in Phase 4 die 📌-Fassung
    (``_ZEILE_FESTGELEGT``) statt der sonst ueblichen -- siehe
    ``_meldungszeilen``. Ohne die beiden (z. B. in bestehenden Tests, die nur
    die Liste der Aenderungen kennen) bleibt die alte Fassung unveraendert.

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
    phase = (
        phasen.aktuelle(conn, chat_id)
        if conn is not None and chat_id is not None else None
    )
    zeilen = _meldungszeilen(_sammle_meldbares(wirkliche_aenderungen), phase=phase)
    if not zeilen:
        return None
    # Birk live 05.10.2026: die Speichermeldung nahm zu viel Raum ein. Eine
    # Meldung, die NUR aus 📌-Zeilen besteht, braucht den Kopf "Noted:" nicht
    # -- die Nadel ist das Kennzeichen (eine Zeile weniger).
    from interview_theater import workshop as _ws

    if _ws.autosave_phase1_2_aktiv() and all(z.startswith("📌") for z in zeilen):
        return "\n".join(zeilen)
    return T._NOTIERT_KOPF + "\n".join(zeilen)


def _sammle_meldbares(wirkliche_aenderungen: list[dict]) -> dict:
    """Ordnet die Aenderungen eines Laufs nach ihrer Art vor.

    Was hier fehlt, bleibt still: ``verworfen``/``entschieden``/``wortlaut_an``
    /``wortlaut_aus``/``interview_benennen`` sind bewusst nicht dabei
    (Aufgabe 4). ``szene_schreiben`` ebenfalls -- es meldet sich selbst, mit
    einer Ankuendigung und spaeter der fertigen Szene (``szene.py``). Und
    ``figur_quelle_setzen`` aus demselben Grund: die Zeile, die zaehlt, ist
    "Sprachprofil fuer Pola aus Interview 2: ..." und die kommt aus
    ``sprachprofil.py``, wenn das Profil wirklich steht."""
    gesammelt: dict = {
        "kernthema": None, "format": None, "rahmen": None, "geschichte": None,
        "hauptkonflikt": None, "begriffe": None, "fragen": None,
        "phase": None, "usa": None, "figuren_anzahl": None,
        "szenen_anzahl": None,
        "figuren": [], "geplant": [], "festgehalten": [],
        "korrigiert": [], "entfernt": [],
        # Padua Phasen TEIL 2: fertige Zeilen aus formen_setzen/
        # sprechweise_setzen (die Module bauen sie selbst, je Szene/Figur).
        "teil2": [],
    }
    einzeln = {
        "szene_usa": "usa",
        "kernthema_setzen": "kernthema",
        "format_setzen": "format",
        "rahmen_setzen": "rahmen",
        "geschichte_setzen": "geschichte",
        "hauptkonflikt_setzen": "hauptkonflikt",
        "begriffe_setzen": "begriffe",
        "fragen_setzen": "fragen",
        "szenenanzahl_setzen": "szenen_anzahl",
    }
    mehrfach = {
        "figur_setzen": "figuren",
        "szene_planen": "geplant",
        "transkript_korrigieren": "korrigiert",
        "entfernen": "entfernt",
    }
    for aenderung in wirkliche_aenderungen:
        art = aenderung.get("art")
        wert = aenderung.get("wert", "")
        if art in einzeln:
            gesammelt[einzeln[art]] = wert
        elif art in mehrfach:
            gesammelt[mehrfach[art]].append(wert)
        elif art == "festlegung_setzen":
            gesammelt["festgehalten"].append((
                aenderung.get("bereich"), aenderung.get("bezug"),
                aenderung.get("text", wert),
            ))
        elif art == "phase_setzen":
            gesammelt["phase"] = phasen.nummer_fuer(wert)
        elif art in ("formen_setzen", "sprechweise_setzen"):
            gesammelt["teil2"].extend(aenderung.get("zeilen") or [])
        # Ein ``entschieden`` bleibt still -- ausser es hat nebenbei die
        # Figurenanzahl gesetzt (B4). Dann ist es eine Arbeitsstandaenderung
        # wie jede andere und gehoert in die Meldung: sonst stuende die Zahl
        # in der Datenbank und die Gruppe wuesste nichts davon.
        if aenderung.get("figuren_anzahl"):
            gesammelt["figuren_anzahl"] = aenderung["figuren_anzahl"]
    return gesammelt


#: Der Kopf der Meldung -- "Notiert:" ist zugleich das Kennzeichen, an dem
#: ``repo.letzte_bot_nachricht_vor`` die Meldung aus dem Vorlauf nimmt (dort
#: werden beide Sprachfassungen erkannt) und das der Simulator aus
#: ``baue_meldung`` selbst liest.
_NOTIERT_KOPF = "Notiert:\n"

#: Arbeitsstandfeld -> Beschriftung in der Meldung (und in "Entfernt: ...").
#: Schluessel sind Spaltennamen, uebersetzt werden nur die Werte.
#: ``eroeffnung`` ist kein Arbeitsstand-Spaltenname (der Block geht in ZWEI
#: Felder, ``interview_eroeffnung``/``interview_abschluss`` -- siehe
#: ``knoepfe.fragen.schreibe_eroeffnung_automatisch``), steht hier aber mit,
#: weil der Autosave-Pfad in Phase 1/2 (``knoepfe.basis._autospeichere``)
#: dieselbe Titel-Tabelle liest wie diese Meldung.
_FELD_BESCHRIFTUNG = {
    "kernthema": "Kernthema",
    "format": "Format",
    "rahmen": "Setting",
    "geschichte": "Geschichte",
    "hauptkonflikt": "Hauptkonflikt",
    "figuren_anzahl": "Anzahl Figuren",
    "begriffe": "Begriffe",
    "fragen": "Fragen",
    "szenen_anzahl": "Anzahl Szenen",
    "eroeffnung": "Eröffnung",
}

#: Die uebrigen Zeilen der Meldung, je mit eigenem Verb.
_ZEILE_FESTGEHALTEN = "Festgehalten{marke}: {text}"
#: Padua-Brainstorming-Umbau (02.10.2026): in Phase 4 (Setting, Figuren &
#: Geschichte) bekommt jede automatisch gespeicherte Festlegung -- und seit
#: derselben Karte auch Setting, Geschichte und Anzahl Szenen -- diese Zeile
#: statt der sonst ueblichen ("Festgehalten: ..."/"Setting: ..."). Sie macht
#: sichtbar, dass hier **nichts** auf eine Bestaetigung wartet: alles, was
#: gesagt wird, ist sofort festgehalten, und der einzige Weg zurueck ist der
#: EINE Undo-Knopf unter der Meldung (``knoepfe.undo_leiste`` --
#: ``rahmen_setzen``/``geschichte_setzen`` sind seit derselben Karte aus
#: ``_LEISTENARTEN`` entfernt, es gibt also nie eine zusaetzliche
#: Grundleiste darunter).
_ZEILE_FESTGELEGT = "📌 Festgelegt: {titel} — {text}"
_ZEILE_KORRIGIERT = "Korrigiert: {zeile}"
_ZEILE_ENTFERNT = "Entfernt: {was}"
_ZEILE_PHASE = "Wir sind jetzt bei {phase}."
_ZEILE_USA_JA = (
    "Szenentexte kommen ab jetzt vom US-Modell (Anthropic). Ich sage es vor "
    "jeder Szene nochmal."
)
_ZEILE_USA_NEIN = "Szenentexte bleiben in der Schweiz. Ich frage nicht wieder."


#: Dieselbe Phasennummer wie ``knoepfe.texte.PHASE_SETTING`` -- hier als
#: eigene Konstante, weil ``erkenner`` nicht von ``knoepfe`` importiert
#: (Zyklus: ``knoepfe`` importiert ``erkenner``).
PHASE_SETTING = 4

#: Felder, die in Phase 4 die 📌-Fassung bekommen (siehe ``_ZEILE_FESTGELEGT``).
_FESTGELEGT_FELDER = frozenset({"rahmen", "geschichte", "szenen_anzahl"})

#: Dasselbe fuer Phase 1 (Begriffe) und Phase 2 (Fragen) -- nur mit dem
#: Profilschalter ``workshop.autosave_phase1_2_aktiv`` (Padua P1-2). Ohne ihn
#: bleibt "Begriffe: ..."/"Fragen: ..." wie bisher, mit der Ja/Nein-Leiste aus
#: ``_LEISTENARTEN`` darunter.
_AUTOSAVE_FELDER_1_2 = frozenset({"begriffe", "fragen"})


def _meldungszeilen(g: dict, phase: int | None = None) -> list[str]:
    """Aus dem Vorgeordneten die Zeilen der Meldung, in fester Reihenfolge."""
    zeilen = []
    beschriftung = T._FELD_BESCHRIFTUNG
    in_phase4 = phase == PHASE_SETTING
    autosave_1_2 = False
    if phase in (1, 2):
        from interview_theater import workshop

        autosave_1_2 = workshop.autosave_phase1_2_aktiv()

    def feld(name: str) -> None:
        if not g[name]:
            return
        festgelegt = (in_phase4 and name in _FESTGELEGT_FELDER) or (
            autosave_1_2 and name in _AUTOSAVE_FELDER_1_2
        )
        if festgelegt:
            zeilen.append(T._ZEILE_FESTGELEGT.format(
                titel=beschriftung[name], text=g[name],
            ))
        else:
            zeilen.append(f"{beschriftung[name]}: {g[name]}")

    for name in ("kernthema", "format", "rahmen", "geschichte",
                 "hauptkonflikt", "figuren_anzahl", "szenen_anzahl"):
        feld(name)
    if g["figuren"]:
        zeilen.append(_figuren_zeile(g["figuren"]))
    feld("begriffe")
    feld("fragen")
    # Eine geplante Szene bekommt ihre Kurzzeile ("Szene 1 · Dialog ·
    # Polizeikessel · Mira, Pola"): die Gruppe soll sehen, welche Szene
    # gemeint ist, ohne die ganze Planung noch einmal zu lesen.
    zeilen.extend(g["geplant"])
    zeilen.extend(g["teil2"])
    # Eine Festlegung bekommt ihr eigenes Verb (06.09.2026) -- und mit dem
    # Bezug in Klammern, wo es einen gibt. Sie MUSS sichtbar sein: sie steht
    # in keinem Feld und auf keiner Checkliste, und die Gruppe braucht sie im
    # Chat, um widersprechen zu koennen ("nimm das wieder raus").
    for bereich, bezug, text in g["festgehalten"]:
        if in_phase4:
            titel = (bereich or "sonstiges")
            titel = titel[:1].upper() + titel[1:]
            if bezug:
                titel = f"{titel} · {bezug}"
            zeilen.append(T._ZEILE_FESTGELEGT.format(titel=titel, text=text))
        else:
            marke = f" ({bezug})" if bezug else ""
            zeilen.append(T._ZEILE_FESTGEHALTEN.format(marke=marke, text=text))
    # Eine Transkriptkorrektur bekommt ihr eigenes Verb (N5): "Korrigiert:
    # gepoekt -> gepogt". Sie ist der Beleg dafuer, dass wirklich etwas
    # passiert ist -- im Probelauf sagte der Bot dreimal "korrigiere ich",
    # und in der Datenbank aenderte sich nichts.
    zeilen.extend(T._ZEILE_KORRIGIERT.format(zeile=zeile) for zeile in g["korrigiert"])
    # Entfernungen stehen in derselben Meldung wie alles andere -- eine
    # Nachricht je Erkennerlauf bleibt die Regel (SPEC § 4.3). Sie tragen ihr
    # eigenes Verb, damit niemand "Notiert:" liest und denkt, es sei etwas
    # dazugekommen.
    zeilen.extend(T._ZEILE_ENTFERNT.format(was=was) for was in g["entfernt"])
    if g["phase"] is not None:
        zeilen.append(T._ZEILE_PHASE.format(phase=phasen.bezeichnung(g["phase"])))
    if g["usa"] == "ja":
        zeilen.append(T._ZEILE_USA_JA)
    elif g["usa"] == "nein":
        zeilen.append(T._ZEILE_USA_NEIN)
    return zeilen


def undo_zeilen(wirkliche_aenderungen: list[dict]) -> list[str]:
    """Die Zeilen, die eine Ruecknahme dieses Laufs nennen wuerde.

    **Dieselbe Quelle wie die Meldung** (``_sammle_meldbares`` →
    ``_meldungszeilen``), nur mit gefilterter Eingabe -- "Rueckgaengig
    gemacht:" soll nicht anders klingen als "Notiert:", und ein zweiter
    Formulierungsweg waere die naechste Stelle, an der beide auseinanderlaufen.

    Gefiltert wird mit einer **Ausschluss**liste
    (``ruecknahme.ZEILEN_OHNE_UNDO``: ``phase_setzen``, ``szene_usa``) und
    nicht mit einer Einschlussliste. Der Grund ist gemessen am Code:
    ``entschieden`` ist in der Meldung still, setzt aber nebenbei
    ``arbeitsstand.figuren_anzahl`` (``_wende_journal_an``) -- eine
    Einschlussliste haette die Zeile "Anzahl Figuren: 4" verschluckt, obwohl
    das Feld verfolgt wird und die Ruecknahme es zurueckdreht."""
    behalten = [
        a for a in wirkliche_aenderungen
        if a.get("art") not in ruecknahme.ZEILEN_OHNE_UNDO
    ]
    return _meldungszeilen(_sammle_meldbares(behalten))


def _merke_undo_vorfall(conn, e, chat_id: int, text: str) -> None:
    """Der Vorfall ``undo_nicht_angelegt`` -- selbst abgesichert: ist die
    Datenbank gerade belegt, scheitert auch dieser Schreibzugriff, und dann
    darf er die Notiert-Meldung nicht mitreissen (Review-Fix Aufgabe 7)."""
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None), "undo_nicht_angelegt", text,
        )
    except Exception:
        log.exception("Vorfall undo_nicht_angelegt nicht geschrieben, chat_id=%s", chat_id)


def _wende_an_mit_schnappschuss(conn, e, chat_id: int, aenderungen: list[dict]
                                ) -> tuple[list[dict], dict | None, dict | None]:
    """``wende_an`` zwischen zwei Schnappschuessen der verfolgten Tabellen --
    Grundlage des Undo-Knopfs (Karte U). Liefert ``(wirkliche, vorher,
    nachher)``; ``vorher``/``nachher`` sind ``None``, wenn ein Schnappschuss
    ausgefallen ist (dann gibt es keinen Knopf, aber einen Vorfall).

    **Beide Schnappschuesse liegen direkt um ``wende_an`` und unter
    ``repo._LOCK``** (Review-Fix Aufgabe 7). Vorher entstand der zweite erst
    beim Anlegen des Laufs, nach Telegram-Sends und Thread-Starts -- was in
    diesen Sekunden ein Knopfdruck der Hauptschleife oder ein Szenenfolge-
    Thread schrieb, landete als Schritt DIESES Laufs im Diff, und das Undo
    haette die Entscheidung der Gruppe still zurueckgedreht. Der Lock ist ein
    ``RLock``, die ``repo``-Aufrufe darin nehmen ihn erneut; ``wende_an``
    schreibt nur in die Datenbank (kein Telegram, kein Modell, kein Warten
    auf einen anderen Thread), haelt ihn also nur Millisekunden. Andere
    Prozesse (Web, die anderen Bots) sperrt er nicht -- die schreiben aber in
    ihre eigene Gruppe bzw. sind durch SQLite serialisiert.

    Hier und nicht in ``wende_an``: ``wende_aus_aufnahme_an`` schickt keine
    Meldung und bekommt deshalb auch kein Undo, und die Signatur von
    ``wende_an`` bleibt, was sie ist."""
    with repo._LOCK:
        try:
            plan = ruecknahme.plan(a.get("art") for a in aenderungen)
            vorher = repo.schnappschuss(conn, chat_id, plan)
        except Exception:
            log.exception("Schnappschuss vor dem Anwenden fehlgeschlagen, "
                          "chat_id=%s", chat_id)
            _merke_undo_vorfall(conn, e, chat_id,
                                "Schnappschuss vor dem Anwenden fehlgeschlagen")
            plan = vorher = None
        wirkliche = wende_an(conn, e, chat_id, aenderungen)
        nachher = None
        if vorher is not None:
            try:
                nachher = repo.schnappschuss(conn, chat_id, plan)
            except Exception:
                log.exception("Schnappschuss nach dem Anwenden fehlgeschlagen, "
                              "chat_id=%s", chat_id)
                _merke_undo_vorfall(conn, e, chat_id,
                                    "Schnappschuss nach dem Anwenden fehlgeschlagen")
    return wirkliche, vorher, nachher


def lauf_fuer_knopf(conn, e, chat_id: int, text: str, schreibe) -> int | None:
    """Dieselbe Schnappschuss-Maschine wie ein Erkennerlauf (Karte U), nur
    ausgeloest durch einen Knopf statt durch ``wende_an`` (UX-Knoepfe-Karte,
    02.10.2026, Abschnitt 2: "Ja, speichern" / phase-2 Annehmen · Verwerfen
    bekommen damit denselben Undo-Knopf wie jede automatische
    Erkenner-Meldung -- keine zweite Ruecknahme-Maschine).

    ``schreibe`` ist ein parameterloser Aufrufer, der die eigentlichen
    ``repo.setze_*``-Schreibzugriffe ausfuehrt; er laeuft **innerhalb** des
    Schnappschuss-Fensters, genau wie ``wende_an`` in
    ``_wende_an_mit_schnappschuss``. ``text`` ist die schon fertige
    "Notiert:"-Zeile -- hier gibt es keine ``aenderungen``-Liste, aus der
    sich wie bei ``undo_zeilen`` ein Wortlaut herleiten liesse.

    Liefert die Lauf-id fuer ``knoepfe.basis.undo_leiste``, oder ``None``
    (kein Diff, oder ein Schnappschuss ist ausgefallen -- dann schreibt
    ``schreibe`` trotzdem, nur ohne Undo-Knopf)."""
    plan = ruecknahme.plan(["knopf_speichern"])
    with repo._LOCK:
        try:
            vorher = repo.schnappschuss(conn, chat_id, plan)
        except Exception:
            log.exception(
                "Schnappschuss vor dem Knopf-Speichern fehlgeschlagen, "
                "chat_id=%s", chat_id,
            )
            schreibe()
            _merke_undo_vorfall(
                conn, e, chat_id,
                "Schnappschuss vor dem Knopf-Speichern fehlgeschlagen",
            )
            return None
        schreibe()
        try:
            nachher = repo.schnappschuss(conn, chat_id, plan)
        except Exception:
            log.exception(
                "Schnappschuss nach dem Knopf-Speichern fehlgeschlagen, "
                "chat_id=%s", chat_id,
            )
            _merke_undo_vorfall(
                conn, e, chat_id,
                "Schnappschuss nach dem Knopf-Speichern fehlgeschlagen",
            )
            return None
    schritte = ruecknahme.schritte(vorher, nachher)
    if not schritte:
        return None
    try:
        return repo.lege_erkenner_lauf_an(conn, chat_id, text, schritte)
    except Exception:
        log.exception(
            "Ruecknahme (Knopf) konnte nicht angelegt werden, chat_id=%s",
            chat_id,
        )
        _merke_undo_vorfall(
            conn, e, chat_id, "Notiert-Meldung ohne Undo-Knopf verschickt",
        )
        return None


def _lege_ruecknahme_an(conn, e, chat_id: int, vorher: dict | None,
                        nachher: dict | None, wirkliche: list[dict]) -> int | None:
    """Schreibt die Ruecknahme-Schritte dieses Laufs und liefert die Lauf-id,
    oder ``None``, wenn es keinen Knopf geben soll.

    Kein Knopf gibt es in drei Faellen: ein Schnappschuss ist ausgefallen
    (der Vorfall steht dann schon), der Diff ist leer (nur Phase, nur USA --
    beides nicht verfolgt), oder es gibt keine Zeile, die die Ruecknahme
    benennen koennte.

    Die Schnappschuesse kommen fertig herein (``_wende_an_mit_schnappschuss``)
    -- hier wird keiner genommen, weil zwischen ``wende_an`` und diesem
    Aufruf schon fremde Schreibzugriffe liegen koennen.

    **Ein Fehlschlag hier reisst die Meldung nicht mit** -- dieselbe Haltung wie
    bei der Grundleiste in ``_sende_meldung``: der Wert ist wichtiger als seine
    Knoepfe. Fuers Dashboard bleibt ein Vorfall stehen."""
    if vorher is None or nachher is None:
        return None
    try:
        return repo.lege_erkenner_lauf_an(
            conn, chat_id, "\n".join(undo_zeilen(wirkliche)),
            ruecknahme.schritte(vorher, nachher),
        )
    except Exception:
        log.exception("Ruecknahme konnte nicht angelegt werden, chat_id=%s", chat_id)
        _merke_undo_vorfall(conn, e, chat_id, "Notiert-Meldung ohne Undo-Knopf verschickt")
        return None


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
        "interview_beenden": befehle.T._TEXT_INTERVIEW_AUS,
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
    from interview_theater import aufnahme, knoepfe  # spaeter Import, haelt den Modulkopf frei

    texte = _interviewmodus_texte()
    for aenderung in wirkliche:
        art = aenderung.get("art")
        text = texte.get(art)
        if text is None:
            continue
        try:
            system = art == "interview_beenden" and aufnahme.fliesstext_aktiv(conn, chat_id)
            message_id = knoepfe.biete_aufnahme(conn, tg, chat_id, text, system=system)
            repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
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


def _starte_kuerzung(klm, tg, conn, e, chat_id: int,
                     aenderungen: list[dict], *,
                     notiz_verbraucht: bool = False) -> bool:
    """Stoesst die Kuerzung an, wenn der Erkenner eine erkannt hat (art
    ``szene_kuerzen``, interview_theater/kuerzung.py).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``: dort
    wird nur in die Datenbank geschrieben, hier faellt eine Nachricht in die
    Gruppe an und ein minutenlanger Modellaufruf. ``kuerzung.starte`` gibt ihn
    sofort an einen eigenen Thread ab.

    **Hoechstens EINE je Lauf**, wie beim Schreibauftrag: die zweite liefe in
    die Sperre je chat_id und ergaebe nur ein 'ich schreibe gerade noch'.

    Ein leerer ``wert`` ist kein Fehler, sondern die Aussage "die ganze
    Geschichte": nach einem Prosalauf gibt es keine Szenennummer zu nennen.

    **Aber nur, solange Geschichten geschrieben werden** (30.09.2026,
    vorlaeufige Voreinstellung, Entscheidung bei Birk): ab der Phase, in der
    Theatertexte entstehen (``szene.schreibt_prosa`` falsch), liest die
    Gruppe einen Theatertext -- ein Lauf ueber die ganze Kurzgeschichte waere
    teuer und am Gemeinten vorbei. Dort gibt es ohne Nummer keinen Lauf,
    sondern eine Rueckfrage in einem Satz (``kuerzung.TEXT_WELCHE_SZENE``).
    Der Knopf "Kuerzer" unter der Kurzgeschichte ist davon nicht betroffen:
    er meint die Geschichte ausdruecklich.

    Den Pruef-Vermerk fuer spaetere Szenen setzt ``kuerzung.starte`` selbst,
    wie auf dem Knopfweg.

    **Nur mit ``ueberarbeitung.aktiv()`` (Padua), Abschlussreview Fix 5:**
    haelt gerade ein Szenen- oder Geschichtenlauf eine Sperre
    (``ueberarbeitung.laeuft``), laeuft KEINE Kuerzung an -- die Pruefung des
    Ganzen in Phase 6 haelt nur die Geschichtensperre, eine Kuerzung von
    Szene 2 braeuchte nur die (freie) Szenensperre, und
    ``schleife.stelle_wieder_her`` schriebe die gekuerzte Szene danach still
    zurueck. Die Gruppe bekommt dieselbe "laeuft noch"-Zeile wie der Knopf --
    ausser die Nachricht hat den Lauf als Regie-Notiz selbst gestartet
    (``notiz_verbraucht``, Fix 3). Liefert True, wenn diese Zeile rausging
    (damit ``_starte_teil2`` sie nicht ein zweites Mal schickt)."""
    from interview_theater import kuerzung, szene  # spaeter Import, haelt den Modulkopf frei

    treffer = next(
        (a for a in aenderungen if a.get("art") == "szene_kuerzen"), None
    )
    if treffer is None:
        return False
    from interview_theater import ueberarbeitung

    if ueberarbeitung.aktiv() and ueberarbeitung.laeuft(chat_id):
        log.info("Kuerzung aus dem Chat zurueckgestellt, ein Lauf geht, chat_id=%s",
                 chat_id)
        if notiz_verbraucht:
            return False
        try:
            ueberarbeitung._sende(conn, tg, e, chat_id, ueberarbeitung.T._TEXT_LAEUFT_NOCH)
        except Exception:
            log.exception("Laeuft-noch-Zeile nicht zustellbar, chat_id=%s", chat_id)
            return False
        return True
    nummer = kuerzung.nummer_aus_wert(treffer.get("wert"))
    try:
        if nummer is None:
            # Padua Phasen TEIL 2: in der Ueberarbeitung (6/7) ist "kuerzer"
            # ohne Nummer die Szene, die gerade gezeigt wird -- nicht die
            # ganze Geschichte und keine Rueckfrage.
            from interview_theater import ueberarbeitung

            if (ueberarbeitung.aktiv() and phasen.aktuelle(conn, chat_id) in (
                    ueberarbeitung.PHASE_UEBERARBEITUNG, ueberarbeitung.PHASE_BUEHNE)):
                nummer = ueberarbeitung.aktuelle_szene(conn, chat_id)
        if nummer is None and not szene.schreibt_prosa(conn, chat_id):
            message_id = tg.sende(chat_id, kuerzung.T.TEXT_WELCHE_SZENE)
            # Wie die Notiert-Meldung (siehe unten in ``laufe``): ohne diesen
            # Eintrag sehen Erkenner und Gespraechsbot die Rueckfrage im
            # naechsten Fenster nicht, wenn die Gruppe nur mit einer Zahl
            # antwortet.
            repo.merke_bot_zeile(conn, chat_id, message_id, e, kuerzung.T.TEXT_WELCHE_SZENE)
            return False
        kuerzung.starte(conn, tg, klm, e, chat_id, nummer)
    except Exception:
        log.exception("Kuerzung konnte nicht gestartet werden, chat_id=%s", chat_id)
    return False


def _starte_entwurf_uebersicht(klm, tg, conn, e, chat_id: int,
                                aenderungen: list[dict]) -> None:
    """Stoesst eine Neugenerierung der Stufe-A-Uebersicht an, wenn der
    Erkenner ``uebersicht_aendern`` gefunden hat (Padua Phasen TEIL 1).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``/
    ``_starte_kuerzung``: dort wird nur in die Datenbank geschrieben, hier
    faellt ein minutenlanger Modellaufruf an. ``entwurf.starte_uebersicht``
    gibt ihn sofort an einen eigenen Thread ab (Zusage 2).

    **Phasengebunden ueber ``PHASEN_SPEZIFISCHE_ARTEN``, hier noch einmal
    geprueft.** ``wende_an()`` filtert ``uebersicht_aendern`` zwar schon
    gegen ``_ist_phasenpassend`` heraus -- aber nur fuer seine EIGENE, lokale
    Kopie der Liste, aus der ``wirkliche`` entsteht; der ``aenderungen``,
    den ``laufe()`` an diese Funktion weiterreicht, bleibt die ungefilterte
    Liste aus ``erkenne()``. Ohne die eigene Pruefung hier liefe eine
    Rueckmeldung zur Uebersicht ausserhalb Phase 5 (z. B. nachdem die Gruppe
    laengst in Phase 6 weiter ist) trotzdem einen neuen, bezahlten Lauf an.
    (Seit Padua Phasen TEIL 2 filtert ``laufe()`` die Liste selbst einmal
    vorab -- die eigene Pruefung hier bleibt als Wache fuer andere Aufrufer.)

    **Zusaetzlich profilgebunden** (nicht nur phasengebunden): ``ARTEN`` und
    ``PHASEN_SPEZIFISCHE_ARTEN`` sind geteilter, profilunabhaengiger Code --
    jede Gruppe, auch Dortmund, bekommt ``uebersicht_aendern`` im Schema-Enum
    des Erkenner-Aufrufs angeboten, und Dortmunds eigene Phase 5 (Schaerfung)
    existiert ebenfalls. Erkennt Dortmunds Modell die art trotzdem einmal
    (unwahrscheinlich, die deutsche Punktbeschreibung verlangt explizit eine
    bereits im Verlauf stehende generierte Uebersicht, die es bei Dortmund nie
    gibt) muss das ein stiller No-Op bleiben, kein echter, bezahlter
    Modellaufruf fuer ein Feature, das diese Gruppe nicht hat -- derselbe
    Grund, aus dem ``knoepfe/stationen.py`` (Task 11) den Uebersicht-Start
    nach der Schaerfung hinter denselben Schalter stellt.

    **Zusaetzlich fixierungsgebunden** (Final-Review-Fund, 03.10.2026): ist
    ``arbeitsstand.geschichte_uebersicht_fixiert_am`` schon gesetzt, ist die
    Uebersicht bestaetigt und ein weiterer ``uebersicht_aendern``-Treffer
    gehoert zu etwas anderem -- plausibel zu einer laufenden Szene in Stufe
    B, deren Rueckmeldung generisch genug ist, um wie eine Uebersicht-Kritik
    zu klingen ("die Spannungskurve ist mir zu flach"). Ohne diese Pruefung
    liefe ein zweiter, bezahlter Stufe-A-Lauf, dessen Bestaetigungsknoepfe
    sich ueber die noch offenen der Szene legen wuerden."""
    from interview_theater import workshop

    if not workshop.prosa_entwurf_aktiv():
        return
    if not _ist_phasenpassend(conn, chat_id, "uebersicht_aendern"):
        return
    arbeitsstand = repo.hole_arbeitsstand(conn, chat_id)
    if arbeitsstand is not None and arbeitsstand["geschichte_uebersicht_fixiert_am"]:
        return
    treffer = next(
        (a for a in aenderungen if a.get("art") == "uebersicht_aendern"), None
    )
    if treffer is None:
        return
    from interview_theater import entwurf

    entwurf.starte_uebersicht(conn, tg, klm, e, chat_id, treffer.get("wert") or None)


#: Arten, die neben einer ``text_ueberarbeiten`` im SELBEN Lauf wegfallen
#: (Padua Phasen TEIL 2, Flow-Audit B2): "mach die Mutter wuetender" ist
#: Rueckmeldung zum gezeigten Text -- keine Festlegung ("Noted:" ohne
#: Ueberarbeitung) und kein zweiter, eigener Schreibauftrag.
_VERDRAENGT_VON_UEBERARBEITUNG = frozenset({"festlegung_setzen", "szene_schreiben"})


def _ohne_konkurrenz_zur_ueberarbeitung(aenderungen: list[dict]) -> list[dict]:
    """Nimmt ``_VERDRAENGT_VON_UEBERARBEITUNG`` heraus, wenn der Lauf eine
    ``text_ueberarbeiten`` traegt -- nur mit ``ueberarbeitung.aktiv()``;
    ohne den Schalter bleibt die Liste unangetastet (Dortmund)."""
    from interview_theater import ueberarbeitung

    if not ueberarbeitung.aktiv():
        return aenderungen
    if not any(a.get("art") == "text_ueberarbeiten" for a in aenderungen):
        return aenderungen
    return [a for a in aenderungen
            if a.get("art") not in _VERDRAENGT_VON_UEBERARBEITUNG]


#: "scene 2: weniger Worte" -- die fuehrende Szenennummer einer
#: Rueckmeldung (``text_ueberarbeiten``). Der Teil vor dem Doppelpunkt geht
#: durch ``kuerzung.nummer_aus_wert`` (streng: nur "Szene N"/"scene N"/"N").
_NOTIZ_MIT_SZENE = re.compile(r"^\s*([^:]{1,20}):\s*(.+)$", re.DOTALL)


def _notiz_und_nummer(wert: str | None) -> tuple[str, int | None]:
    from interview_theater import kuerzung

    text = (wert or "").strip()
    treffer = _NOTIZ_MIT_SZENE.match(text)
    if treffer:
        nummer = kuerzung.nummer_aus_wert(treffer.group(1).strip())
        if nummer is not None:
            return treffer.group(2).strip(), nummer
    return text, None


def _laeuft_ein_lauf(chat_id: int) -> bool:
    """Haelt gerade ein Lauf dieser Gruppe eine Sperre (Szene, Geschichte,
    Sprechweisen, Uebersicht)? Dann wirkt eine TEIL-2-Art nicht -- z. B. hat
    ``ablauf`` dieselbe Nachricht nach "No, change it again" schon als
    Regie-Notiz verbraucht und den Lauf gestartet."""
    from interview_theater import entwurf, sprechweise, ueberarbeitung

    return (ueberarbeitung.laeuft(chat_id)
            or sprechweise._sperre_fuer(chat_id).locked()
            or entwurf._sperre_fuer(chat_id).locked())


_SCHAERFUNG_KEINE = re.compile(r"^\s*(?:none|keine|nothing|nichts)\b", re.IGNORECASE)
_SCHAERFUNG_SZENE = re.compile(r"^\s*(?:scene|szene)\s*(\d{1,2})\b", re.IGNORECASE)
_SCHAERFUNG_FIGUR = re.compile(r"^\s*(?:character|figur)\s+(.+?)\s*$", re.IGNORECASE)


def _entscheide_schaerfung(conn, tg, chat_id: int, wert: str) -> None:
    """``schaerfung_entscheidung`` (Flow-Audit B1): dieselben Rumpfe wie die
    Schaerfungs-Knoepfe (``knoepfe.szenen``)."""
    from interview_theater.knoepfe import szenen as knopf_szenen

    if _SCHAERFUNG_KEINE.match(wert or ""):
        knopf_szenen.verwirf_schaerfung(conn, tg, chat_id)
        return
    treffer = _SCHAERFUNG_SZENE.match(wert or "")
    if treffer:
        knopf_szenen.uebernimm_schaerfung_szene(conn, tg, chat_id, int(treffer.group(1)))
        return
    treffer = _SCHAERFUNG_FIGUR.match(wert or "")
    if treffer:
        knopf_szenen.uebernimm_schaerfung_figur(conn, tg, chat_id, treffer.group(1))


def _wartet_auf_uebertragung(conn, chat_id: int) -> bool:
    """Ist die Szene, an der Phase 7 gerade steht, noch ohne Buehnentext?"""
    from interview_theater import ueberarbeitung

    nummer = ueberarbeitung.aktuelle_szene(conn, chat_id)
    if nummer is None:
        return False
    zeile = next((s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == nummer),
                 None)
    return zeile is not None and not (zeile["volltext"] or "").strip()


def _starte_teil2(klm, tg, conn, e, chat_id: int, freigegeben: list[dict],
                  wirkliche: list[dict], *, notiz_verbraucht: bool = False,
                  besetzt_gemeldet: bool = False) -> None:
    """Die Wege der fuenf TEIL-2-Arten (Padua, "Chat wirkt, wo Knoepfe
    wirken"). ``freigegeben`` ist schon phasen- und profilgefiltert
    (``_ist_phasenpassend``); ``wirkliche`` traegt, was ``formen_setzen``/
    ``sprechweise_setzen`` tatsaechlich geschrieben haben.

    Kein Modellaufruf hier: was eins braucht (Ueberarbeitung, Sprechweisen,
    der naechste Szenenlauf), geht ueber die bestehenden ``starte``-Wege in
    einen eigenen Thread. Laeuft schon ein Lauf, wirken
    ``text_ueberarbeiten``/``fassung_abnehmen`` NICHT (nur Log) -- siehe
    ``_laeuft_ein_lauf``. Jede Art in ihrem eigenen try: ein Fehler hier
    reisst die Notiert-Meldung nicht mit.

    ``notiz_verbraucht`` (Abschlussreview Fix 3): eine Nachricht dieses Laufs
    war schon die Regie-Notiz nach "No, change it again" -- ``ablauf`` hat
    mit ihr die Ueberarbeitung gestartet. Dann wirken
    ``text_ueberarbeiten``/``fassung_abnehmen`` still NICHT: keine zweite
    Ueberarbeitung und keine "laeuft noch"-Zeile ueber den Lauf, den die
    Gruppe gerade selbst angestossen hat. ``besetzt_gemeldet``: die Zeile
    kam in diesem Lauf schon (``_starte_kuerzung``) -- nicht zweimal."""
    from interview_theater import ueberarbeitung

    if not ueberarbeitung.aktiv():
        return

    def erste(art: str):
        return next((a for a in freigegeben if a.get("art") == art), None)

    ueberarbeiten = erste("text_ueberarbeiten")
    abnehmen = erste("fassung_abnehmen")
    try:
        # Hoechstens EINE der beiden je Lauf; neben einer Rueckmeldung ist ein
        # "passt" im selben Lauf keine Abnahme der noch alten Fassung.
        if ueberarbeiten is not None or abnehmen is not None:
            if notiz_verbraucht:
                log.info("Ueberarbeitung/Abnahme aus dem Chat entfaellt, die "
                         "Nachricht war schon die Regie-Notiz, chat_id=%s", chat_id)
            elif _laeuft_ein_lauf(chat_id) and besetzt_gemeldet:
                log.info("Ueberarbeitung/Abnahme aus dem Chat zurueckgestellt, "
                         "Zeile schon gesendet, chat_id=%s", chat_id)
            elif _laeuft_ein_lauf(chat_id):
                # Fix-Runde 1 (Review Task 10): nicht still -- dieselbe Zeile
                # wie der Knopf in derselben Lage, genau einmal je Lauf.
                log.info("Ueberarbeitung/Abnahme aus dem Chat zurueckgestellt, "
                         "ein Lauf geht, chat_id=%s", chat_id)
                ueberarbeitung._sende(conn, tg, e, chat_id,
                                      ueberarbeitung.T._TEXT_LAEUFT_NOCH)
            elif ueberarbeiten is not None:
                notiz, nummer = _notiz_und_nummer(ueberarbeiten.get("wert"))
                ueberarbeitung.ueberarbeite(conn, tg, klm, e, chat_id, notiz, nummer)
            else:
                ueberarbeitung.nimm_ab(conn, tg, klm, e, chat_id)
    except Exception:
        log.exception("Ueberarbeitung/Abnahme aus dem Chat gescheitert, chat_id=%s",
                      chat_id)
    try:
        schaerfung = erste("schaerfung_entscheidung")
        if schaerfung is not None:
            _entscheide_schaerfung(conn, tg, chat_id, schaerfung.get("wert") or "")
    except Exception:
        log.exception("Schaerfungs-Entscheidung aus dem Chat gescheitert, chat_id=%s",
                      chat_id)
    geschrieben = {a.get("art") for a in wirkliche}
    try:
        if "formen_setzen" in geschrieben:
            offen = ueberarbeitung.formen_offen(conn, chat_id)
            if offen:
                # Abschlussreview Fix 4: eine Teilantwort bekommt eine Zeile,
                # welche Nummern noch fehlen -- statt "Noted" und Stille.
                ueberarbeitung._sende(
                    conn, tg, e, chat_id, ueberarbeitung.T._TEXT_FORMEN_FEHLEN.format(
                        nummern=", ".join(str(n) for n in offen)))
            elif not ueberarbeitung.sprechweisen_fixiert(conn, chat_id):
                ueberarbeitung.weiter_7(conn, tg, klm, e, chat_id)
            elif (not ueberarbeitung.laeuft(chat_id)
                  and _wartet_auf_uebertragung(conn, chat_id)):
                # Abschlussreview Fix 4: eine schon uebertragene Szene hat
                # eine neue Form (``_wende_formen_an`` hat ihren Text
                # zurueckgenommen) und ist jetzt wieder dran -- derselbe
                # Schrittweg wie nach einer Abnahme; der Lauf geht in einen
                # Thread (``szene.starte``).
                ueberarbeitung.weiter_7(conn, tg, klm, e, chat_id)
    except Exception:
        log.exception("Weiter nach der Formwahl gescheitert, chat_id=%s", chat_id)
    try:
        from interview_theater import knoepfe, sprechweise

        if ("sprechweise_setzen" in geschrieben
                and not ueberarbeitung.sprechweisen_fixiert(conn, chat_id)
                and not sprechweise._sperre_fuer(chat_id).locked()):
            # Die aktualisierte Liste mit denselben zwei Knoepfen.
            knoepfe.biete_sprechweisen(conn, tg, e, chat_id)
    except Exception:
        log.exception("Sprechweisen-Liste nach dem Chat gescheitert, chat_id=%s",
                      chat_id)


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


def _schliesse_interview_ab(klm, tg, conn, e, wirkliche: list[dict]) -> int | None:
    """Stoesst nach einem erkannten "fertig" das Zusammenfuegen und die eine
    Verdichtung des Interviews an (§ 10.6, ``aufnahme.starte_abschluss``).

    Nicht in ``wende_an``, aus demselben Grund wie ``_starte_szene``: dort
    wird nur in die Datenbank geschrieben, hier faellt ein
    Sprachmodell-Aufruf an und eine Nachricht in die Gruppe. Der Aufruf geht
    sofort an einen eigenen Thread -- der Erkenner-Nachlauf haengt nicht
    daran, und die Bestaetigung "Aufnahme beendet." steht laengst im Chat.

    Ein Fehlschlag hier darf die Meldung nicht mitreissen: der Modus ist schon
    aus, und der Nachhol-Arbeiter greift ein liegengebliebenes Interview beim
    naechsten Durchlauf ohnehin auf.

    Liefert die ``aufnahme_id``, wenn der Abschluss-Thread wirklich
    gestartet ist, sonst None."""
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
        return None
    try:
        aufnahme.starte_abschluss(conn, tg, klm, e, kopf_id)
    except Exception:
        log.exception("Interviewabschluss konnte nicht gestartet werden, id=%s", kopf_id)
        return None
    return kopf_id


#: Erkenner-Art -> (Ping-Pong-Art der Knopfleiste, Phase, in der sie traegt).
#: Nur die Arten, ueber die in ihrer Phase im Ping-Pong entschieden wird --
#: dort und nur dort gehoert die Grundleiste unter die Notiert-Meldung.
#:
#: Warum die Phase und nicht ``knoepfe.offene_art``: die Meldung geht raus,
#: NACHDEM der Wert geschrieben wurde -- die Art ist dann nicht mehr "offen".
_LEISTENARTEN = {
    "begriffe_setzen": ("begriffe", 1),
    "fragen_setzen": ("fragen", 2),
    # ``rahmen_setzen``/``geschichte_setzen`` standen hier bis zum
    # Brainstorming-Umbau (Padua, 02.10.2026): Phase 4 ist jetzt freies
    # Erfinden, jede Festlegung speichert sofort und bekommt die
    # 📌-Fassung mit genau einem Rueckgaengig-Knopf (siehe
    # ``_ZEILE_FESTGELEGT``) statt einer Ping-Pong-Grundleiste darunter.
}


def _sende_meldung(conn, tg, chat_id: int, text: str, wirkliche: list[dict],
                   lauf_id: int | None = None) -> int:
    """Schickt die Notiert-Meldung -- mit Grundleiste, wenn der Erkenner
    gerade die Art gespeichert hat, die in dieser Phase offen ist, und seit
    Karte U (01.10.2026) mit dem Undo-Knopf darunter.

    Der Anlass (Birk, Live-Befund 05.09.2026, 23:37): der Nachlauf laeuft
    NACH der Gespraechsantwort, die Leiste hing also unter der Antwort und
    nicht unter dem Wert. Sie gehoert dorthin, wo steht, worueber entschieden
    wird.

    Faellt die Tastatur aus (Telegram-Fehler), geht die Meldung trotzdem
    raus: der Wert ist wichtiger als seine Knoepfe.

    Der Undo-Knopf steht an BEIDEN Wegen: unter der Grundleiste als letzte,
    ruhige Zeile (mobil gilt ein Hauptknopf je Bildschirm), und ohne
    Grundleiste als einzige. Deshalb wird aus ``tg.sende`` dort
    ``knoepfe.sende_notiert_nur_undo`` -- derselbe Sendeweg wie jede andere
    Knopfnachricht, samt Mitschrift in ``nachricht``.

    Die Undo-Knopfzeile wird **genau einmal** angelegt und an beide Wege
    durchgereicht -- sonst bliebe je Meldung eine zweite, nie gezeigte Zeile
    offen liegen. Und sie hat ihr **eigenes** try: scheitert sie, steht die
    Grundleiste trotzdem da (Review-Fix Aufgabe 7)."""
    from interview_theater import knoepfe
    from interview_theater.knoepfe import basis

    try:
        # Begriffs-Korrektur in Phase 1 (Padua, Birk 05.10.2026, Brief
        # "p1-bleiben"): dieselbe Frage wie nach dem Vorschlagsblock --
        # aktualisierte Liste, "Yes, on to the questions" · "Change
        # something" · Undo -- statt der B5-Abschlussnachricht. Vor
        # ``undo_leiste`` unten, sonst laege eine zweite, nie gezeigte
        # Undo-Zeile offen.
        if wirkliche and all(a.get("art") == "begriffe_setzen" for a in wirkliche) \
                and basis.begriffe_bleiben_in_phase_1(conn, chat_id):
            return basis.biete_begriffe_aktualisiert(
                conn, tg, chat_id, str(wirkliche[-1].get("wert") or ""), lauf_id)
    except Exception:
        log.exception("Begriffe-Frage nach dem Erkennerlauf fehlgeschlagen, "
                      "chat_id=%s", chat_id)
    zusatz = []
    try:
        zusatz = knoepfe.undo_leiste(conn, chat_id, lauf_id)
    except Exception:
        log.exception("Undo-Knopf nicht angelegt, chat_id=%s", chat_id)
    try:
        phase = phasen.aktuelle(conn, chat_id)
        autosave_1_2 = False
        if phase in (1, 2):
            from interview_theater import workshop

            autosave_1_2 = workshop.autosave_phase1_2_aktiv()
        for aenderung in wirkliche:
            eintrag = _LEISTENARTEN.get(aenderung.get("art"))
            if eintrag is None or eintrag[1] != phase:
                continue
            wert = str(aenderung.get("wert") or "").strip()
            if not wert:
                continue
            # Padua Hotfix B5 (02.10.2026): macht GENAU dieses Speichern die
            # Phase abschliessbar, kommt statt "Notiert + Ja/Nein" und
            # danach "Phase abgeschlossen + Weiter" EINE Nachricht -- die
            # Abschlussnachricht mit "Weiter zu Phase N · Titel", "<Feld>
            # aendern" und dem Undo-Knopf (Karte U bleibt erfuellt).
            # "Ja, speichern" faellt weg: der Erkenner HAT den Wert schon
            # geschrieben. ``_biete_phase_an`` danach findet den Merkposten
            # gesetzt und schweigt.
            nur_dieses = all(a.get("art") == aenderung.get("art") for a in wirkliche)
            for alte in (knoepfe.ART_SPEICHERN, knoepfe.ART_ANDERS, knoepfe.ART_EIGENE):
                knoepfe._nimm_alte_leiste_ab(conn, tg, chat_id, alte)
            ergebnis = knoepfe.sende_abschluss_statt_meldung(
                conn, tg, chat_id, eintrag[0], text,
                nur_dieses_feld=nur_dieses, zusatz=zusatz,
            )
            if ergebnis is not None:
                return ergebnis[0]
            if autosave_1_2:
                # Padua P1-2 (siehe workshop.autosave_phase1_2_aktiv): kein
                # Phasenangebot faellig, aber auch keine Ja/Nein-Leiste mehr
                # -- der Wert steht schon (SPEC "Ueberschreiben ist der
                # Normalfall"), ``text`` traegt schon die 📌-Fassung
                # (``_meldungszeilen``), und der Undo-Knopf bleibt allein.
                return knoepfe.sende_notiert_nur_undo(
                    conn, tg, chat_id, text, lauf_id, leiste=zusatz)
            message_id, _ = knoepfe.sende_notiert_mit_leiste(
                conn, tg, chat_id, text, eintrag[0], wert, zusatz=zusatz
            )
            return message_id
    except Exception:
        log.exception("Leiste unter der Notiert-Meldung fehlgeschlagen, chat_id=%s", chat_id)
    if zusatz:
        try:
            return knoepfe.sende_notiert_nur_undo(
                conn, tg, chat_id, text, lauf_id, leiste=zusatz)
        except Exception:
            log.exception("Undo-Knopf unter der Notiert-Meldung fehlgeschlagen, "
                          "chat_id=%s", chat_id)
    return tg.sende(chat_id, text)


def _eintritt_nach_phasenwechsel(conn, tg, klm, e, chat_id: int, wirkliche: list[dict]) -> None:
    """Hat der Erkenner die Phase gesetzt, bekommt die Gruppe denselben
    Rahmen wie ueber den Knopf (06.09.2026): Kopfzeile, Einleitung,
    Checkliste und die Einstiegsknoepfe dieser Phase.

    Weich wie ``_biete_phase_an``: ein Fehlschlag hier darf die Notiert-Zeile
    nicht mitreissen."""
    nummern = [
        int(a["wert"]) for a in wirkliche
        if a.get("art") == "phase_setzen" and str(a.get("wert") or "").isdigit()
    ]
    if not nummern:
        return
    try:
        from interview_theater import knoepfe

        knoepfe.eintritt_in_phase(conn, tg, klm, e, chat_id, nummern[-1])
    except Exception:
        log.exception("Phaseneintritt nach dem Erkennerlauf fehlgeschlagen, chat_id=%s", chat_id)


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
        # Padua Phasen TEIL 2, Abschlussreview Fix 3: welche Nachrichten
        # dieser Lauf liest -- um zu erkennen, ob eine davon schon als
        # Regie-Notiz verbraucht ist (``ablauf.nimm_notiz_verbraucht``). Nur
        # mit dem Schalter; Dortmund liest hier nichts zusaetzlich.
        from interview_theater import ueberarbeitung

        stapel = ([n["message_id"] for n in repo.unextrahierte(conn, chat_id)]
                  if ueberarbeitung.aktiv() else [])
        aenderungen = erkenne(klm, conn, e, chat_id)
        if not aenderungen:
            return
        notiz_verbraucht = False
        if stapel:
            from interview_theater import ablauf

            notiz_verbraucht = ablauf.nimm_notiz_verbraucht(chat_id, stapel)
        # EINMAL gegen Phase und Profilschalter gefiltert (Padua Phasen TEIL
        # 2): dieselbe Liste geht an ``wende_an`` und an jeden Startweg
        # unten. Vorher bekamen ``_starte_szene``/``_starte_kuerzung`` die
        # ungefilterte Liste; fuer die profil- und phasenfreien Arten ist
        # der Filter ein No-Op. Danach, nur mit ``ueberarbeitung.aktiv()``:
        # neben einer Rueckmeldung zum Text faellt eine Festlegung bzw. ein
        # eigener Schreibauftrag im selben Lauf weg (Flow-Audit B2).
        freigegeben = _ohne_konkurrenz_zur_ueberarbeitung([
            a for a in aenderungen
            if _ist_phasenpassend(conn, chat_id, a.get("art"))
        ])
        # Der Stand VOR und NACH dem Anwenden, direkt um ``wende_an`` und
        # unter ``repo._LOCK`` -- Grundlage des Undo-Knopfs (Karte U).
        wirkliche, vorher, nachher = _wende_an_mit_schnappschuss(
            conn, e, chat_id, freigegeben)
        # Punkt 6 der Nacht-Simulation, zwei Wege zurueck zum Angebot:
        #
        # 1. Die Gruppe BITTET darum ("weiter", "naechste Phase", "fertig
        #    hier") -- der Erkenner liest das als ``phase_setzen`` ohne
        #    wirksame Nummer. Dann kommt die Abschlussnachricht mit "Weiter
        #    zu <Phase>" erneut.
        # 2. Die Gruppe hat "Noch etwas aendern" gedrueckt und danach etwas
        #    gespeichert -- genau EIN Angebot je Aenderung, nicht bei jeder
        #    Nachricht.
        #
        # Beides raeumt nur den Merkposten ab; verschickt wird weiter unten
        # ueber den einen Weg (``_biete_phase_an``).
        #
        # Ausnahme Phase 1 unter Padua (``_weiter_aus_phase_1``): dort ist
        # die Bitte schon das Weiter.
        wirkliche = wirkliche + _weiter_aus_phase_1(conn, chat_id, aenderungen)
        _erneuere_angebot_auf_bitte(conn, chat_id, aenderungen)
        if wirkliche:
            phasen.erneuere_nach_aenderung(conn, chat_id)
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
        _starte_szene(klm, tg, conn, e, chat_id, freigegeben, wirkliche)
        # Und dieselbe Bauart fuer die Kuerzung (30.09.2026, C10): aus den
        # erkannten Aenderungen, weil sie wie ``szene_schreiben`` nichts in
        # den Arbeitsstand schreibt und in ``wirkliche`` deshalb nie auftaucht.
        besetzt_gemeldet = _starte_kuerzung(
            klm, tg, conn, e, chat_id, freigegeben,
            notiz_verbraucht=notiz_verbraucht)
        # Padua Phasen TEIL 1 (03.10.2026): Rueckmeldung zur generierten
        # Geschichts-Uebersicht (Stufe A von Phase 5) -- derselbe Grund wie
        # bei _starte_szene/_starte_kuerzung, kein Schreibpfad in wende_an.
        _starte_entwurf_uebersicht(klm, tg, conn, e, chat_id, freigegeben)
        text = baue_meldung(wirkliche, conn, chat_id)
        # Dieselbe Notiert-Zeile nicht zweimal (06.09.2026, Testgruppe
        # 21:50/21:52: derselbe Szenenfolge-Block stand wortgleich zweimal im
        # Chat). Gespeichert wurde in so einem Fall trotzdem korrekt -- nur
        # die Meldung darueber ist ueberfluessig, und ein Bot, der dasselbe
        # zweimal sagt, sieht kaputt aus.
        if text is not None and _steht_schon_da(conn, chat_id, text):
            log.info("Notiert-Meldung als Wiederholung uebersprungen, chat_id=%s", chat_id)
            text = None
        if text is not None:
            lauf_id = _lege_ruecknahme_an(conn, e, chat_id, vorher, nachher, wirkliche)
            message_id = _sende_meldung(conn, tg, chat_id, text, wirkliche, lauf_id)
            if lauf_id is not None:
                # Unter welcher Nachricht der Knopf haengt -- gebraucht, um
                # nach der Ruecknahme genau ihre Grundleiste verfallen zu
                # lassen. Weich: scheitert es (busy DB), wirkt der Knopf
                # trotzdem, nur die Grundleiste verfaellt dann nicht -- und
                # Bot-Zeile, Phaseneintritt und Phasenangebot duerfen nicht
                # mit ausfallen.
                try:
                    repo.merke_erkenner_lauf_nachricht(conn, lauf_id, message_id)
                except Exception:
                    log.exception("Nachricht zum Erkennerlauf nicht gemerkt, "
                                  "chat_id=%s, lauf_id=%s", chat_id, lauf_id)
            # Wie ablauf.antworte: die gesendete Meldung wird als Bot-Nachricht
            # mitgeschrieben, damit sie im naechsten Verlaufsfenster steht.
            repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
        # Padua Phasen TEIL 2: die Wege der fuenf neuen Arten -- NACH der
        # Notiert-Meldung, damit "Noted: Scene 1: Chorus" vor dem naechsten
        # Schritt (Sprechweisen) im Chat steht.
        _starte_teil2(klm, tg, conn, e, chat_id, freigegeben, wirkliche,
                      notiz_verbraucht=notiz_verbraucht,
                      besetzt_gemeldet=bool(besetzt_gemeldet))
        # Hat die Gruppe im selben Zug die Phase gewechselt, kommt direkt
        # hinter der Meldung der Phasenrahmen (06.09.2026): derselbe Eintritt
        # wie ueber den Knopf und ueber ``/phase``.
        _eintritt_nach_phasenwechsel(conn, tg, klm, e, chat_id, wirkliche)
        # Direkt hinter der Notiert-Zeile: hat GENAU dieses Speichern die
        # naechste Phase moeglich gemacht, sagt der Bot es sofort
        # (06.09.2026). Hier ist die Stelle, an der die Voraussetzung
        # entsteht -- ein Zug spaeter waere es schon eine Erinnerung.
        _biete_phase_an(conn, tg, chat_id)
    except Exception:
        log.exception("Erkenner-Nachlauf fehlgeschlagen, chat_id=%s", chat_id)
        repo.merke_vorfall(
            conn,
            chat_id,
            getattr(e, "bot_name", None),
            "erkenner_nachlauf_fehler",
            "Erkenner-Nachlauf (anwenden/melden) fehlgeschlagen",
        )


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)

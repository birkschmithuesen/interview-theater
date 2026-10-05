"""Das Workshop-Profil: alles, was an diesem Einsatzort individuell ist.

**Warum es das gibt** (Birk, 06.09.2026, nach der Analyse
``docs/workshop-profil-analyse-2026-09-06.md``). Das Repository ist an 1217
Stellen "Dortmund": Alter der Gruppe, Traegerverein, Auffuehrungsort,
Formenliste, Phasennamen, der Wortlaut der Einleitungen. Solange es nur
einen Einsatzort gibt, ist das kein Problem. Sobald ein zweiter dazukommt
(Padua, Italienisch, andere Altersgruppe), muesste man entweder das Repo
gabeln oder bei jedem Workshop dieselben sechs Dateien von Hand umschreiben
-- und beim naechsten ``git pull`` waere es wieder weg.

Deshalb: alles Individuelle liegt unter ``workshop/<name>/`` und wird ueber
die Umgebungsvariable ``IT_WORKSHOP`` **je Prozess** eingehaengt. Weil die
Env schon heute je Gruppe geladen wird (``betrieb/gruppeN.env``), koennen
zwei Workshops parallel auf einem Server laufen.

**Ohne Variable gilt das eingebaute Vorgabeprofil** (``VORGABE_WERTE``) --
und das traegt exakt die Werte, die vor dem Umbau im Code standen. Das ist
die Zusage, an der dieser Umbau gemessen wird: mit
``IT_WORKSHOP=dortmund-2026`` und ohne Variable entstehen dieselben Prompts
wie vorher. ``tests/test_profil_bitgleich.py`` prueft beides.

**Format TOML, nicht YAML** (06.09.2026). Die Analyse schlaegt ``profil.yaml``
vor; PyYAML ist aber keine Abhaengigkeit dieses Projekts, und eine neue
Abhaengigkeit fuer eine Konfigurationsdatei ist der falsche Preis.
``tomllib`` steht seit Python 3.11 in der Standardbibliothek, und dieses
Projekt verlangt ohnehin 3.11. TOML ist genauso ohne Python-Kenntnis
lesbar und aenderbar -- Zahlen, Listen und mehrzeilige Texte (``\"\"\"...\"\"\"``)
schreiben sich darin sogar geradliniger als in YAML-Blockskalaren.

**Kein Profil-Element ist Python.** Wer eine Altersgruppe, einen Ort oder
einen Formennamen aendern will, aendert ``profil.toml`` oder eine
Markdown-Datei daneben -- nie Code. Wenn eine Anpassung Code braucht, liegt
sie in der falschen Schicht.

**Fehlerbild am Workshoptag ist die teuerste Waehrung.** Ein fehlendes oder
kaputtes Profil bricht den Start mit einer klaren Meldung ab
(``ProfilFehler``) -- kein Halbstart, bei dem der Bot laeuft und die Gruppe
den falschen Rahmen bekommt. ``scripts/pruefe_profil.py`` prueft dasselbe
vorher, ohne einen Bot zu starten.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

#: Die eine Umgebungsvariable, die ein Profil auswaehlt. Je Prozess gesetzt
#: (``betrieb/gruppeN.env``), nie global.
VARIABLE = "IT_WORKSHOP"

#: Wo die Profile liegen. ``IT_WORKSHOP_BASIS`` verschiebt das Verzeichnis --
#: gebraucht wird das von Tests und von ``scripts/pruefe_profil.py``, wenn
#: ein Profil an einer anderen Stelle geprueft werden soll. Im Betrieb steht
#: die Variable nicht.
BASIS_VARIABLE = "IT_WORKSHOP_BASIS"

_PAKET = Path(__file__).resolve().parent

#: Der Dateiname des Profils im Profilverzeichnis.
DATEI = "profil.toml"

#: Der Formen-Katalog. Eigene Datei, weil sie einer anderen Hand gehoert:
#: welche Formen es gibt, entscheiden Birk und die Choreografin, waehrend
#: profil.toml Zielgruppe, Orte und Rahmen traegt.
FORMEN_DATEI = "formen.toml"

#: Die Arbeitsphasen: Nummer, Kurzname, Satz, Stichwoerter.
PHASEN_DATEI = "phasen.toml"

#: Die Einleitungen, die die Gruppe beim Eintritt in eine Phase liest.
#: Eigene Datei, weil sie Nina und Birk gehoert und nicht dem Code -- es ist
#: der Wortlaut, den jemand im Chat liest, und er wird oefter angefasst als
#: die Phasenmechanik daneben.
PHASENTEXTE_DATEI = "phasentexte.toml"

#: Die Felder, ohne die ein Profil nicht startet. Punkte trennen Ebenen.
#: Bewusst kurz: was fehlen darf, faellt auf den Wert des Vorgabeprofils
#: zurueck -- was hier steht, ist das, dessen Fehlen am Workshoptag als
#: falscher Inhalt und nicht als Fehlermeldung auffiele.
PFLICHTFELDER = (
    "beschreibung",
    "sprache.code",
    "sprache.anrede",
    "zielgruppe.beschreibung",
)

#: Die Sprachen, fuer die es Chat- und Prompttexte gibt (Karte A1,
#: 30.09.2026). Deutsch steht im Code, jede weitere unter
#: ``interview_theater/sprachen/<code>/``. Ein Profil mit einer anderen
#: Sprache weist ``scripts/pruefe_profil.py`` ab: es liefe sonst halb
#: deutsch, ohne dass es jemand merkt.
SPRACHEN = ("de", "en")


class ProfilFehler(RuntimeError):
    """Ein Profil fehlt, ist unlesbar oder unvollstaendig.

    Eigene Klasse, damit ``bot.main`` und ``scripts/pruefe_profil.py`` sie
    von einem gewoehnlichen Programmierfehler unterscheiden koennen: bei
    einem Profilfehler hilft ein Blick in ``workshop/<name>/profil.toml``,
    bei allem anderen nicht."""


#: Das eingebaute Vorgabeprofil -- **exakt die Werte, die vor dem Umbau im
#: Code standen** (Stand 06.09.2026, Zweig ``feat/workshop-profil``).
#:
#: Es ist nicht "irgendein sinnvoller Ausgangspunkt", sondern die
#: Beweisgrundlage: ``workshop/dortmund-2026/profil.toml`` traegt dieselben
#: Werte, und ein Test vergleicht beide Baeume Feld fuer Feld. Wer hier
#: etwas aendert, aendert das Verhalten ohne Profil -- also fuer jeden
#: Prozess, in dem ``IT_WORKSHOP`` nicht gesetzt ist.
VORGABE_WERTE: dict[str, Any] = {
    # Ein Geruest ist ein angefangenes Profil: die Struktur steht, die
    # Inhalte fehlen. Es darf geladen und geprueft werden -- damit ein Test
    # daran nicht scheitert (E.1 Frage 8) --, aber kein Bot startet damit.
    # Wer es fertig macht, streicht diese Zeile.
    "geruest": False,
    "beschreibung": (
        "Zweitaegiger Theaterworkshop mit einem Migrantinnenverein in "
        "Dortmund, 05./06.09.2026."
    ),
    "sprache": {
        # Prompt- und Chatsprache. Steuert spaeter auch die Whisper-Sprache.
        "code": "de",
        # Wie die Gruppe angesprochen wird. Deutsch "ihr", italienisch "voi".
        "anrede": "ihr",
        # Was Whisper erkennen soll: ein ISO-639-1-Code ("de", "it") oder
        # "auto" -- dann schickt stt.py gar keine Sprache mit und Whisper
        # erkennt sie selbst (Karte A1, Birk E5). Eine Gruppe kann den Wert
        # fuer sich umstellen (gruppe.stt_sprache, /sprache, Knopf in Phase 3).
        "whisper": "de",
    },
    "datenschutz": {
        # E8 (Birk, 29.09.2026): ersetzt die Vornamen im Gespraechsverlauf
        # durch "Mitglied 1", "Mitglied 2" ..., bevor sie in einen Prompt
        # gehen -- ein Modell kann keinen Namen verwenden, den es nie sieht.
        # Aus in Dortmund: dort war der Name im Verlauf gewollt.
        "pseudonyme": False,
    },
    "zielgruppe": {
        # Der Satz, der sechsmal wortgleich in den Prompts steht.
        "beschreibung": "junge Frauen zwischen 15 und 18 Jahren",
        # Der Traegerkontext in Klammern; leer = keine Klammer.
        "traeger": "Migrantinnenverein Dortmund",
    },
    "orte": {
        # Wie die Prompts die Spielorte beschreiben. Seit dem 06.09.2026
        # steht hier bewusst KEINE Beispielliste: die Orte nennt die Gruppe,
        # ein Beispiel im Prompt wird nachgeplappert.
        "beschreibung": (
            "altersgerechte, lebensnahe Orte aus der Welt der Gruppe -- welche,\n"
            "bestimmt die Gruppe selbst (keine Beispielorte aus dieser Anweisung)."
        ),
        # Was ausgeschlossen ist.
        "ausgeschlossen": ["Club", "Disko", "Alkohol", "Nachtleben", "Drogen"],
        # Wo das fertige Stueck gezeigt wird.
        "auffuehrung": "auf einem oeffentlichen Platz oder in einer grossen Halle",
        # Orte, die in den Prompts als BEISPIEL vorkommen -- in einem
        # Satz ueber das Vorschlagen, in einem Layoutbeispiel. Nicht die
        # Orte des Stuecks: die nennt die Gruppe. Die Reihenfolge zaehlt,
        # die Prompts greifen ueber {{ort_beispiel_1}} ... darauf zu.
        "beispiele": ["Bushaltestelle", "Schulhof", "Kiosk", "Bahnhof"],
    },
    "projekt": {
        # Worum es in dem Stueck geht, in einem Satz -- so, wie es eine
        # Interviewerin einer fremden Person auf der Strasse sagt. Steht im
        # Auftrag fuer den Eroeffnungstext (knoepfe.ANWEISUNG_EROEFFNUNG).
        # Der lange Wortlaut, den die Workshopleitung den Gruppen erklaert
        # hat, steht als prompts/projekt.md daneben.
        "kurzbeschreibung": (
            "ein Theaterstueck ueber das Leben der Menschen in der "
            "Dortmunder Nordstadt; die Befragten sind Expertinnen und "
            "Experten fuer das Leben hier und erzaehlen persoenliche "
            "Geschichten, die im Theater im Depot in der Nachbarschaft "
            "sichtbar werden - ihre Geschichten werden erzaehlt"
        ),
    },
    "konflikt": {
        # Was an Stoff drin sein darf, und was nicht.
        "erlaubt": "Familie, Erwartungen, Zugehoerigkeit, Sprache, Zukunft",
        "ausgeschlossen": "Keine Gewaltverherrlichung",
    },
    # Laengen-Rhythmus je Szene (30.09.2026, Karte R). **aktiv = False** ist
    # die Zusage an Dortmund: ohne Variable und mit
    # IT_WORKSHOP=dortmund-2026 aendert sich kein Zeichen an einem Prompt,
    # und keine dieser Zahlen wird gelesen. Wer den Schalter umlegt, aendert
    # das Verhalten seines Profils -- nicht das des Repos.
    "laengen": {
        "aktiv": False,
        # Was "Kuerzer/Instagram" auf alle Budgets legt (Karte: 0,25).
        "kurz_faktor": 0.25,
        # Ab welchem Anteil des Budgets EIN Kuerzungslauf angehaengt wird.
        "nachzaehl_schwelle": 1.3,
        # Rueckfall fuer eine Form, die unter ``rahmen`` nicht steht.
        "vorgabe_min": 200,
        "vorgabe_max": 450,
        # Woerter je Szene, Formname -> [min, max]. Leer heisst: jede Form
        # nimmt vorgabe_min/vorgabe_max. Die Werte gehoeren ins Profil, weil
        # sie von Ort, Altersgruppe und Spieldauer abhaengen.
        "rahmen": {},
        # Die Rhythmus-Muster. Der Code waehlt eines je Gruppe und liest es
        # zyklisch ueber die Szenennummern -- ``kurz-lang-kurz`` heisst also
        # auch bei sieben Szenen kurz, lang, kurz, kurz, lang, kurz, kurz.
        # Jedes Muster traegt mindestens zwei VERSCHIEDENE Stufen: eine
        # Liste aus einer Stufe koennte gar nichts anderes als flach werden.
        "muster": [
            ["kurz", "lang", "kurz"],
            ["lang", "kurz", "schlag"],
            ["kurz", "kurz", "lang"],
            ["mittel", "lang", "schlag"],
        ],
    },
    # Der letzte Sprachpass (30.09.2026, Karte R). Vier mechanisch gezaehlte
    # Muster, Grenzwerte je 1.000 Woerter -- ausser dem Fazitsatz, der
    # positionell gezaehlt wird (nur in den letzten Saetzen) und deshalb je
    # TEXT zaehlt. Die Einheit steht im Schluesselnamen, damit sie niemand
    # raten muss.
    "sprachpass": {
        "aktiv": False,
        "gedankenstriche_je_1000": 6.0,
        "nicht_sondern_je_1000": 2.0,
        "adjektiv_dreier_je_1000": 2.0,
        "fazitsatz_je_text": 1,
    },
    # Die Weboberflaeche (02.10.2026, Padua). ``dashboard_log_einklappen``
    # klappt je Karte den Technikteil (Zahlen, Vorfaelle, Aufrufe) und die
    # Bot-Zuordnung in ein geschlossenes <details>. Aus ist die Zusage an
    # Dortmund: das Dashboard bleibt byte-gleich.
    # ``dashboard_gestaltet`` (P2, Aufgabe 3) gibt dem Dashboard die
    # Gestaltung aus ``web_gestalt`` (Tokens, Fortschritt je Gruppe, Hinweis
    # nur bei einem Problem). Aus heisst auch hier: byte-gleich wie vorher.
    # ``workbench_bearbeitbar`` (Padua, 03.10.2026): der Arbeitsstand-Tab
    # ("Workbench") mit Formularen. ``false`` macht ihn zur reinen
    # Statusansicht (``web.werkbank_koerper``), Aenderungen gehen dann nur
    # ueber den Chat, und der Werkbank-POST antwortet 403. An ist die Zusage
    # an Dortmund: Seite und Endpunkt bleiben byte-gleich.
    "web": {
        "dashboard_log_einklappen": False,
        "dashboard_gestaltet": False,
        "workbench_bearbeitbar": True,
        "phasennav_stepper": False,
    },
}


#: Der eingebaute Formen-Katalog -- **exakt die Werte, die vor dem Umbau in
#: ``szene.FORMEN``, ``szene.FORM_STICHWOERTER``, ``web_schreiben.FORMEN`` und
#: ``szenenfolge.FORM_VORGABE`` standen** (Stand 06.09.2026).
#:
#: Die Reihenfolge ist die der Knopfleiste (``knoepfe.biete_szenenform``):
#: erst die Sprechformen, dann die musikalischen. ``anzeige`` ist die
#: Schreibweise im Prompt-Fliesstext ("Dialog, Monolog, Chor, Lied, Rap"),
#: ``name`` die kleingeschriebene, die in der Datenbank landet.
#:
#: ``prosa`` steht bewusst **nicht** darin: sie ist die Formvariante der
#: Phase 6, die der Code setzt und die Gruppe nie waehlt.
VORGABE_FORMEN: dict[str, Any] = {
    # Die Form, mit der eine Szene startet, wenn die Vorschlagszeile keine
    # nennt, und der Rueckfall von ``szene.formdatei``.
    "vorgabe": "dialog",
    # Wie die Anzahl im Prompt-Fliesstext ausgeschrieben wird ("genau
    # fuenf: ..."). Muss zur Zahl der Eintraege passen;
    # scripts/pruefe_profil.py prueft das fuer deutschsprachige Profile.
    "anzahl_wort": "fuenf",
    "form": [
        {
            "name": "dialog",
            "anzeige": "Dialog",
            # "Dialog wird zuletzt geprueft" -- das Wort "Szene" steht in
            # fast jeder Formangabe, und Dialog ist ohnehin der Rueckfall.
            "stichwoerter": [
                "dialog", "gespraech", "gespräch", "gesprochen",
                "sprechtheater", "text", "sprechszene", "szene",
            ],
        },
        {
            "name": "monolog",
            "anzeige": "Monolog",
            "stichwoerter": ["monolog", "soloszene", "solo"],
        },
        {
            "name": "chor",
            "anzeige": "Chor",
            "stichwoerter": ["chor", "chorisch", "wir-form", "sprechchor"],
        },
        {
            "name": "lied",
            "anzeige": "Lied",
            "stichwoerter": ["lied", "song", "gesang", "gesungen", "singen",
                             "musik", "arie"],
        },
        {
            "name": "rap",
            "anzeige": "Rap",
            "stichwoerter": ["rap", "sprechgesang", "beat", "reim", "hip-hop",
                             "hiphop"],
        },
    ],
}


#: Die Arbeitsphasen -- **exakt die Werte, die vor dem Umbau in
#: ``phasen.PHASEN``, ``phasen.STICHWOERTER``, ``phasen.MEHRDEUTIG``,
#: ``phasen.ERSTE`` und ``phasen.MELDUNG`` standen** (Stand 06.09.2026).
#:
#: Die *Mechanik* bleibt generisch (Phase halten, springen, Journal
#: schreiben); was hier steht, ist der Inhalt: wie viele Stationen es gibt,
#: wie sie heissen und unter welchen Woertern eine Gruppe sie meint.
#:
#: ``stichwoerter``: zusaetzlich zum Kurznamen. Noetig, seit ein Kurzname
#: aus zwei Sachen besteht -- gegen "Setting, Figuren & Geschichte" trifft
#: ein Teilstringvergleich weder "wir sind noch beim Setting" noch "lasst
#: uns Figuren machen", und beides sind genau die Saetze, mit denen eine
#: Gruppe diese Phase benennt.
VORGABE_PHASEN: dict[str, Any] = {
    # Die Phase, die gilt, solange keine gesetzt wurde (``phase IS NULL``).
    "erste": 1,
    # Die Meldung, mit der jede Phasenaenderung hoerbar wird.
    "meldung": "Wir sind jetzt bei {bezeichnung}. Falls nicht, sagt es mir.",
    # Stichwoerter, die in mehr als einer Phase vorkommen, mit der
    # spaeteren Phase, die sie meinen, sobald die Gruppe schon dort ist:
    # "Schaerfung" heisst beides -- die am Material (5) und die am
    # fertigen Stueck (7).
    "mehrdeutig": {"5": 7},
    "phase": [
        {
            "nummer": 1, "name": "Begriffe",
            "satz": "Die im Plenum gesammelte Begriffsliste aufnehmen und ordnen.",
            "stichwoerter": ["begriffe", "begriff", "begriffsliste"],
        },
        {
            "nummer": 2, "name": "Fragen",
            "satz": "Aus den Begriffen Interviewfragen entwickeln.",
            # "interviewfragen" steht hier bewusst NICHT: der Vergleich
            # laeuft in beide Richtungen, und "interview" waere darin
            # enthalten -- die Gruppe landete beim Formulieren statt beim
            # Aufnehmen.
            "stichwoerter": ["fragen", "frage", "frageliste"],
        },
        {
            "nummer": 3, "name": "Interviews",
            "satz": "Interviews fuehren, das Material verdichten.",
            "stichwoerter": ["interviews", "interview", "aufnahmen"],
        },
        {
            "nummer": 4, "name": "Setting, Figuren & Geschichte",
            "satz": "Frei erfinden: worin es spielt, wer vorkommt, was passiert.",
            # "kernthema", "format" und "konflikt" bleiben als Altlast
            # stehen: eine Gruppe (oder ein Journaleintrag von gestern)
            # sagt weiter "wir sind beim Kernthema" und meint die Station,
            # an der erfunden wird.
            "stichwoerter": [
                "setting", "figuren", "figur", "rahmen", "rahmung",
                "kernthema", "kernthemas", "format", "konflikt",
                "hauptkonflikt", "geschichte", "handlung", "grobstruktur",
            ],
        },
        {
            "nummer": 5, "name": "Schaerfung",
            "satz": "Die erfundene Geschichte am Interviewmaterial schaerfen.",
            "stichwoerter": ["schaerfung", "schaerfen", "clustern", "verdichtungen"],
        },
        {
            "nummer": 6, "name": "Szenen als Geschichte",
            "satz": "Jede Szene als Prosa erzaehlen -- was passiert, noch ohne Form.",
            "stichwoerter": ["szenentexte", "szenentext", "szenen", "szene"],
        },
        {
            "nummer": 7, "name": "Feinschliff",
            "satz": ("Je Szene die Form waehlen, die Geschichte uebersetzen, "
                     "das Stueck pruefen."),
            "stichwoerter": ["durchlauf", "feinschliff", "stueckpruefung", "pruefrunde"],
        },
    ],
}

#: Die Einleitungen im Chat -- **exakt der Wortlaut, der vor dem Umbau in
#: ``phasentexte.EINLEITUNGEN`` stand** (Birk hat ihn am 06.09.2026
#: ausdruecklich bestaetigt; er wandert in eine Datei und aendert sich dabei
#: um kein Zeichen).
#:
#: Zwei bis vier Saetze je Phase: was hier passiert, was die Gruppe tut, was
#: ich tue, was am Ende steht. Keine Eigennamen -- weder erfundene Figuren
#: noch Orte: was hier als Beispiel steht, taucht spaeter als Vorschlag des
#: Bots wieder auf. Keine Slash-Befehle: beworben wird der Knopf.
VORGABE_PHASENTEXTE: dict[str, Any] = {
    "einleitung": {
        "1": (
            "Hier kommt eure Begriffsliste aus dem Plenum zu mir. Ihr schickt "
            "sie getippt oder als Sprachnachricht, so wie sie bei euch an der "
            "Wand steht. Ich halte sie fest, ordne sie und frage nach, wo ein "
            "Begriff noch zu gross ist. Am Ende stehen die Kernbegriffe, mit "
            "denen ihr weiterarbeitet."
        ),
        "2": (
            "Aus euren Begriffen werden jetzt die Interviewfragen. Ich schlage "
            "euch zehn vor, ihr sagt mir die Nummern von genau drei. Danach "
            "schauen wir, welche Frage heikel ist und wie ihr sie so stellt, "
            "dass sie leicht zu beantworten ist, und womit ihr ein Gespraech "
            "anfangt und aufhoert. Am Ende habt ihr einen Leitfaden zum "
            "Mitnehmen."
        ),
        "3": (
            "Jetzt fuehrt ihr die Interviews - den Leitfaden habt ihr dabei. So "
            "laeuft es: Ihr drueckt Aufnahme starten, dann nehmt ihr das Gespraech "
            "als Sprachnachrichten auf, so viele wie noetig, gern auch in "
            "Stuecken. Ich tippe alles mit. Am Ende drueckt ihr Interview beenden "
            "(oder sagt am Schluss der Aufnahme \"fertig\"). Dann fasse ich das "
            "Interview von selbst zusammen - die Themen und die woertlichen "
            "Zitate, mit denen wir spaeter arbeiten. Am Ende steht zu jedem "
            "Interview eine Zusammenfassung. Danach koennt ihr die "
            "Zusammenfassung und das Transkript ansehen und gegenpruefen."
        ),
        "4": (
            "Ab hier wird erfunden - ganz frei, ohne Material. Ihr denkt euch aus, "
            "wo euer Stueck spielt (Ort, Zeit, Anlass), wer darin vorkommt, und "
            "was passiert: die Geschichte im Groben, wie sie ausgeht, und die "
            "Szenenfolge mit Titel, einem Satz, den Figuren und einem Vorschlag "
            "fuer die Form. Ich helfe mit Vorschlaegen, wenn ihr wollt. Direkt "
            "danach kommen die Interviews ins Spiel und schaerfen, was ihr gebaut "
            "habt."
        ),
        "5": (
            "Jetzt kommen die Interviews zurueck. Ich lege neben jede Szene und "
            "jede Figur die Stellen aus euren Aufnahmen, die dazu passen, mit "
            "dem woertlichen Zitat. Eure Geschichte aendert sich dadurch nicht, "
            "sie wird genauer. Ihr entscheidet Vorschlag fuer Vorschlag und "
            "koennt noch eine Runde drehen."
        ),
        "6": (
            "Jetzt schreibe ich eure Geschichte am Stueck - eine Kurzgeschichte, "
            "wie in einem Buch: was passiert, wer da ist, was gesagt und "
            "gefuehlt wird, in Prosa. Wie viele Abschnitte es werden, entscheidet "
            "die Geschichte. Aus jedem Abschnitt wird danach eine Szene. Kein "
            "Theatertext, keine Form; das kommt im Feinschliff. Ihr lest sie und "
            "sagt mir, was anders werden soll."
        ),
        "7": (
            "Alle Szenen stehen als Geschichte. Jetzt der Feinschliff: Szene fuer "
            "Szene entscheidet ihr die Form - {{formen_liste_oder}} -, und ich "
            "uebersetze die Geschichte in genau diese Form. "
            "Danach lese ich euer Stueck einmal als Ganzes, wie ein Zuschauer, "
            "und sage euch zu jeder Frage, wo es traegt und wo nicht: "
            "Spannungsbogen, Figuren, Spannung, Nachvollziehbarkeit, Anfang und "
            "Ende, Sprechbarkeit. Zu jedem Punkt ein Vorschlag, den ihr in die "
            "Szene geben koennt. Ihr koennt das Textbuch jederzeit als Datei "
            "holen."
        ),
    },
    # Was statt der Einleitung der letzten Phase dasteht, solange **nicht**
    # jede Szene einen Text hat (06.09.2026, in der Simulation gemessen).
    # Der alte Text fing mit "Alle Szenen stehen" an -- ein Satz ueber die
    # Datenlage, den der Text nicht geprueft hat. Eine Behauptung ueber den
    # Stand gehoert an die Daten gebunden, sonst ist sie ein Versprechen.
    "letzte_offen": (
        "Hier seht ihr euer Textbuch am Stueck. Ein Teil der Szenen ist noch "
        "ungeschrieben - tippt eine davon an, dann hole ich das nach. Bei den "
        "fertigen achten wir auf die Uebergaenge und darauf, was sich beim "
        "Sprechen sperrig anfuehlt."
    ),
}


def _einfrieren(wert: Any) -> Any:
    """Macht aus dem geladenen TOML-Baum etwas Unveraenderliches.

    Ein Profil ist Konfiguration, keine Zustandsablage: wer es aus Versehen
    veraendert, aendert stillschweigend das Verhalten aller spaeteren
    Aufrufe im selben Prozess. Dicts werden zu ``MappingProxyType``, Listen
    zu Tupeln; alles andere bleibt, wie es ist."""
    if isinstance(wert, dict):
        return MappingProxyType({k: _einfrieren(v) for k, v in wert.items()})
    if isinstance(wert, list):
        return tuple(_einfrieren(v) for v in wert)
    return wert


def _vereinige(vorgabe: Any, eigen: Any) -> Any:
    """Legt ``eigen`` ueber ``vorgabe`` -- Ebene fuer Ebene, nicht als Ganzes.

    Ein Profil, das nur ``[zielgruppe] beschreibung = "..."`` setzt, soll den
    Traeger aus der Vorgabe behalten und nicht verlieren. Nur Dicts werden
    vereinigt; eine Liste ersetzt die Liste der Vorgabe vollstaendig (eine
    halb ueberschriebene Ortsliste waere schlimmer als eine falsche)."""
    if isinstance(vorgabe, dict) and isinstance(eigen, dict):
        zusammen = dict(vorgabe)
        for schluessel, wert in eigen.items():
            zusammen[schluessel] = _vereinige(vorgabe.get(schluessel), wert)
        return zusammen
    return eigen


@dataclass(frozen=True)
class Profil:
    """Ein geladenes Workshop-Profil -- eingefroren, ohne Zustand.

    ``name`` ist der Verzeichnisname (``dortmund-2026``) bzw. ``VORGABE_NAME``
    fuer das eingebaute Profil. ``verzeichnis`` ist ``None``, solange kein
    Profil eingehaengt ist -- dann gibt es auch keine Overlay-Dateien."""

    name: str
    verzeichnis: Path | None
    werte: Any
    #: Der Formen-Katalog aus ``formen.toml``, eingefroren wie ``werte``.
    formen: Any = None
    #: Die Arbeitsphasen aus ``phasen.toml``.
    phasen: Any = None
    #: Die Einleitungen aus ``phasentexte.toml``.
    phasentexte: Any = None

    def wert(self, pfad: str, vorgabe: Any = None) -> Any:
        """Ein Feld ueber seinen Punktpfad (``"zielgruppe.traeger"``).

        Liefert ``vorgabe``, wenn irgendein Schritt des Pfades fehlt -- ein
        Leser soll an einem nicht gesetzten Feld nicht abstuerzen, sondern
        das melden koennen, was er als Ersatz nimmt."""
        stelle: Any = self.werte
        for schritt in pfad.split("."):
            if not isinstance(stelle, (dict, MappingProxyType)):
                return vorgabe
            if schritt not in stelle:
                return vorgabe
            stelle = stelle[schritt]
        return stelle

    def geruest(self) -> bool:
        """Ein angefangenes Profil: die Struktur steht, die Inhalte fehlen.

        Es laesst sich laden und pruefen -- ein Test soll daran nicht
        scheitern (E.1 Frage 8) --, aber kein Bot startet damit."""
        return bool(self.wert("geruest", False))

    def fehlende_pflichtfelder(self) -> list[str]:
        """Welche Felder aus ``PFLICHTFELDER`` leer sind."""
        return [feld for feld in PFLICHTFELDER if not self.wert(feld)]


#: Der Name des eingebauten Profils. Er steht in Logzeilen und in der
#: Ausgabe von ``scripts/pruefe_profil.py``; er ist kein Verzeichnis.
VORGABE_NAME = "(eingebaut)"

#: Das eingebaute Profil als fertiges Objekt -- einmal eingefroren, von
#: allen geteilt.
VORGABE = Profil(VORGABE_NAME, None,
                 _einfrieren(VORGABE_WERTE), _einfrieren(VORGABE_FORMEN),
                 _einfrieren(VORGABE_PHASEN), _einfrieren(VORGABE_PHASENTEXTE))


def basis() -> Path:
    """Das Verzeichnis, unter dem die Profile liegen."""
    eigen = os.environ.get(BASIS_VARIABLE)
    if eigen:
        return Path(eigen).expanduser()
    return _PAKET.parent / "workshop"


def verzeichnis_fuer(name: str) -> Path:
    """Wo das Profil ``name`` liegt.

    Der Name kommt aus einer Umgebungsvariable, also aus der Hand eines
    Menschen -- die Pruefung auf Pfadtrenner steht deshalb hier und nicht
    im Vertrauen darauf, dass niemand ``IT_WORKSHOP=../../etc`` schreibt."""
    if not name or name != name.strip() or "/" in name or "\\" in name or name.startswith("."):
        raise ProfilFehler(
            f"{VARIABLE}={name!r} ist kein Profilname. Erlaubt ist der "
            f"Verzeichnisname unter {basis()}, z. B. 'dortmund-2026'."
        )
    return basis() / name


def lade(name: str) -> Profil:
    """Laedt das Profil ``name`` von der Platte.

    Wirft ``ProfilFehler`` mit einer Meldung, die sagt, was zu tun ist --
    fehlendes Verzeichnis, fehlende Datei, kaputtes TOML, fehlendes
    Pflichtfeld. Kein Halbstart: lieber gar kein Bot als einer mit dem
    falschen Rahmen."""
    verz = verzeichnis_fuer(name)
    datei = verz / DATEI
    if not verz.is_dir():
        raise ProfilFehler(
            f"Workshop-Profil {name!r} fehlt: {verz} gibt es nicht. "
            f"Entweder {VARIABLE} korrigieren oder das Verzeichnis anlegen "
            f"(Anleitung: docs/workshop-profil-umbau-2026-09-06.md)."
        )
    if not datei.is_file():
        raise ProfilFehler(
            f"Workshop-Profil {name!r} hat keine {DATEI}: {datei} fehlt."
        )
    werte = _vereinige(VORGABE_WERTE, _lies_toml(datei))
    formen = _vereinige(VORGABE_FORMEN, _lies_toml(verz / FORMEN_DATEI, pflicht=False))
    # Phasen und Phasentexte werden **nicht** Feld fuer Feld vereinigt,
    # sobald ein Profil eigene mitbringt: sie sind ein zusammenhaengender
    # Satz, kein Stapel einzelner Werte. Ein Profil mit drei Stationen
    # erbte sonst die Einleitungen der Phasen 4 bis 7 und einen
    # Mehrdeutigkeits-Eintrag fuer eine Phase, die es nicht hat.
    roh_phasen = _lies_toml(verz / PHASEN_DATEI, pflicht=False)
    stationen = _vereinige(VORGABE_PHASEN, roh_phasen)
    if "phase" in roh_phasen and "mehrdeutig" not in roh_phasen:
        stationen["mehrdeutig"] = {}
    roh_texte = _lies_toml(verz / PHASENTEXTE_DATEI, pflicht=False)
    texte = _vereinige(VORGABE_PHASENTEXTE, roh_texte)
    if "einleitung" in roh_texte:
        texte["einleitung"] = roh_texte["einleitung"]
    profil = Profil(name, verz, _einfrieren(werte), _einfrieren(formen),
                    _einfrieren(stationen), _einfrieren(texte))
    # Ein Geruest darf unvollstaendig sein -- es soll sich ansehen und
    # pruefen lassen, ohne dass ein Test daran scheitert (E.1 Frage 8).
    # Dass damit kein Bot startet, steht in ``bot.main`` und in
    # ``scripts/pruefe_profil.py``, wo es hingehoert: an den Start.
    fehlend = profil.fehlende_pflichtfelder()
    if fehlend and not profil.geruest():
        raise ProfilFehler(
            f"{datei}: Pflichtfeld(er) leer oder nicht gesetzt: "
            f"{', '.join(fehlend)}"
        )
    _pruefe_formen(profil, verz / FORMEN_DATEI)
    _pruefe_phasen(profil, verz / PHASEN_DATEI)
    return profil


def _lies_toml(datei: Path, pflicht: bool = True) -> dict[str, Any]:
    """Eine TOML-Datei des Profils. Fehlt eine nicht verpflichtende, gilt
    die Vorgabe -- ein Profil, das nichts an den Formen aendert, braucht
    keine ``formen.toml``."""
    try:
        return tomllib.loads(datei.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if pflicht:
            raise ProfilFehler(f"{datei} fehlt.") from None
        return {}
    except tomllib.TOMLDecodeError as fehler:
        raise ProfilFehler(f"{datei} ist kein gueltiges TOML: {fehler}") from fehler
    except OSError as fehler:
        raise ProfilFehler(f"{datei} ist nicht lesbar: {fehler}") from fehler


def _pruefe_formen(profil: "Profil", datei: Path) -> None:
    """Der Formen-Katalog muss benutzbar sein, bevor ein Bot startet.

    Was hier abbricht, waere sonst ein Fehlerbild mitten in Phase 7: eine
    Szene ohne Regelblock, eine Knopfleiste ohne Beschriftung, ein
    Rueckfall auf eine Form, die es nicht gibt."""
    eintraege = profil.formen.get("form") if profil.formen else None
    if not eintraege:
        raise ProfilFehler(f"{datei}: kein einziger [[form]]-Eintrag.")
    namen = []
    for nummer, eintrag in enumerate(eintraege, start=1):
        wert = (eintrag.get("name") or "").strip() if hasattr(eintrag, "get") else ""
        if not wert:
            raise ProfilFehler(f"{datei}: [[form]] Nr. {nummer} hat keinen 'name'.")
        if wert in namen:
            raise ProfilFehler(f"{datei}: Form {wert!r} steht zweimal.")
        namen.append(wert)
    vorgabe = profil.formen.get("vorgabe")
    if vorgabe not in namen:
        raise ProfilFehler(
            f"{datei}: vorgabe={vorgabe!r} ist keine der Formen "
            f"({', '.join(namen)}). Die Vorgabe ist der Rueckfall, wenn eine "
            f"Szene keine Form nennt -- sie muss es geben."
        )


def _pruefe_phasen(profil: "Profil", datei: Path) -> None:
    """Die Phasen muessen luecken- und dublettenfrei bei 1 anfangen.

    Die Nummern sind nicht Schmuck: sie stehen in der Datenbank
    (``arbeitsstand.phase``), in den Migrationen und in den Dateinamen der
    Phasenprompts. Eine Luecke waere eine Gruppe, die nicht weiterkommt."""
    eintraege = profil.phasen.get("phase") if profil.phasen else None
    if not eintraege:
        raise ProfilFehler(f"{datei}: kein einziger [[phase]]-Eintrag.")
    nummern = []
    for stelle, eintrag in enumerate(eintraege, start=1):
        nummer = eintrag.get("nummer") if hasattr(eintrag, "get") else None
        if not isinstance(nummer, int):
            raise ProfilFehler(
                f"{datei}: [[phase]] Nr. {stelle} hat keine ganzzahlige 'nummer'.")
        if not (eintrag.get("name") or "").strip():
            raise ProfilFehler(f"{datei}: Phase {nummer} hat keinen 'name'.")
        nummern.append(nummer)
    if sorted(nummern) != list(range(1, len(nummern) + 1)):
        raise ProfilFehler(
            f"{datei}: die Nummern muessen 1..{len(nummern)} sein, "
            f"lueckenlos und jede einmal -- sie sind: {sorted(nummern)}."
        )
    fehlend = sorted(set(phasentexte_einleitungen(profil)) - set(nummern))
    if fehlend:
        raise ProfilFehler(
            f"{PHASENTEXTE_DATEI}: Einleitung(en) fuer Phase(n) {fehlend}, "
            f"die es in {datei.name} nicht gibt."
        )
    mehrdeutig = phasen_mehrdeutig(profil)
    unbekannt = sorted(
        (set(mehrdeutig) | set(mehrdeutig.values())) - set(nummern))
    if unbekannt:
        raise ProfilFehler(
            f"{datei}: [mehrdeutig] nennt Phase(n) {unbekannt}, die es nicht gibt."
        )


def phasenliste(profil: Profil | None = None) -> tuple[tuple[int, str, str], ...]:
    """Die Arbeitsphasen als ``(Nummer, Kurzname, Satz)`` -- die Form, die
    ``phasen.PHASEN`` seit jeher hat, jetzt aus dem Profil."""
    profil = profil or aktiv()
    return tuple(
        (e["nummer"], e["name"], e.get("satz", ""))
        for e in sorted(profil.phasen.get("phase", ()), key=lambda e: e["nummer"])
    )


def phasen_stichwoerter(profil: Profil | None = None) -> dict[int, tuple[str, ...]]:
    """Woerter, unter denen eine Phase gemeint sein kann."""
    profil = profil or aktiv()
    return {
        e["nummer"]: tuple(e.get("stichwoerter", ()))
        for e in profil.phasen.get("phase", ())
    }


def phasen_mehrdeutig(profil: Profil | None = None) -> dict[int, int]:
    """Stichwoerter, die zwei Phasen meinen koennen, mit der spaeteren.

    Die Schluessel stehen in TOML als Text (``[mehrdeutig] 5 = 7``) und
    werden hier zu Zahlen -- eine Phasennummer ist eine Zahl, und ein Leser
    soll nicht wissen muessen, aus welchem Dateiformat sie kam."""
    profil = profil or aktiv()
    return {int(k): int(v) for k, v in profil.phasen.get("mehrdeutig", {}).items()}


def phasen_meldung(profil: Profil | None = None) -> str:
    """Die Zeile, mit der ein Phasenwechsel gemeldet wird (mit
    ``{bezeichnung}`` als Fuellstelle)."""
    profil = profil or aktiv()
    return profil.phasen.get("meldung", "")


def phase_erste(profil: Profil | None = None) -> int:
    """Die Phase, die gilt, solange keine gesetzt wurde."""
    profil = profil or aktiv()
    return int(profil.phasen.get("erste", 1))


def phase_letzte(profil: Profil | None = None) -> int:
    """Die hoechste Phasennummer -- eine Stelle statt einer 7 an sechs."""
    liste = phasenliste(profil)
    return liste[-1][0] if liste else 0


def phasentexte_einleitungen(profil: Profil | None = None) -> dict[int, str]:
    """Die Einleitung je Phase, im Wortlaut. Platzhalter stehen noch drin --
    gefuellt wird in ``phasentexte.py``, wo auch der Hot-Reload sitzt."""
    profil = profil or aktiv()
    roh = profil.phasentexte.get("einleitung", {}) if profil.phasentexte else {}
    return {int(k): v for k, v in roh.items()}


def phasentexte_letzte_offen(profil: Profil | None = None) -> str:
    """Was statt der Einleitung der letzten Phase dasteht, solange nicht
    jede Szene einen Text hat."""
    profil = profil or aktiv()
    return profil.phasentexte.get("letzte_offen", "") if profil.phasentexte else ""


#: Geladene Profile je Name. Ein Profil wird einmal je Prozess von der Platte
#: gelesen -- anders als die Prompts ist es **kein** Hot-Reload-Kandidat: eine
#: halb gespeicherte ``profil.toml`` mitten im Workshop waere genau der
#: Halbstart, den dieses Modul verhindern soll.
_GELADEN: dict[str, Profil] = {}


def aktiv() -> Profil:
    """Das Profil dieses Prozesses -- aus ``IT_WORKSHOP``, sonst die Vorgabe.

    Die Variable wird bei **jedem** Aufruf gelesen und das Ergebnis je Name
    zwischengespeichert. Das kostet einen Dict-Zugriff und haelt die Zusage
    aus D.5 der Analyse: kein Profilzustand in einem Modul-Global, das ein
    zweites Profil im selben Prozess falsch beantworten wuerde."""
    name = (os.environ.get(VARIABLE) or "").strip()
    if not name:
        return VORGABE
    profil = _GELADEN.get(name)
    if profil is None:
        profil = lade(name)
        _GELADEN[name] = profil
    return profil


def name() -> str:
    """Der Name des aktiven Profils -- der Cache-Schluessel der Prompts."""
    return aktiv().name


def vergiss() -> None:
    """Leert den Profil-Zwischenspeicher. Nur fuer Tests und
    ``scripts/pruefe_profil.py`` -- im Betrieb wird ein Profil nie neu
    geladen (siehe ``_GELADEN``)."""
    _GELADEN.clear()
    _PLATZHALTER.clear()


#: Die Platzhalter je Profilname. Sie haengen nur an ``profil.toml``, und die
#: wird je Prozess einmal gelesen -- also einmal bauen, nicht je Prompt.
_PLATZHALTER: dict[str, dict[str, str]] = {}


def _liste(wert: Any, trenner: str = ", ") -> str:
    """Eine Liste aus dem Profil als Fliesstext. Ein einzelner String bleibt,
    wie er ist -- wer ``ausgeschlossen = "Club und Disko"`` schreibt, meint
    genau das."""
    if isinstance(wert, (tuple, list)):
        return trenner.join(str(teil) for teil in wert)
    return "" if wert is None else str(wert)


def formen(profil: Profil | None = None) -> tuple[str, ...]:
    """Die Formen, die eine Szene haben kann -- kleingeschrieben, in der
    Reihenfolge der Knopfleiste.

    Die eine Quelle. ``szene.FORMEN`` und ``web_schreiben.FORMEN`` lesen
    beide hier (D.8 der Analyse: sie trugen dieselbe Tupel zweimal, und die
    Weboberflaeche haette sonst eine andere Formenliste zeigen koennen als
    der Chat)."""
    profil = profil or aktiv()
    return tuple(e["name"] for e in profil.formen.get("form", ()))


def form_anzeige(profil: Profil | None = None) -> tuple[str, ...]:
    """Dieselben Formen, wie sie im Prompt-Fliesstext geschrieben werden
    ("Dialog"). Fehlt ``anzeige``, wird der Name gross geschrieben."""
    profil = profil or aktiv()
    return tuple(
        e.get("anzeige") or e["name"].capitalize()
        for e in profil.formen.get("form", ())
    )


def form_stichwoerter(profil: Profil | None = None) -> dict[str, tuple[str, ...]]:
    """Woerter, unter denen eine Form gemeint sein kann. Das Feld
    ``szene.form`` ist frei -- die Gruppe entscheidet, nicht der Code --,
    und "gesungen" muss trotzdem beim Lied landen."""
    profil = profil or aktiv()
    return {
        e["name"]: tuple(e.get("stichwoerter", ()))
        for e in profil.formen.get("form", ())
    }


def form_vorgabe(profil: Profil | None = None) -> str:
    """Die Form, die gilt, wenn keine genannt ist -- der Rueckfall von
    ``szene.formdatei`` und die Vorgabe der Szenenfolge."""
    profil = profil or aktiv()
    return profil.formen.get("vorgabe", "")


#: Wie eine Auswahl im Fliesstext verbunden wird ("Lied oder Rap"). Hier und
#: nicht in sprache.py, weil sprache.py dieses Modul importiert (Karte A1).
_ODER = {"de": " oder ", "en": " or "}


def platzhalter(profil: Profil | None = None) -> dict[str, str]:
    """Die Werte, die ``{{...}}`` in einem Prompt fuellen.

    Nur die **einzeiligen** Werte aus ``profil.toml``. Zusammenhaengende
    Prosa (der Rahmenblock, ein Formen-Regelblock) kommt nicht von hier,
    sondern als Markdown-Datei aus ``workshop/<name>/prompts/`` --
    ``anweisungen.platzhalter()`` legt beides zusammen. Der Grund steht in
    E.1 Frage 1 der Analyse: wer Prosa in eine Konfigurationsdatei presst,
    bekommt unlesbare Blockskalare; wer Zahlen in Markdown laesst, kann sie
    nicht pruefen.

    Ein Wert wird eingesetzt, **wie er dasteht** -- er wird nicht neu
    umbrochen. Ein Platzhalter gehoert deshalb an eine Stelle im Prompt, an
    der der Wert in eine Zeile passt; alles andere ist ein Baustein und
    keine Variable."""
    profil = profil or aktiv()
    fertig = _PLATZHALTER.get(profil.name)
    if fertig is not None:
        return fertig
    werte = {
        "beschreibung": _liste(profil.wert("beschreibung", "")),
        "sprache": _liste(profil.wert("sprache.code", "")),
        "anrede": _liste(profil.wert("sprache.anrede", "")),
        "zielgruppe": _liste(profil.wert("zielgruppe.beschreibung", "")),
        "zielgruppe_traeger": _liste(profil.wert("zielgruppe.traeger", "")),
        "orte": _liste(profil.wert("orte.beschreibung", "")),
        "orte_ausgeschlossen": _liste(profil.wert("orte.ausgeschlossen", ())),
        "auffuehrungsort": _liste(profil.wert("orte.auffuehrung", "")),
        "konflikt_erlaubt": _liste(profil.wert("konflikt.erlaubt", "")),
        "konflikt_ausgeschlossen": _liste(profil.wert("konflikt.ausgeschlossen", "")),
        "projekt_kurz": _liste(profil.wert("projekt.kurzbeschreibung", "")),
    }
    # Der Konfliktrahmen in seinen zwei Satzformen (01.10.2026, Karte P-Fix,
    # Birks Punkt 5). Ein Profil darf ``konflikt.erlaubt`` leer lassen; dann
    # soll in der Vorlage kein Satzzeichen verwaisen -- aus "conflict may be
    # serious -- {{konflikt_erlaubt}}." wird sonst "conflict may be serious
    # -- ." und aus "({{konflikt_erlaubt}})" ein leeres Klammerpaar.
    # Gerechnet wird HIER und nicht in der Markdown-Vorlage: eine Vorlage
    # kennt keine Bedingung, und zwei Vorlagen je Fall waeren zwei
    # Wahrheiten. Die Form steht im Namen -- Strich fuer den langen
    # Rahmenblock, Klammer fuer den kurzen.
    erlaubt = werte["konflikt_erlaubt"].strip()
    werte["konflikt_erlaubt_strich"] = f" -- {erlaubt}" if erlaubt else ""
    werte["konflikt_erlaubt_klammer"] = f" ({erlaubt})" if erlaubt else ""
    # Die Beispielorte einzeln ({{ort_beispiel_1}} ...) und als Aufzaehlung.
    # Einzeln, weil ein Prompt sie an verschiedenen Stellen und in
    # verschiedenen Rollen braucht: einmal als Ort, an dem sich zwei
    # treffen, einmal als Zeile in einem Layoutbeispiel.
    beispiele = profil.wert("orte.beispiele", ()) or ()
    for nummer, ort in enumerate(beispiele, start=1):
        werte[f"ort_beispiel_{nummer}"] = str(ort)
    werte["orte_beispiele"] = _liste(beispiele)
    anzeige = form_anzeige(profil)
    werte.update({
        # "genau fuenf" -- ausgeschrieben, weil es im Fliesstext steht.
        "formen_anzahl": _liste(profil.formen.get("anzahl_wort", "")),
        # "Dialog, Monolog, Chor, Lied, Rap"
        "formen_liste": ", ".join(anzeige),
        # "Dialog, Monolog, Chor, Lied oder Rap" -- fuer die Stellen, an
        # denen der Satz eine Auswahl beschreibt und kein Verzeichnis.
        "formen_liste_oder": (
            _ODER.get(str(profil.wert("sprache.code", "de")), " oder ").join(
                [", ".join(anzeige[:-1]), anzeige[-1]])
            if len(anzeige) > 1 else "".join(anzeige)
        ),
        "form_vorgabe": form_vorgabe(profil),
        "form_vorgabe_anzeige": next(
            (a for n, a in zip(formen(profil), anzeige) if n == form_vorgabe(profil)),
            "",
        ),
    })
    _PLATZHALTER[profil.name] = werte
    return werte


def prosa_entwurf_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 5 (Prose Draft) die zweistufige Uebersicht-dann-Szenen-
    Erzeugung faehrt (Padua Phasen TEIL 1, 03.10.2026, entwurf.py).

    Vorgabe false -- wie ``[laengen] aktiv``: ohne diese Zeile im Profil
    bleibt Phase 5 genau das, was sie vorher war (die automatische
    Schaerfung, sonst nichts). Dortmund setzt die Zeile nicht und bleibt
    unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("prosa_entwurf.aktiv", False))


def diskussion_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 1 die Hintergrund-Diskussionsaufnahme faehrt (Padua Phase
    1+2 Umbau, 03.10.2026).

    Vorgabe false -- wie ``[laengen] aktiv``: ohne diese Zeile im Profil
    bleibt Phase 1 genau das, was sie vorher war. Dortmund setzt die Zeile
    nicht und bleibt unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("diskussion.aktiv", False))


def fragen_weich_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 2 sensible Fragen zusaetzlich in eine weiche Fassung
    umschreiben laesst (``VORSCHLAG FRAGEN WEICH:``, Angebot nach der letzten
    Entscheidung, weiche Fassung im Leitfaden).

    Vorgabe true -- Dortmund bleibt unberuehrt. Padua schaltet es ab (Birk,
    03.10.2026 live: „Die ganze Softwaregeschichte beim Fragen entwickeln
    kannst du fuer Padua deaktivieren [...] Es hat nicht gut funktioniert,
    aber deaktivier das einfach.“). Ausgeschaltet heisst: kein Prompt-Auftrag,
    nichts gespeichert, kein Angebot, im Leitfaden steht die Frage selbst."""
    profil = profil or aktiv()
    return bool(profil.wert("fragen_weich.aktiv", True))


def fragen_ab_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 2 den A/B-Vergleich eigene-vs-KI-Fragen faehrt (Padua Phase
    1+2 Umbau, 03.10.2026).

    Vorgabe false -- wie ``[laengen] aktiv``: ohne diese Zeile im Profil
    bleibt Phase 2 genau das, was sie vorher war. Dortmund setzt die Zeile
    nicht und bleibt unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("fragen_ab.aktiv", False))


def fragen_eigene_min(profil: Profil | None = None) -> int:
    """Ab wie vielen eigenen Fragen der Knopf "Suggest questions" (und der
    Schluss "eigene Fragen fertig") in Phase 2 gilt (Padua, Birk 05.10.2026
    14:05). Vorgabe 0 -- ohne ``[fragen] eigene_min`` bleibt alles wie
    bisher; Dortmund setzt die Zeile nicht."""
    profil = profil or aktiv()
    return int(profil.wert("fragen.eigene_min", 0))


def workbench_bearbeitbar(profil: Profil | None = None) -> bool:
    """Ob der Arbeitsstand-Tab ("Workbench") Formulare traegt und der
    Werkbank-POST schreibt (Padua, 03.10.2026, Karte t_49e7354c).

    Vorgabe true -- Dortmund setzt die Zeile nicht und bleibt byte-gleich.
    Padua setzt false: dort ist die Werkbank reine Anzeige, geaendert wird
    im Chat (Birk: "Workbench reiner Status-Ausspieler")."""
    profil = profil or aktiv()
    return bool(profil.wert("web.workbench_bearbeitbar", True))


def prueflauf_aktiv(profil: Profil | None = None) -> bool:
    """Der Pruefllauf vor jeder Anzeige eines Textes (Padua Phasen TEIL 2,
    03.10.2026): Richterfragen -> Ueberarbeitung -> neu bewerten, hoechstens
    ``schleife.RUNDEN_MAX`` Runden, danach Sprachpass/Nachpass. Ohne den
    Schalter laeuft jeder Szenen- und Prosalauf wie vorher."""
    profil = profil or aktiv()
    return bool(profil.wert("prueflauf.aktiv", False))


def ueberarbeitung_aktiv(profil: Profil | None = None) -> bool:
    """Die Padua-Fassung der Phasen 6 (Rewrite) und 7 (Stage Version):
    erst das Ganze, dann Szene fuer Szene; Formwahl und Sprechweisen per
    Chat; Lesen im Script-Tab statt im Chat; die Chat-Arten dazu
    (erkenner.PROFILSCHALTER_DER_ARTEN). Ohne den Schalter bleiben 6 und 7
    wie vorher."""
    profil = profil or aktiv()
    return bool(profil.wert("ueberarbeitung.aktiv", False))


def interview_fliesstext(profil: Profil | None = None) -> bool:
    """Ein Interview = EINE Transkriptblase im Web-Chat (Padua, 04.10.2026,
    Karte t_ea994c7f): jeder fertige Teil schreibt dieselbe Blase als
    Fliesstext weiter, statt eine eigene "Interview N, Teil K:"-Nachricht
    zu schicken; dazu gehen "Aufnahme beendet.", die Abschlusszeile und
    "war sehr kurz" als Systemzeilen raus.

    Vorgabe false -- Dortmund und das eingebaute Profil bleiben bitgleich.
    Gilt nur fuer Web-Gruppen (``aufnahme.fliesstext_aktiv``): Telegram
    behaelt auch mit dem Schalter das Echo je Teil samt Leiste."""
    profil = profil or aktiv()
    return bool(profil.wert("interview.fliesstext", False))


def modellwahl_einwilligung_aktiv(profil: Profil | None = None) -> bool:
    """Ob vor einem Claude-Szenenlauf die US-Provider-Einwilligungsfrage
    ueberhaupt gestellt wird (Padua Modellwahl-Nachtrag, 04.10.2026, Birk:
    "nur die Interviews auf Kimi, aller Rest auf Opus").

    Vorgabe true -- Dortmund und das eingebaute Profil bleiben dadurch
    unveraendert (Einwilligung noetig). Padua setzt false: sobald der
    Betreiber Claude erlaubt (IT_SZENE_ANBIETER=claude), laeuft jede Phase
    ausser Phase 3 (Interviews) ohne Rueckfrage auf Claude --
    ``szene_claude.ist_aktiv``/``angebot_faellig``/``wartet_auf_antwort``
    und die Erkenner-Art ``szene_usa`` lesen diesen Schalter (naechster
    Task)."""
    profil = profil or aktiv()
    return bool(profil.wert("modellwahl.einwilligung", True))


def modellwahl_zitate_an_claude_aktiv(profil: Profil | None = None) -> bool:
    """Ob woertliche Interview-Belegzitate im Claude-Szenen-Prompt stehen
    duerfen (Padua Modellwahl-Nachtrag, 04.10.2026; Birk live 18:20
    bestaetigt: die interviewten Personen werden vor der Aufnahme darauf
    hingewiesen).

    Vorgabe true -- unveraendertes Verhalten. Padua setzt die Zeile
    explizit auf true, damit die Entscheidung im Profil steht statt nur
    implizit vom Default zu kommen. Mit false entfernt
    ``szene._kernpaket_text`` den woertlichen Zitattext fuer einen
    Claude-Lauf (Thema/Zuordnung bleiben) -- der Unterschalter bleibt
    damit jederzeit mit einer Zeile umkehrbar."""
    profil = profil or aktiv()
    return bool(profil.wert("modellwahl.zitate_an_claude", True))


def autosave_phase1_2_aktiv(profil: Profil | None = None) -> bool:
    """Ob Phase 1 (Begriffe) und Phase 2 (Eroeffnung) einen Vorschlag sofort
    speichern statt der Ja/Nein-Rueckfrage "Ja, speichern" / "Nein, nochmal
    aendern" (Padua P1-2, Abnahme-Befund t_0b702d1d: beide Knoepfe schrieben
    seit dem 02.10.2026 ohnehin denselben Wert -- die Rueckfrage war nur noch
    ein Klick ohne Entscheidung).

    Mit dem Schalter laeuft Phase 1/2 wie Phase 4 schon heute: sofort
    speichern, eine 📌-Zeile statt "Notiert: ...", EIN Undo-Knopf statt
    Ja/Nein (``knoepfe.basis._autospeichere``, ``erkenner._sende_meldung``).

    Vorgabe false -- wie ``[laengen] aktiv``: ohne diese Zeile im Profil
    bleibt Phase 1/2 genau das, was sie vorher war. Dortmund setzt die Zeile
    nicht und bleibt unberuehrt."""
    profil = profil or aktiv()
    return bool(profil.wert("speichern.autosave_phase1_2", False))

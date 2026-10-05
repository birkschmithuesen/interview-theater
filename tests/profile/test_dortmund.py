"""Was das Profil ``dortmund-2026`` zusichert -- die Werte, nicht die Form.

**Warum diese Datei getrennt steht** (D.1 und E.1 Frage 6 der Analyse).
Mindestens 15 Testdateien pruefen heute Dortmund-Werte hart: "15 und 18",
die Herkules-Zahlen, "Dialog, Monolog, Chor, Lied, Rap". Wer sie
"profilfaehig" macht, indem er die Literale durch Profil-Lookups ersetzt,
verliert genau die Zusicherung, um derentwillen sie geschrieben wurden --
der Test prueft dann nur noch, dass zwei Stellen dasselbe sagen.

Richtig ist zweistufig:

* **generisch** -- ``tests/test_rahmen.py``, ``tests/test_formen_katalog.py``,
  ``tests/test_phasen_profil.py``, ``tests/test_orte_beispiele.py``: der
  Rahmen ist da und nicht leer, die Formenliste ist ueberall dieselbe, die
  Phasennummern sind lueckenlos. Diese Tests gelten fuer **jedes** Profil.
* **profil-spezifisch** -- diese Datei: die Werte, die fuer Dortmund gelten,
  als Literale ausgeschrieben. Sie laeuft ausdruecklich mit
  ``IT_WORKSHOP=dortmund-2026``; damit ist zugleich geprueft, dass der
  Profil-Weg dieselben Texte liefert wie der eingebaute Vorgabewert.

Ein Profil, das es noch nicht gibt (``padua-2026`` ist ein Geruest), hat
hier keine Datei und darf deshalb an keiner Zusicherung scheitern
(E.1 Frage 8).
"""

import re

import pytest

from interview_theater import anweisungen, phasen, phasentexte, szene, szenenfolge, workshop

NAME = "dortmund-2026"


@pytest.fixture(autouse=True)
def dortmund(monkeypatch):
    """Alles in dieser Datei laeuft mit eingehaengtem Profil."""
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, NAME)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


# --- Zielgruppe und Rahmen (Kopie aus tests/test_anweisungen.py) ---------

@pytest.mark.parametrize("name", ["system", "szene", "phasen/4", "phasen/5"])
def test_rahmen_des_stuecks_steht_in_den_prompts(name):
    """Die Gruppe sind junge Frauen zwischen 15 und 18 -- Orte,
    Auffuehrungsort und Format stehen fest und gehen jedem Modellvorschlag
    vor."""
    text = anweisungen.hole(name)
    assert "Rahmen des Stuecks" in text
    for stichwort in ("15 und 18", "keine Beispielorte", "Halle", "Buehnenbild"):
        assert stichwort in text, (name, stichwort)


def test_der_traeger_steht_im_langen_rahmenblock():
    text = anweisungen.hole("system")
    assert "junge Frauen zwischen 15 und 18 Jahren" in text
    assert "(Migrantinnenverein Dortmund)" in text


def test_die_werte_im_profil():
    profil = workshop.aktiv()
    assert profil.wert("zielgruppe.beschreibung") == "junge Frauen zwischen 15 und 18 Jahren"
    assert profil.wert("zielgruppe.traeger") == "Migrantinnenverein Dortmund"
    assert profil.wert("sprache.code") == "de"
    assert profil.wert("sprache.anrede") == "ihr"
    assert profil.wert("orte.auffuehrung") == (
        "auf einem oeffentlichen Platz oder in einer grossen Halle")
    assert tuple(profil.wert("orte.ausgeschlossen")) == (
        "Club", "Disko", "Alkohol", "Nachtleben", "Drogen")
    assert tuple(profil.wert("orte.beispiele")) == (
        "Bushaltestelle", "Schulhof", "Kiosk", "Bahnhof")


def test_die_zielgruppe_steht_in_jeder_rahmenfassung():
    """Der kurze und der knappe Block tragen den Wortlaut ausgeschrieben --
    dort faellt der Zeilenumbruch mitten in den Satz, und ein eingesetzter
    Wert wird nicht neu umbrochen. Damit sie nicht von profil.toml
    abweichen, stehen sie hier."""
    for name in ("rahmen-kurz", "rahmen-knapp"):
        text = anweisungen.hole(name)
        assert "junge" in text and "Frauen zwischen 15 und 18 Jahren" in text


def test_das_projekt_ist_die_dortmunder_nordstadt():
    text = anweisungen.hole("phasen/2")
    assert "Dortmunder Nordstadt" in text
    assert "Theater im Depot" in text


# --- Formen (Kopie aus tests/test_anweisungen.py) ------------------------

def test_es_gibt_genau_fuenf_formen():
    assert szene.FORMEN == ("dialog", "monolog", "chor", "lied", "rap")
    assert szenenfolge.FORM_VORGABE == "dialog"
    assert workshop.platzhalter()["formen_anzahl"] == "fuenf"
    for form in szene.FORMEN:
        assert anweisungen.hole(f"formen/{form}").strip()
    for weg in ("formen/stumm", "formen/tanztheater", "formen/text"):
        assert anweisungen.hole_optional(weg) is None, weg


def test_die_formenliste_steht_in_den_prompts():
    for name in ("system", "phasen/4", "phasen/6"):
        text = anweisungen.hole(name)
        for form in ("Dialog", "Monolog", "Chor", "Lied", "Rap"):
            assert form in text, (name, form)
    folge = szenenfolge.systemanweisung(5)
    assert "genau fuenf: Dialog, Monolog, Chor, Lied, Rap" in folge


# --- Herkules-Mass (Kopie aus tests/test_anweisungen.py) -----------------

def test_der_formblock_ist_ein_sprechtheater_textbuch():
    text = anweisungen.hole("formen/dialog")
    assert "Sprechszene" in text
    assert "Sprechtheater-Textbuch" in text
    assert "Ausgangsmaterial" in text
    assert "Choreografin" in text, "der Hintergrund-Absatz gehoert dazu"


def test_der_formblock_gibt_die_gemessenen_zielwerte_als_zahlen():
    text = anweisungen.hole("formen/dialog")
    for zahl in ("700 bis 1500 Woerter", "acht Woerter"):
        assert zahl in text, zahl
    assert "%" in text
    assert "Regieanweisung" in text


def test_der_formblock_nimmt_der_choreografin_nichts_vorweg():
    text = anweisungen.hole("formen/dialog")
    negativ = text.split("## Was du nicht schreibst", 1)
    assert len(negativ) == 2, "die Negativliste fehlt"
    for begriff in ("Choreografie", "Counts", "[BEWEGUNG]", "Krump", "Cypher",
                    "Buehnenbild", "Musik-, Licht- und Videoanweisungen"):
        assert begriff in negativ[1], begriff


# --- Phasen (die sieben Stationen vom 06.09.2026) ------------------------

def test_die_sieben_phasen_heissen_so():
    assert phasen.PHASEN == (
        (1, "Begriffe",
         "Die im Plenum gesammelte Begriffsliste aufnehmen und ordnen."),
        (2, "Fragen", "Aus den Begriffen Interviewfragen entwickeln."),
        (3, "Interviews", "Interviews fuehren, das Material verdichten."),
        (4, "Setting, Figuren & Geschichte",
         "Frei erfinden: worin es spielt, wer vorkommt, was passiert."),
        (5, "Schaerfung",
         "Die erfundene Geschichte am Interviewmaterial schaerfen."),
        (6, "Szenen als Geschichte",
         "Jede Szene als Prosa erzaehlen -- was passiert, noch ohne Form."),
        (7, "Feinschliff",
         "Je Szene die Form waehlen, die Geschichte uebersetzen, das Stueck "
         "pruefen."),
    )
    assert phasen.LETZTE == 7
    assert phasen.ERSTE == 1
    assert phasen.MEHRDEUTIG == {5: 7}
    assert phasen.MELDUNG == "Wir sind jetzt bei {bezeichnung}. Falls nicht, sagt es mir."


def test_die_stichwoerter_der_phasen():
    stichwoerter = phasen.STICHWOERTER
    assert stichwoerter[1] == ("begriffe", "begriff", "begriffsliste")
    assert "interviewfragen" not in stichwoerter[2], (
        "der Vergleich laeuft in beide Richtungen -- 'interview' waere darin "
        "enthalten und die Gruppe landete beim Formulieren statt beim Aufnehmen")
    assert "kernthema" in stichwoerter[4], "Altlast, bleibt bewusst stehen"
    assert stichwoerter[7] == ("durchlauf", "feinschliff", "stueckpruefung",
                               "pruefrunde")


# --- Phasentexte, Zeichen fuer Zeichen ----------------------------------
#
# Birk hat den Wortlaut am 06.09.2026 ausdruecklich bestaetigt. Er ist beim
# Umbau in phasentexte.toml gewandert und hat sich dabei um kein Zeichen
# geaendert -- das steht hier als Literal, damit ein Diff es zeigt und nicht
# nur eine Pruefsumme.

EINLEITUNGEN = {
    1: (
        "Hier kommt eure Begriffsliste aus dem Plenum zu mir. Ihr schickt "
        "sie getippt oder als Sprachnachricht, so wie sie bei euch an der "
        "Wand steht. Ich halte sie fest, ordne sie und frage nach, wo ein "
        "Begriff noch zu gross ist. Am Ende stehen die Kernbegriffe, mit "
        "denen ihr weiterarbeitet."
    ),
    2: (
        "Aus euren Begriffen werden jetzt die Interviewfragen. Ich schlage "
        "euch zehn vor, ihr sagt mir die Nummern von genau drei. Danach "
        "schauen wir, welche Frage heikel ist und wie ihr sie so stellt, "
        "dass sie leicht zu beantworten ist, und womit ihr ein Gespraech "
        "anfangt und aufhoert. Am Ende habt ihr einen Leitfaden zum "
        "Mitnehmen."
    ),
    3: (
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
    4: (
        "Ab hier wird erfunden - ganz frei, ohne Material. Ihr denkt euch aus, "
        "wo euer Stueck spielt (Ort, Zeit, Anlass), wer darin vorkommt, und "
        "was passiert: die Geschichte im Groben, wie sie ausgeht, und die "
        "Szenenfolge mit Titel, einem Satz, den Figuren und einem Vorschlag "
        "fuer die Form. Ich helfe mit Vorschlaegen, wenn ihr wollt. Direkt "
        "danach kommen die Interviews ins Spiel und schaerfen, was ihr gebaut "
        "habt."
    ),
    5: (
        "Jetzt kommen die Interviews zurueck. Ich lege neben jede Szene und "
        "jede Figur die Stellen aus euren Aufnahmen, die dazu passen, mit "
        "dem woertlichen Zitat. Eure Geschichte aendert sich dadurch nicht, "
        "sie wird genauer. Ihr entscheidet Vorschlag fuer Vorschlag und "
        "koennt noch eine Runde drehen."
    ),
    6: (
        "Jetzt schreibe ich eure Geschichte am Stueck - eine Kurzgeschichte, "
        "wie in einem Buch: was passiert, wer da ist, was gesagt und "
        "gefuehlt wird, in Prosa. Wie viele Abschnitte es werden, entscheidet "
        "die Geschichte. Aus jedem Abschnitt wird danach eine Szene. Kein "
        "Theatertext, keine Form; das kommt im Feinschliff. Ihr lest sie und "
        "sagt mir, was anders werden soll."
    ),
    7: (
        "Alle Szenen stehen als Geschichte. Jetzt der Feinschliff: Szene fuer "
        "Szene entscheidet ihr die Form - Dialog, Monolog, Chor, Lied oder "
        "Rap -, und ich uebersetze die Geschichte in genau diese Form. "
        "Danach lese ich euer Stueck einmal als Ganzes, wie ein Zuschauer, "
        "und sage euch zu jeder Frage, wo es traegt und wo nicht: "
        "Spannungsbogen, Figuren, Spannung, Nachvollziehbarkeit, Anfang und "
        "Ende, Sprechbarkeit. Zu jedem Punkt ein Vorschlag, den ihr in die "
        "Szene geben koennt. Ihr koennt das Textbuch jederzeit als Datei "
        "holen."
    ),
}

EINLEITUNG_LETZTE_OFFEN = (
    "Hier seht ihr euer Textbuch am Stueck. Ein Teil der Szenen ist noch "
    "ungeschrieben - tippt eine davon an, dann hole ich das nach. Bei den "
    "fertigen achten wir auf die Uebergaenge und darauf, was sich beim "
    "Sprechen sperrig anfuehlt."
)


@pytest.mark.parametrize("nummer", sorted(EINLEITUNGEN))
def test_die_einleitung_ist_zeichengleich_mit_dem_bestaetigten_wortlaut(nummer):
    assert phasentexte.EINLEITUNGEN[nummer] == EINLEITUNGEN[nummer]


def test_die_ersatzfassung_der_letzten_phase_ist_zeichengleich():
    assert phasentexte.EINLEITUNG_LETZTE_OFFEN == EINLEITUNG_LETZTE_OFFEN


def test_keine_einleitung_bewirbt_einen_slash_befehl():
    """docs/agents/entscheidungen.md: Slash-Befehle werden nirgends beworben, beworben wird der
    Knopf."""
    for nummer, text in phasentexte.EINLEITUNGEN.items():
        assert "/" not in text, nummer


def test_keine_einleitung_nennt_einen_eigennamen_oder_siezt():
    """Anti-Nachplapper wie bei den Prompts, dazu die Anrede: die Gruppe
    sind junge Frauen zwischen 15 und 18, angesprochen mit "ihr"."""
    verboten = re.compile(r"\b(Kessel|Mira|Pola|Pal|Demo|Birk|Hawaii)\b", re.I)
    for nummer, text in phasentexte.EINLEITUNGEN.items():
        assert verboten.findall(text) == [], nummer
        assert " Sie " not in text, nummer


# --- Der Profil-Weg liefert dasselbe wie die eingebaute Vorgabe ---------

def test_das_profil_liefert_dasselbe_wie_ohne_variable(monkeypatch):
    """Die Zusage in einem Satz. Alles oben laeuft mit
    ``IT_WORKSHOP=dortmund-2026``; hier steht daneben, dass ohne die
    Variable dieselben Texte entstehen."""
    mit = {name: anweisungen.hole(name) for name in
           ("system", "szene", "rahmen", "phasen/2", "phasen/4", "formen/dialog")}
    monkeypatch.delenv(workshop.VARIABLE)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    ohne = {name: anweisungen.hole(name) for name in mit}
    assert mit == ohne

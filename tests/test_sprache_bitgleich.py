"""Dortmund bleibt bitgleich -- auch durch die Sprachumstellung (Karte A1).

Zwei Massstaebe, beide VOR dem ersten Umbauschritt abgelegt (30.09.2026):

* ``docs/prompt-audit/schnappschuss-vor-sprache-a1.txt`` -- jede Prompt-Datei
  und jede zusammengesetzte Systemanweisung (``scripts/prompt_schnappschuss``),
* ``docs/prompt-audit/texte-vor-sprache-a1.txt`` -- jede Modul-Konstante,
  aus der ein Nutzer- oder Modelltext entstehen kann
  (``scripts/text_schnappschuss``, eine Obermenge der spaeteren Texttabelle).

Geprueft wird ohne ``IT_WORKSHOP`` und mit ``dortmund-2026``. Neue Abschnitte
sind erlaubt (eine neue Konstante ist keine Undichtigkeit), ein
verschwundener oder veraenderter ist ein Befund -- ausser er steht in
``VERSCHOBEN`` oder ``GEAENDERT``, mit Grund.
"""

import re
from pathlib import Path

import pytest

from interview_theater import anweisungen, workshop
from scripts import prompt_schnappschuss, text_schnappschuss

WURZEL = Path(__file__).resolve().parent.parent
PROMPTS = WURZEL / "docs" / "prompt-audit" / "schnappschuss-vor-sprache-a1.txt"
TEXTE = WURZEL / "docs" / "prompt-audit" / "texte-vor-sprache-a1.txt"
DORTMUND = "dortmund-2026"

#: Abschnitte, die A1 absichtlich an einen anderen Ort legt: alt -> neu.
#: Der Wert muss am neuen Ort zeichengleich sein.
VERSCHOBEN: dict[str, str] = {
    # Aufgabe 10 (K1): alle Texte des Knopf-Pakets stehen in knoepfe/texte.py.
    "knoepfe.stationen._ERLEDIGT_FUER": "knoepfe.texte._ERLEDIGT_FUER",
}

#: Karte P2-Fix (02.10.2026, Restspannung 4): prompts/system.md nennt den
#: Hauptkonflikt jetzt als Rahmen-Entscheidung von Station **4** statt 5.
#: Seit dem Zusammenlegen von 4 und 5 am 06.09.2026 heisst Station 4
#: "Setting, Figuren & Geschichte" und traegt die Stichwoerter
#: konflikt/hauptkonflikt (workshop.py:331-342); Station 5 ist die
#: Schaerfung. Englisch steht die 4 seit c8 (en/prompts/system.md:45), und
#: dieselbe deutsche Datei nennt sie an drei anderen Stellen schon richtig
#: (:30, :32, :224). Gewollte Verhaltensaenderung fuer Dortmund: eine Zahl
#: in einem Satz (tests/test_anweisungen.py). Die Systemanweisung geht in
#: jede Phase ein, deshalb neun Abschnitte und nicht einer.
_GRUND_STATION_4 = (
    "Karte P2-Fix (02.10.2026, Restspannung 4): Hauptkonflikt = "
    "Rahmen-Entscheidung von Station 4 statt 5, wie englisch seit c8 und wie "
    "workshop.VORGABE_PHASEN. Die Systemanweisung steckt in jeder Phase, "
    "daher derselbe Grund fuer alle neun Abschnitte "
    "(tests/test_anweisungen.py::test_der_hauptkonflikt_gehoert_zu_station_vier)."
)

#: Abschnitte, deren Wert A1 absichtlich aendert -- mit Grund. Jede Zeile
#: hier ist eine Verhaltensaenderung fuer Dortmund.
GEAENDERT: dict[str, str] = {
    "befehle._BEKANNTE_BEFEHLE": (
        "Aufgabe 8: der versteckte Befehl /sprache kommt dazu (Whisper-"
        "Sprache je Gruppe). Kein bestehender Befehl aendert sich, und er "
        "steht nicht in BEFEHLE_LISTE. Gewollte Verhaltensaenderung fuer "
        "Dortmund: /sprache antwortet jetzt statt mit "
        "\"Diesen Befehl kenne ich nicht.\"."
    ),
    "web._BEARBEITEN_JS": (
        "Aufgabe 17: das Skript der Gruppenseite traegt keine Meldungen mehr "
        "(\"Wirklich entfernen?\", \"speichert …\", \"gespeichert\", \"ging "
        "nicht\"), es liest sie aus data-Attributen von #meldungen, die "
        "web._bearbeiten_html aus web._JS_* (ueber T) setzt. Fuer Dortmund "
        "stehen dieselben vier Woerter wie vorher neben dem Feld -- geaendert "
        "hat sich nur der Weg, nicht der Text (tests/test_web_sprache.py)."
    ),
    "dramaturgie.fanout.TEXT_SZENENAUFTRAG": (
        "Nachbesserung Aufgabe 23 (Review-Befund 3): die Konstante ist ganz "
        "weg, wortgleich mit szene.TEXT_AUFTRAG_NEU war sie eine zweite "
        "Stelle fuer denselben Wortlaut. dramaturgie.fanout.szenenauftrag "
        "delegiert seitdem an szene.T.TEXT_AUFTRAG_NEU -- fuer Dortmund "
        "aendert sich am ausgehenden Text nichts, nur die Quelle ist jetzt "
        "eine statt zwei (tests/test_sprache_parser.py)."
    ),
    "szene._REIHENFOLGE": (
        "Karte R, Aufgabe 8 (30.09.2026): der Blockname \"laenge\" steht "
        "direkt hinter \"aufgabe\". Kein Nutzertext, sondern die Reihenfolge "
        "der Bloecke. Fuer Dortmund bleibt der Block leer (laengen.aktiv = "
        "false) und faellt in _zusammen ersatzlos weg -- der Nutzertext ist "
        "zeichengleich (tests/test_laengen_szene.py, "
        "tests/test_profil_bitgleich.py)."
    ),
    "szene.KERNPAKET_KOPF": (
        "Karte P2-Fix (02.10.2026, Restspannung 2): der Kopf nennt das "
        "Kernthema nicht mehr. EIN Kopf traegt beide Zweige von "
        "szene._kernpaket_text (Schaerfungen je Szene; ersatzweise die "
        "globale Kernzitat-Auswahl), und \"am Kernthema gefiltert\" war fuer "
        "keinen wahr. Gewollte Verhaltensaenderung fuer Dortmund: eine "
        "Ueberschrift im Szenen-Nutzertext, derselbe Block darunter "
        "(tests/test_szene_sprache.py)."
    ),
    "kontext.KERNPAKET_KOPF": (
        "Karte P2-Fix (02.10.2026, Restspannung 4): \"kommen aus dem "
        "Kernthema\" -> \"aus der Geschichte\". _baue_kernpaket setzt "
        "arbeitsstand.geschichte an den Anfang (kontext.py:472-473), das "
        "Kernthema nur darunter und nur wenn gesetzt; englisch sagt es seit "
        "c8 (en/texte.toml:848). Gewollte Verhaltensaenderung fuer Dortmund: "
        "ein Wort in der Ueberschrift des Blocks (tests/test_kontext.py)."
    ),
    "kurzgeschichte.ANWEISUNG": (
        "Karte P2-Fix (02.10.2026, c5, Birks Entscheidung): die "
        "Abschnittszahl ist fest, sobald eine Szenenfolge steht -- die "
        "Anweisung sagt, dass der Auftrag sie dann nennt, und die freie Wahl "
        "ist der zweite Fall. Gewollte Verhaltensaenderung fuer Dortmund: "
        "sie macht prompts/formen/prosa.md:29-34 (\"Steht schon eine "
        "Szenenfolge, ist sie verbindlich\") zum ersten Mal "
        "widerspruchsfrei. Die ersetzbare Laengenzeile ist unberuehrt "
        "(tests/test_laengen_prosa.py)."
    ),
    "kuerzung.TEXT_NOTIZ_PROSA": (
        "Karte P2-Fix, Abschlussreview (02.10.2026): die Kuerzungsnotiz nennt "
        "keine Abschnittszahl mehr (\"Behalte genau {anzahl} Abschnitte\" -> "
        "\"Behalte die Abschnitte\"). Sie zaehlte die Szenen MIT Prosa, der "
        "Auftrag (kurzgeschichte._ZEILE_ABSCHNITTE) die GEPLANTEN -- bei "
        "sechs geplanten und vier geschriebenen standen zwei Zahlen in einem "
        "Prompt. Gewollte Verhaltensaenderung fuer Dortmund: die Zahl steht "
        "genau einmal im Nutzertext, im Auftrag "
        "(tests/test_kuerzung.py::test_kuerzen_bindet_die_abschnittszahl_genau_einmal)."
    ),
    # Padua Hotfix Befund 2 (02.10.2026): das Gespraechsmodell (reiner Text)
    # sieht keine Bilder und soll ein Foto deshalb nicht mehr anbieten --
    # zusaetzlich zur Station-4-Umbenennung aus Karte P2-Fix, die denselben
    # Abschnitt beruehrt.
    "prompt system": (
        _GRUND_STATION_4 + " Dazu (Padua Hotfix Befund 2): system.md bietet "
        "nicht mehr an, die Begriffsliste \"von einem Foto abgetippt\" zu "
        "schicken, und bekommt stattdessen den Satz \"Du kannst keine "
        "Bilder oder Dateien sehen ...\". Gewollte Verhaltensaenderung fuer "
        "Dortmund: dieselbe Korrektur wie fuer Padua, das Modell sieht dort "
        "ebenfalls keine Bilder. Dazu Padua Hotfix B1 (Befund 1, "
        "02.10.2026): unter /aufnahme steht, dass eine Sprachnachricht ohne "
        "laufende Aufnahme abgetippt ankommt (im Verlauf mit "
        "\"(Sprachnachricht)\" markiert) und wie jeder Beitrag beantwortet "
        "wird -- nie behaupten, Sprachnachrichten nicht hoeren/abtippen zu "
        "koennen (Live-Fall: genau das sagte der Bot, obwohl Whisper laengst "
        "transkribiert hatte). Gilt fuer Dortmund ebenso."
    ),
    "prompt phasen/1": (
        "phasen/1.md: \"getippt, von einem Foto abgetippt oder als "
        "Sprachnachricht\" wird zu \"getippt oder als Sprachnachricht\" -- "
        "derselbe Grund wie bei \"prompt system\" (Padua Hotfix B2). Dazu "
        "Padua Hotfix B4 (Befund 4, 02.10.2026): die Zeile \"Ordne, was "
        "zusammengehoert, und sag der Gruppe, was du siehst\" ist gestrichen "
        "(Live-Fall: der Bot kommentierte und assoziierte ungefragt, dann "
        "haengte er eine Frage an, die die direkt folgende Speicherleiste "
        "nie beantwortete). Neu: die Liste wird nur wiedergegeben und "
        "bestaetigt, keine Frage am Ende -- die Speicherknoepfe sind die "
        "einzige Frage. Die Rueckfrage zur Praezisierung eines einzelnen "
        "unklaren Begriffs bleibt erlaubt, ersetzt dann aber den "
        "Vorschlagsblock in derselben Nachricht, statt daneben zu stehen."
    ),
    "anweisungen.system(phase=None)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=1)": "siehe \"prompt system\"/\"prompt phasen/1\" oben.",
    "anweisungen.system(phase=2)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=3)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=4)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=5)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=6)": "siehe \"prompt system\" oben.",
    "anweisungen.system(phase=7)": "siehe \"prompt system\" oben.",
    "kontext.ERSTKONTAKT": (
        "Padua Hotfix Befund 2: die Begruessung bittet nicht mehr um die "
        "Begriffsliste \"als Foto abgetippt\" -- das Gespraechsmodell sieht "
        "ohnehin keine Bilder. Gewollte Verhaltensaenderung fuer Dortmund."
    ),
    "knoepfe.texte._TEXT_PHASE_ANGEBOT": (
        "Padua Hotfix Befund 5b (Birk 02.10.2026): die Rueckfrage nennt die "
        "Phase mit Nummer und Titel (\"Weiter zu Phase 2 · Fragen?\"). "
        "Gewollt auch fuer Dortmund/Vorgabeprofil."
    ),
    "knoepfe.texte._TEXT_PHASE_WEITER": (
        "Padua Hotfix Befund 5b (Birk 02.10.2026): \"Weiter zu Phase "
        "{phase}?\", {phase} = phasen.bezeichnung (Nummer + Titel)."
    ),
    "knoepfe.texte._TEXT_WEITER_ZU_KNOPF": (
        "Padua Hotfix Befund 5b (Birk 02.10.2026): der Weiter-Knopf heisst "
        "\"Weiter zu Phase 2 · Fragen\" statt \"Weiter zu Fragen\"."
    ),
}

_ZEILE = re.compile(r"^(\S+)\s+(\d+)\s+(.*)$")


@pytest.fixture(autouse=True)
def frisch(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    anweisungen._CACHE.clear()
    yield
    workshop.vergiss()
    anweisungen._CACHE.clear()


def _lies(text: str) -> dict[str, str]:
    fertig = {}
    for zeile in text.splitlines():
        pruef, laenge, name = _ZEILE.match(zeile).groups()
        fertig[name] = f"{pruef} {laenge}"
    return fertig


def _vergleiche(erwartet: dict[str, str], jetzt: dict[str, str]) -> None:
    fehlend, abweichend = [], []
    for name, wert in erwartet.items():
        if name in GEAENDERT:
            continue
        ziel = VERSCHOBEN.get(name, name)
        if ziel not in jetzt:
            fehlend.append(name)
        elif jetzt[ziel] != wert:
            abweichend.append(
                f"\n  {name}\n    erwartet: {wert}\n    bekommen: {jetzt[ziel]}")
    assert not fehlend, "verschwunden: " + ", ".join(sorted(fehlend))
    assert not abweichend, "".join(abweichend)


def _prompts_jetzt() -> dict[str, str]:
    anweisungen._CACHE.clear()
    return _lies(prompt_schnappschuss.fingerabdruck())


def _texte_jetzt() -> dict[str, str]:
    return _lies(prompt_schnappschuss.fingerabdruck(text_schnappschuss.teile()))


def test_prompts_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_prompts_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(PROMPTS.read_text(encoding="utf-8")), _prompts_jetzt())


def test_texte_ohne_variable_wie_vor_a1():
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_texte_mit_dortmund_wie_vor_a1(monkeypatch):
    monkeypatch.setenv(workshop.VARIABLE, DORTMUND)
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


def test_massstaebe_sind_nicht_leer():
    assert len(_lies(PROMPTS.read_text(encoding="utf-8"))) >= 121
    assert len(_lies(TEXTE.read_text(encoding="utf-8"))) >= 600


def test_muster_aus_einer_menge_haengt_nicht_am_hashseed():
    """``befehle._SZENE_ENTFERNEN`` entsteht aus ``"|".join(<Menge>)`` --
    ohne Normalisierung wechselte sein Abschnitt mit ``PYTHONHASHSEED``
    (gemessen beim Ablegen des Massstabs). Der Schnappschuss sortiert die
    Alternativen; derselbe Ausdruck mit sortierter Menge ergibt dieselbe Form."""
    from interview_theater import befehle

    sortiert = re.compile(
        r"^(?:szene\s*)?(\d{1,3})\s+(?:"
        + "|".join(sorted(befehle._ENTFERNEN_WOERTER)) + r")\.?$",
        re.IGNORECASE,
    )
    normal = text_schnappschuss._ohne_mengenreihenfolge(
        befehle, befehle._SZENE_ENTFERNEN)
    assert text_schnappschuss.form(normal) == text_schnappschuss.form(sortiert)


def test_jede_ausnahme_hat_einen_grund():
    for name, grund in GEAENDERT.items():
        assert grund.strip(), name
    for alt, neu in VERSCHOBEN.items():
        assert alt != neu, alt

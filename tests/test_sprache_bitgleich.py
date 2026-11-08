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
    "prompt schaerfung": (
        "Zuordnung-Umbau (Birk/Robo 07.10.2026, zuordnung-pruefung.md): der "
        "Pauschal-Lauf ueber alle Szenen/Figuren wird durch Je-Ziel-Aufrufe "
        "ersetzt (drei statt vier Ausgabelisten: eintrag_nummern/staerke/"
        "begruendungen statt eintrag_nummern/szenen_nummern/figuren_namen/"
        "begruendungen), der Prompt beschreibt das neue Ein-Ziel-Verfahren "
        "und die Staerke-Skala statt \"was nicht passt, bleibt weg\". Nicht "
        "profilabhaengig -- aendert sich fuer Padua und Dortmund gleich."
    ),
    "befehle._BEKANNTE_BEFEHLE": (
        "Aufgabe 8: der versteckte Befehl /sprache kommt dazu (Whisper-"
        "Sprache je Gruppe). Kein bestehender Befehl aendert sich, und er "
        "steht nicht in BEFEHLE_LISTE. Gewollte Verhaltensaenderung fuer "
        "Dortmund: /sprache antwortet jetzt statt mit "
        "\"Diesen Befehl kenne ich nicht.\". "
        "Padua-Hilfe Task 1 (03.10.2026): die Konstante ist seitdem eine "
        "ueber __getattr__ (PEP 562) sprachabhaengig gebaute Menge "
        "(_bekannte_befehle(), Alias-Tabelle _BEFEHL_EN), nicht mehr ein "
        "Literal -- fuer Dortmund (de) liefert sie weiterhin genau dieselben "
        "16 Werte wie vorher, nur das en-Profil (Padua) bekommt zusaetzliche "
        "englische Befehlsnamen (tests/test_befehle.py)."
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
    "knoepfe.ANWEISUNG_EINLEITUNGEN": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026, Padua): die "
        "Sensibilitaetspruefung laeuft seit diesem Umbau IM selben "
        "Modellzug wie der Fragenvorschlag selbst, nicht mehr als eigener "
        "Schritt danach -- die Konstante ist ganz weg "
        "(tests/test_phase2_einzeln.py)."
    ),
    "knoepfe.texte.ANWEISUNG_EINLEITUNGEN": (
        "Siehe knoepfe.ANWEISUNG_EINLEITUNGEN oben -- dieselbe Entfernung, "
        "andere Schnappschuss-Ebene."
    ),
    "knoepfe.texte.TEXT_ARBEIT_SENSIBILITAET": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): keine eigene "
        "Arbeitszeile mehr, weil die Sensibilitaetspruefung keinen eigenen "
        "Modellzug mehr hat (siehe knoepfe.ANWEISUNG_EINLEITUNGEN)."
    ),
    "knoepfe.texte.TEXT_PRUEFUNG_LAEUFT": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): dieselbe Entfernung, "
        "die Zeile gehoerte zum gestrichenen Sensibilitaetspruefungs-Schritt."
    ),
    "knoepfe.texte._HAKEN": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): letzter Rest der "
        "stillgelegten Toggle-Knopf-Auswahl (06.09.2026), jetzt restlos "
        "entfernt -- kein Aufrufer mehr."
    ),
    "knoepfe.texte._TEXT_FRAGEN_NICHT_DREI": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): keine feste Zahl "
        "mehr (\"No hard count anywhere\") -- die Gruppe entscheidet Frage "
        "fuer Frage, nicht per Dreierauswahl."
    ),
    "knoepfe.texte._TEXT_FRAGEN_NOTIERT": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): die Nummernwahl "
        "entfaellt, die Notiert-Zeile heisst jetzt "
        "``_TEXT_FRAGEN_ABGESCHLOSSEN``."
    ),
    "knoepfe.texte._TEXT_FRAGEN_NUMMERN_FALSCH": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): dieselbe Entfernung "
        "wie ``_TEXT_FRAGEN_NICHT_DREI`` -- keine Nummernwahl mehr."
    ),
    "knoepfe.texte._TEXT_FRAGEN_UEBERNEHMEN_KNOPF": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): der Knopf \"Diese 3 "
        "nehmen\" ist Geschichte (``ART_FRAGEN_UEBERNEHMEN`` bleibt als "
        "stillgelegte Art stehen, nur die Beschriftung ist weg)."
    ),
    "knoepfe.texte._TEXT_FRAGEN_UEBERNOMMEN": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): dieselbe Entfernung "
        "wie ``_TEXT_FRAGEN_NOTIERT`` -- die Quittung heisst jetzt "
        "``_TEXT_FRAGEN_ABGESCHLOSSEN``."
    ),
    "prompt phasen/2": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026, Padua): der Vorschlag "
        "traegt die Sensibilitaetspruefung im selben Modellzug, danach ein "
        "Ueberblick mit Richtungsfrage statt Nummernwahl, danach Frage fuer "
        "Frage (tests/test_phase2_einzeln.py)."
    ),
    "anweisungen.system(phase=2)": (
        "Folge aus 'prompt phasen/2' oben -- dieselbe Aenderung in der "
        "zusammengesetzten Systemanweisung."
    ),
    "knoepfe.ANWEISUNG_FRAGEN_ANDERE": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): kein fester Zehner "
        "mehr (\"No hard count anywhere\"), traegt jetzt die "
        "Sensibilitaetspruefung mit und nimmt eine optionale Richtung "
        "entgegen (tests/test_phase2_einzeln.py)."
    ),
    "knoepfe.texte.ANWEISUNG_FRAGEN_ANDERE": (
        "Siehe knoepfe.ANWEISUNG_FRAGEN_ANDERE oben -- dieselbe Aenderung, "
        "andere Schnappschuss-Ebene."
    ),
    "knoepfe.texte._TEXT_FRAGEN_ANDERE_KNOPF": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): der Knopf heisst "
        "jetzt \"Andere Richtung\" statt \"Andere Fragen\" -- er fragt "
        "seitdem zuerst nach der Richtung, statt sofort neu vorzuschlagen."
    ),
    "knoepfe.texte._TEXT_FRAGEN_WAHL": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): die Nummernwahl ist "
        "weg, der Text dient nur noch als Antwort auf einen Druck aus "
        "einer alten, schon verschickten Nachricht."
    ),
    "vorschlag.ARTEN": (
        "Phase-2-Umbau 'Fragen einzeln' (02.10.2026): neuer Marker "
        "'frage' fuer die eine gerade geschaerfte Frage, neben der "
        "bestehenden Fragenliste 'fragen' (tests/test_phase2_einzeln.py)."
    ),
    "vorschlag._ZEILE": (
        "Siehe vorschlag.ARTEN oben -- derselbe neue Marker in der "
        "Erkennungs-Regex."
    ),
    "szene._REIHENFOLGE": (
        "Karte R, Aufgabe 8 (30.09.2026): der Blockname \"laenge\" steht "
        "direkt hinter \"aufgabe\". Kein Nutzertext, sondern die Reihenfolge "
        "der Bloecke. Fuer Dortmund bleibt der Block leer (laengen.aktiv = "
        "false) und faellt in _zusammen ersatzlos weg -- der Nutzertext ist "
        "zeichengleich (tests/test_laengen_szene.py, "
        "tests/test_profil_bitgleich.py)."
    ),
    "kontext._REIHENFOLGE": (
        "Padua Phase 1+2 Umbau, Aufgabe 8 (03.10.2026): der Blockname "
        "\"diskussion\" steht direkt hinter \"festlegungen\". Kein "
        "Nutzertext, sondern die Reihenfolge der Bloecke. Fuer Dortmund "
        "bleibt der Block leer (keine Zeile in diskussion_verdichtung ohne "
        "das Profil ``diskussion.aktiv``) und faellt in _zusammen ersatzlos "
        "weg -- der Nutzertext ist zeichengleich (tests/test_kontext.py, "
        "tests/test_profil_bitgleich.py)."
        " Karte t_4517d4ad (04.10.2026): \"begriffe_detail\" steht direkt "
        "hinter \"diskussion\" -- fuer Dortmund ebenfalls leer (keine Spalte "
        "begriffe_detail ohne Begriffsboard) und ersatzlos weg."
        " Birk 08.10.2026 ~09:35 (Nachtrag, \"No, change\"-Dialog): "
        "\"karte_dialog\" steht direkt hinter \"szene\" -- fuer Dortmund "
        "leer (kein ``[karten] aktiv``, ``szenenkarte.dialog_kontextblock`` "
        "liefert ohne den Schalter nichts) und ersatzlos weg."
    ),
    # Padua-Brainstorming-Umbau, Phase 4 (02.10.2026, .phase4-brainstorm-brief.md):
    # die neue Erkenner-Art ``szenenanzahl_setzen`` (Anzahl Szenen ist ein
    # fixes Feld, das die Gruppe selbst setzt) und die Entfernung der
    # Rahmen->Figurenanzahl-Kette. Sechs Stellen aendern sich zusammen:
    "erkenner.ARTEN": (
        "Neue Art szenenanzahl_setzen (Punkt 24 in erkenner.md) -- die "
        "Anzahl Szenen ist seit dem Phase-4-Umbau ein eigenes "
        "Arbeitsstandfeld, das die Gruppe selbst nennt."
    ),
    "erkenner.SCHEMA": (
        "Folgt aus ARTEN: das JSON-Schema des Erkenneraufrufs listet jede "
        "bekannte Art im Enum, szenenanzahl_setzen kommt dazu."
    ),
    "erkenner._LEISTENARTEN": (
        "rahmen_setzen/geschichte_setzen sind heraus: Phase 4 zeigt unter "
        "jeder automatisch gespeicherten Festlegung nur noch den EINEN "
        "Rueckgaengig-Knopf (📌-Zeile, siehe erkenner._ZEILE_FESTGELEGT), "
        "keine Ping-Pong-Grundleiste mehr."
    ),
    "knoepfe.texte._KETTE": (
        "\"rahmen\" ist kein Kettenglied mehr: die Figurenanzahl-Frage kommt "
        "nach dem Setting nicht mehr automatisch (freies Brainstorming ohne "
        "feste Reihenfolge). kernthema/kernfrage bleiben rueckwaertskompatibel."
    ),
    "szenenfolge.ANWEISUNG_GESCHICHTE_SZENEN": (
        "Keine Form/Begruendung-Spalte mehr in der Szenenfolge, die Phase 4 "
        "vorschlaegt -- die Form einer Szene entscheidet die Gruppe erst im "
        "Feinschliff (Phase 7), nicht beim Erfinden der Geschichte."
    ),
    "prompt erkenner": (
        "Punkt 22 (festlegung_setzen) erlaubt jetzt einen freien, kurzen "
        "Bereichstitel statt alles Unbekannte unter \"sonstiges\" zu "
        "sammeln, und der neue Punkt 24 (szenenanzahl_setzen) kommt dazu; "
        "die Abgrenzungsabsaetze wurden entsprechend angepasst."
    ),
    "szenenfolge.systemanweisung_geschichte_szenen": (
        "Folgt aus ANWEISUNG_GESCHICHTE_SZENEN: keine Form/Begruendung-"
        "Spalte mehr in der phase-4-Szenenfolge."
    ),
    "prompt phasen/4": (
        "Volle Neufassung (Padua-Brainstorming-Umbau, 02.10.2026): freie "
        "Reihenfolge statt fester Kette (Setting -> Figuren -> Geschichte), "
        "Vorschlaege nur auf Anfrage oder im Stillstand statt als feste "
        "Eroeffnungsfrage, keine Form/Begruendung mehr in der Szenenfolge, "
        "die Anzahl Szenen als eigenes Feld, ein Hinweis auf die "
        "automatische Festlegung und den Phasenabschluss-Vorschlag."
    ),
    "anweisungen.system(phase=4)": (
        "Folgt aus der Neufassung von phasen/4.md (siehe oben) -- die "
        "Basisanweisung haengt den Phasentext unveraendert an. Zusaetzlich "
        "Karte P2-Fix (Restspannung 4), siehe _GRUND_STATION_4 unten -- "
        "beide Aenderungen treffen denselben zusammengesetzten Abschnitt."
    ),
    "szenenfolge.systemanweisung_geschichte(3)": (
        "Folgt aus phasen/4.md: die zusammengesetzte Systemanweisung fuer "
        "den Richtungs-Vorschlag haengt den neuen Phasentext an."
    ),
    "szenenfolge.systemanweisung_geschichte(4)": (
        "Folgt aus phasen/4.md, wie systemanweisung_geschichte(3)."
    ),
    "szenenfolge.systemanweisung_geschichte(5)": (
        "Folgt aus phasen/4.md, wie systemanweisung_geschichte(3)."
    ),
    "szenenfolge.systemanweisung_geschichte(6)": (
        "Folgt aus phasen/4.md, wie systemanweisung_geschichte(3)."
    ),
    "prompt phasen/5": (
        "Karte t_6177d71f (07.10.2026): dramaturgische Rolle in Phase 5 -- "
        "ein erkennbarer Widerspruch zwischen Zitat und Figurenhaltung darf "
        "als Beobachtung benannt werden (nie als Abwertung), und das "
        "'Erst fragen, dann vorschlagen'-Boilerplate ist durch eine "
        "phasenspezifische Fassung ersetzt, weil die Zuordnung automatisch "
        "laeuft und es in Phase 5 kaum freie Vorschlaege gibt "
        "(tests/test_phase57_dramaturg_regeln.py)."
    ),
    "prompt phasen/6": (
        "Folgt aus dem Phase-4-Umbau (02.10.2026): Phase 4 entscheidet keine "
        "Form je Szene mehr, also behauptet Phase 6 nicht mehr \"die Form je "
        "Szene steht schon\" -- sie wird erst im Feinschliff entschieden."
    ),
    "prompt phasen/7": (
        "Karte t_6177d71f (07.10.2026): eine Zeile vor den sechs bereits "
        "bewaehrten Feinschliff-Regeln ('Hier arbeitest du wie ein "
        "erfahrener Dramaturg am Text') gibt ihnen eine Identitaet, ohne "
        "ihren Wortlaut zu aendern (tests/test_phase57_dramaturg_regeln.py)."
    ),
    "anweisungen.system(phase=6)": (
        "Folgt aus phasen/6.md (siehe oben). Zusaetzlich Karte P2-Fix "
        "(Restspannung 4), siehe _GRUND_STATION_4 unten -- beide "
        "Aenderungen treffen denselben zusammengesetzten Abschnitt."
    ),
    "szenenfolge.systemanweisung(3)": (
        "Folgt aus phasen/6.md (siehe oben)."
    ),
    "szenenfolge.systemanweisung(4)": (
        "Folgt aus phasen/6.md (siehe oben)."
    ),
    "szenenfolge.systemanweisung(5)": (
        "Folgt aus phasen/6.md (siehe oben)."
    ),
    "szenenfolge.systemanweisung(6)": (
        "Folgt aus phasen/6.md (siehe oben)."
    ),
    "prompt phasen/3": (
        "Karte Phase3-Web: Bedienungsanleitung kanal-neutral umformuliert, "
        "02.10.2026. Die Schritte nennen keinen Telegram-Knopfwortlaut mehr "
        "(\"Interview starten\" / \"Interview geht weiter\" / \"Interview "
        "ist fertig\"), sondern das Verhalten (Aufnahme starten / "
        "aufnehmen / beenden) -- einige dieser Knoepfe werden im Web-Kanal "
        "seit Aufgabe 2 nicht mehr angeboten."
    ),
    "anweisungen.system(phase=3)": (
        "Karte Phase3-Web, 02.10.2026: Folgewirkung derselben Aenderung an "
        "prompt phasen/3 -- die zusammengesetzte Systemanweisung bettet den "
        "Phasentext direkt ein, siehe Begruendung dort. Zusaetzlich Karte "
        "P2-Fix (Restspannung 4), siehe _GRUND_STATION_4 unten -- beide "
        "Aenderungen treffen denselben zusammengesetzten Abschnitt."
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
    # phase=3/4/6 stehen oben, zusammen mit dem jeweils eigenen Grund --
    # beide Karten (P2-Fix und Padua-Brainstorming-Umbau) treffen denselben
    # zusammengesetzten Abschnitt, siehe die kombinierten Begruendungen dort.
    # Padua Hotfix Befund 2 (02.10.2026): das Gespraechsmodell (reiner Text)
    # sieht keine Bilder und soll ein Foto deshalb nicht mehr anbieten --
    # zusaetzlich zur Station-4-Umbenennung aus Karte P2-Fix, die denselben
    # Abschnitt beruehrt. Dazu (Ankuendigung-ohne-Inhalt-Fix, 02.10.2026):
    # ein neuer Absatz "Nie auf einer Ankuendigung enden" -- Ergebnis des
    # Padua-Befunds, dass das Modell einen Vorschlag ankuendigte und seinen
    # Zug dort beendete, ohne ihn zu liefern (siehe ablauf.py:_ohne_ankuendigung).
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
    "web._TEXTBUCH_JS": (
        "Karte W, Aufgabe 11 (30.09.2026): die vereinte Seite haengt den "
        "Zustand der Probenansicht nicht mehr an document.body, sondern an "
        "die Wurzel [data-textbuch] (auf der Einzelseite weiterhin der "
        "<body>) -- sonst faerbte der Rollenfilter auch den Chat. Dazu "
        "schreibt schreib() einen leeren Wert jetzt ohne "
        "Gleichheitszeichen, damit das blosse Tab-Wort im Fragment "
        "(#textbuch) einen Klick auf den Rollenfilter ueberlebt. Kein "
        "Nutzertext aendert sich (tests/test_web_vereint.py, "
        "tests/test_web_textbuch.py)."
    ),
    "web._CSS_GEMEINSAM": (
        "Mobile-App-Shell, Nachbesserung 03.10.2026 (Birk-Befund 09:19, "
        "Handytest): ``html { overflow-x: hidden; }`` dazu, "
        "``overflow-x: hidden;`` an die bestehende ``body``-Regel "
        "angehaengt -- kein horizontales Scrollen mehr auf irgendeiner "
        "Seite dieses Moduls. Reines Layout-CSS, kein Nutzertext "
        "(docs/ux-padua/BERICHT.md, Abschnitt \"Mobile-App-Shell, "
        "Nachbesserung 03.10.\")."
    ),
    "web._CSS_GRUPPE": (
        "Padua UX Kopfzeilen-Karte (03.10.2026, Task 4): Birk, live am "
        "Handy -- 'der Link zur Rehearsal view ist unsinnig, da identisch "
        "mit Script-Tab.' Der redundante Probenansicht-Link aus dem "
        "Arbeitsstand-Panel entfaellt; die dazugehoerigen, jetzt toten "
        "``.probenansicht``/``.probenansicht a``-Regeln sind mit ihm "
        "entfernt (tests/test_web_textbuch.py::"
        "test_die_gruppenseite_verlinkt_die_probenansicht_nicht_mehr). "
        "Reines Layout-CSS, kein Nutzertext -- die Route "
        "/g/<token>/textbuch und der Textbuch-Tab selbst sind unveraendert."
    ),
    "ablauf._DENKSPUR_MARKER": (
        "Abnahme P3-4, Befund A1 (06.10.2026, Commit bbac086): "
        "_DENKSPUR_MARKER um das weiche \"ich sollte \" sowie die drei "
        "eindeutigen Phrasen \"der benutzer fragt\", \"laut den "
        "instruktionen\", \"die instruktionen sagen\" ergaenzt -- der "
        "Denkspur-Filter erkennt jetzt auch ein Selbstgespraech, in dem "
        "das Modell sich als Ausfuehrendes einer Anweisung beschreibt "
        "bzw. die Systemanweisung zitiert (gemessen in sim.db, "
        "nachricht.message_id=17). Kein Nutzertext: die Konstante filtert "
        "Modell-Selbstgespraech aus, bevor eine Antwort die Gruppe "
        "erreicht, sie wird selbst nie verschickt (tests/test_ablauf.py)."
    ),
    "ablauf._DENKSPUR_EINDEUTIG": (
        "Siehe ablauf._DENKSPUR_MARKER oben -- dieselbe Abnahme-Ergaenzung: "
        "die drei neuen eindeutigen Phrasen stehen in beiden Mengen, weil "
        "sie allein schon Beweis fuer eine Denkspur sind. Kein Nutzertext "
        "(tests/test_ablauf.py)."
    ),
    "knoepfe.texte._TEXT_NACH_SPEICHERN_FRAGE": (
        "Karte t_c5d68218 (06.10.2026): statt der Aufforderung, noch etwas "
        "hinzuzufuegen ('Wollt ihr noch etwas hinzufuegen, bevor es "
        "weitergeht?'), steht jetzt eine Bestaetigungsfrage ('Passt das so "
        "fuer euch?'). Gewollte Verhaltensaenderung fuer Dortmund: ein "
        "optionaler, modellgestuetzter Zusatz (Verbesserungsvorschlag oder "
        "kritische Rueckfrage, nie erzwungen) kann danach als eigene "
        "Nachricht folgen (interview_theater/nachspeichern.py), die alte "
        "Konstante selbst bleibt unveraendert in Bedeutung und Aufrufstellen "
        "(tests/test_nachspeichern_wiring.py)."
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


@pytest.mark.dortmund
def test_texte_ohne_variable_wie_vor_a1():
    # Ohne IT_WORKSHOP gilt Dortmund als Vorgabe; der Massstab ist eine
    # Dortmund-Bitgleich-Pruefung (eingefroren seit 04.10.2026, AGENTS.md).
    # Karte t_a0d171ab aendert ``web._CSS_DASHBOARD`` fuer den Padua-Ticker
    # (neue Klassen .ticker-teil/.ticker-warnung) -- das ist eine neue
    # Padua-Funktion, keine Dortmund-Regression.
    _vergleiche(_lies(TEXTE.read_text(encoding="utf-8")), _texte_jetzt())


@pytest.mark.dortmund
def test_texte_mit_dortmund_wie_vor_a1(monkeypatch):
    # Dieselbe Begruendung wie oben, hier fuer das explizite
    # dortmund-2026-Profil.
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

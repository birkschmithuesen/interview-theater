"""Zusammenbau des Gespraechs-Prompts (SPEC-kontext-architektur.md § 6, § 7).

**Datengetrieben statt aufgabengetrieben.** Es gibt keine
Phasen-Zustandsmaschine: jeder Block unten wird schlicht weggelassen, solange
die zugrundeliegenden Daten leer sind. Am Samstagvormittag gibt es Begriffe
und sonst nichts -- also enthaelt der Prompt Begriffe und sonst nichts.
Biegt die Gruppe ab, aendert sich die Materiallage und der Prompt folgt
automatisch; es gibt keinen Zustand, der ihr widersprechen koennte.

**Reihenfolge: stabil nach vorn, fluechtig nach hinten** --
``verdichtungen, transkripte, arbeitsstand, journal, fenster, ausloeser``.
Begruendet einzig mit der Aufmerksamkeitsverteilung des Modells: was am Ende
des Prompts steht, wiegt am schwersten und soll deshalb das Aktuellste sein.
Kein Caching-Argument: in den Messlaeufen gegen Infomaniak steht in jeder
Antwort ``prompt_tokens_details: null`` -- unbelegt und deshalb nirgends als
Begruendung verwendet (§ 6.1).

Szenen sind seit dem 04.09.2026 eingebaut (siehe ``interview_theater/szene.py``,
das sie schreibt): die Szenenliste als Teil des Arbeitsstands (Block 4) und
die zuletzt geaenderte Szene im Volltext als eigener Block 5 -- beide
datengetrieben wie alles andere, also weg, solange es keine Szene gibt.
"""

import logging
import os
import re
from datetime import datetime, timedelta

from interview_theater import phasen, repo, workshop

log = logging.getLogger(__name__)

#: System-Prompt, wortidentisch aus der Datei geladen (siehe
#: interview_theater/prompts/system.md). Wird der Sprachmodell-Anfrage getrennt vom
#: Rueckgabewert von baue() als ``system``-Feld mitgegeben (vgl.
#: interview_theater.llm.LLM.schema/.prosa).
from interview_theater import anweisungen


def system(bot_name: str | None = None, phase: int | None = None) -> str:
    """Systemanweisung, heiss nachgeladen (siehe interview_theater.anweisungen).

    ``phase`` haengt die Anweisung fuer die aktuelle Arbeitsphase an
    (``prompts/phasen/N.md``). Sie steuert den Fokus, nicht den
    Informationszugang: die datengetriebenen Bloecke unten bleiben davon
    unberuehrt."""
    return anweisungen.system(bot_name, phase)

#: Kein Tokenizer -- zwei Tage vor dem Workshop keine Abhaengigkeit, die sich
#: fuer Kimi nicht sauber verifizieren laesst. Zeichen ÷ 3 ueberschaetzt bei
#: deutschen Komposita leicht die Tokenzahl -- die richtige Fehlerrichtung:
#: lieber zu frueh kuerzen als zu spaet (§ 7.1).
_ZEICHEN_JE_TOKEN = 3

#: Budgets in Token je Block (SPEC § 6.2) -- rein dokumentarisch, wie in
#: keinem der Bloecke einzeln durchgesetzt. Die tatsaechliche Begrenzung des
#: Gesamtprompts leistet ausschliesslich die zweistufige Kuerzung (§ 7.2):
#: erst Transkripte raus, dann das Fenster von vorn beschnitten, bis das
#: Ziel erreicht ist oder nichts mehr uebrig ist. Ein Block, der schon beim
#: Bauen auf sein eigenes Budget zusammengestutzt wuerde, wuerde genau die
#: Faelle verstecken, die die Kuerzung eigentlich zeigen soll (ein sehr
#: langer Gespraechsverlauf allein kann das Ziel reissen, auch ganz ohne
#: Transkripte). ``arbeitsstand`` enthaelt laut § 6.2 Block 4 auch die
#: Szenenliste (Titel plus je eine Zeile), ``szene`` ist Block 5: die eine
#: zuletzt geaenderte Szene im Volltext.
#:
#: ``fenster`` ist seit dem 06.09.2026 (Auftrag 2) **historisch**: das reale
#: Fensterbudget steht in ``FENSTER_ZEICHEN`` und wird ueber
#: ``fenster_grenzen()`` gelesen. Der Wert hier bleibt als Spec-Referenz
#: stehen und wird von **keinem** Codepfad mehr benutzt -- er war der
#: Ausgangspunkt von Befund C.3.
#:
#: ``system`` steht seit dem 06.09.2026 (Auftrag 4) auf dem **gemessenen**
#: Wert statt auf den nie durchgesetzten 900 aus der Spec: je Phase 7.670 bis
#: 9.339 Token. Durchgesetzt wird er nicht hier, sondern von
#: ``SYSTEM_ZEICHEN_MAX`` (Test) und ``gesamtgrenze()`` (Laufzeit).
BUDGETS = {
    "system": 9000,
    "verdichtungen": 3000,
    "transkripte": 5000,
    "kernpaket": 2000,
    "arbeitsstand": 1200,
    # **Das einzige Budget, das wirklich durchgesetzt wird** (06.09.2026,
    # Analyse § 4.2). Es steht hier nicht als Spec-Referenz, sondern als
    # Grenze: ``_baue_festlegungen`` kappt daran und an
    # ``FESTLEGUNGEN_ZEILEN``. Der Grund ist Risiko 1 der Analyse -- der
    # Erkenner neigt zur Uebererfassung, und ein Auffangblock ohne Deckel
    # waechst unbegrenzt. 800 Token sind rund 2.400 Zeichen; die gemessene
    # Gruppe haette in Phase 4 etwa 12 Zeilen a 70 Zeichen erzeugt.
    "festlegungen": 800,
    # Wie "festlegungen" direkt darueber ein kleiner Zusatzblock neben dem
    # eigentlichen Gespraech (Padua Phase 1+2 Umbau, 03.10.2026): der
    # Diskussions-Verdichtungstext ist durch seinen eigenen Prompt schon auf
    # rund 150 Woerter gedeckelt (``interview_theater.diskussion``), ein
    # eigenes Zeichenbudget wird hier wie bei den meisten Eintraegen oben nur
    # dokumentarisch gefuehrt -- durchgesetzt wird er in der Kuerzungsleiter
    # durch Wegwerfen im Ganzen, siehe ``_baue_diskussion_block``.
    "diskussion": 800,
    # Die Begruendungen je Begriff aus dem Begriffsboard (Karte t_4517d4ad):
    # klein wie die Diskussion, und wie sie bei Platznot im Ganzen weg.
    "begriffe_detail": 400,
    # Seit 05.10.2026 (Birk: "Der Chat muss immer ueber alles Bescheid
    # wissen"): das Begriffsboard als eigener Block in jeder Phase, und der
    # Wortlaut alles Mitgehoerten (Diskussion, Brainstorm). Durchgesetzt wird
    # ``mitgehoert`` ueber ``MITGEHOERT_ZEICHEN`` (juengstes zuerst
    # behalten), ``board`` ist durch ``begriffsboard.TOP``-artige Kuerze
    # klein; beide fallen in der Kuerzungsleiter vor den Verdichtungen.
    "board": 500,
    "mitgehoert": 2000,
    "phasenhinweis": 50,
    "figurenhinweis": 100,
    "szene": 2000,
    "journal": 1500,
    "fenster": 8000,
    "ausloeser": 300,
}

#: Zielgroesse Normalfall und Reissleine, in Token (§ 6.2, § 7.2).
ZIEL = 20_000
REISSLEINE = 40_000

#: **Harte Obergrenze des Nutzertextes in ZEICHEN** (Audit 06.09.2026,
#: Befund G4). Bis hierher war ZIEL = 20.000 Token die einzige Bremse -- und
#: sie hat am 06.09. nicht gegriffen: gemessen gingen 52.361 Zeichen raus,
#: nach ``schaetze`` (Zeichen ÷ 3) rund 17.400 Token, also *unter* ZIEL. Der
#: Prompt war damit formal in Ordnung und praktisch unbrauchbar: ein Fenster
#: von 700 Zeilen bis in den Vormittag zurueck, in dem das Modell die
#: Gegenwart nicht mehr fand. § 7.2 der SPEC nennt fuer das Fenster 8.000
#: Token; 24.000 Zeichen (~7.000 Token nach unserer Schaetzung, ~8.000 real
#: bei deutschen Komposita) ist diese Zahl, in der Einheit gemessen, in der
#: wir sie ohne Tokenizer sicher pruefen koennen.
#:
#: Ueber ``IT_PROMPT_ZEICHEN`` konfigurierbar: am Workshoptag muss sich das
#: ohne Codeaenderung nachziehen lassen.
ZEICHEN_GRENZE_VORGABE = 24_000

#: **Harte Obergrenze fuer System + Koerper zusammen, in ZEICHEN** (Audit
#: 06.09.2026, Befund C.1, Auftrag 4). Bis hierher bemass jede Grenze nur den
#: Koerper -- und der ist im Betrieb der kleinere Teil: gemessen standen im
#: Gespraechszug der Testgruppe **26.365 Zeichen Systemanweisung gegen 8.810
#: Zeichen Koerper**, drei Viertel des Prompts also ausserhalb jeder Messung.
#: Wer ``ZEICHEN_GRENZE`` auf 24.000 las und den Prompt fuer ~8.000 Token
#: hielt, irrte um den Faktor 4,4. § 6.2 Block 1 setzt fuer die
#: Systemanweisung 900 Token; gemessen sind es je Phase 7.784-9.339.
#:
#: Wert (30.09.2026, ``docs/kontext-3-5-kalibrierung.md``): **60.000 Zeichen**
#: (~20.000 Token nach unserer Schaetzung -- weit unter Kimis Fenster, 256K).
#: Die 40.000 vom 06.09. schnitten nach dem Prompt-Umbau in 6 von 7 Phasen:
#: gemessen, phasengerechte Vollast, System + Koerper roh bis **53.012
#: Zeichen (Phase 7)**, und die Kuerzung drueckte das Fenster dabei auf 4
#: Eintraege, unter ``FENSTER_MIN_NACHRICHTEN``. Hergeleitet ist 60.000 nicht
#: aus dem letzten Lauf, sondern strukturell: ``SYSTEM_ZEICHEN_MAX`` (36.000)
#: + ``ZEICHEN_GRENZE_VORGABE`` (24.000). Damit greift die Gesamtgrenze erst,
#: wenn schon eine Teilgrenze gebrochen ist -- typisch eine Anweisung, die
#: zur Laufzeit durch Regie-Zettel oder Profil-Anweisung ueber ihren
#: Testdeckel waechst (Befund C.1). Reserve gegen die Messung: 6.988 (13 %).
#: Die Summe steht als Zahl da, nicht als Ausdruck; ein Test
#: (``test_gesamtgrenze_ist_system_plus_koerper``) haelt die Herleitung fest,
#: damit ein angehobener ``SYSTEM_ZEICHEN_MAX`` die Gesamtgrenze nicht still
#: mitzieht, sondern eine bewusste Entscheidung verlangt.
#: Die Koerpergrenze oben bleibt daneben bestehen: sie faengt den Fall, in dem
#: der Koerper allein entgleist, auch wenn die Anweisung gerade kurz ist.
#:
#: Ueber ``IT_PROMPT_ZEICHEN_GESAMT`` konfigurierbar -- dieselbe Ueberlegung
#: wie bei ``IT_PROMPT_ZEICHEN``: am Workshoptag ohne Codeaenderung nachziehbar.
GESAMT_ZEICHEN_GRENZE_VORGABE = 60_000

#: Obergrenze der Systemanweisung je Phase, in Zeichen -- kein Laufzeit-Limit
#: (die Anweisung wird nie gekuerzt, sie ist die Rolle des Bots), sondern eine
#: Zusicherung, die ein Test haelt (``test_prompt_audit``). Sie verhindert,
#: dass ``prompts/system.md`` und ``prompts/phasen/*.md`` unbemerkt
#: weiterwachsen, bis vom Gesamtbudget nichts mehr fuer den Koerper bleibt.
#: Gemessen lag die groesste Phase (2) am 06.09.2026 bei 28.018 Zeichen
#: (Deckel damals 30.000). Beim Merge von feat/kontext-3-5 in den heutigen
#: Stand (30.09.2026) neu gemessen, nach dem Prompt-Umbau auf main
#: (sieben Phasen, Phasentexte, Workshop-Profil), Vorgabeprofil, Bot
#: ``gruppe4``, ohne Regie-Zettel: Phase 1: 26.085 · 2: 33.676 · 3: 27.598 ·
#: 4: 33.064 · 5: 26.883 · 6: 30.014 · 7: 29.389 Zeichen. Der Deckel steht
#: mit demselben Abstand (~7 %) ueber dem Maximum wie vorher: 36.000.
SYSTEM_ZEICHEN_MAX = 36_000


def _aus_umgebung(name: str, vorgabe: int, mindestens: int) -> int:
    """Eine Zeichengrenze aus der Umgebung, mit stillem Rueckfall.

    Bei jedem Aufruf gelesen, nicht beim Import: dieselbe Ueberlegung wie beim
    Hot-Reload der Prompts (``anweisungen.py``) -- eine Aenderung soll ohne
    Neustart wirken. Ein unlesbarer oder unsinniger Wert faellt still auf die
    Vorgabe zurueck; am Workshoptag darf ein Tippfehler in einer Umgebung den
    Bot nicht stumm schalten."""
    roh = os.environ.get(name)
    if not roh:
        return vorgabe
    try:
        wert = int(roh)
    except ValueError:
        log.warning("%s unlesbar (%r), nehme %d", name, roh, vorgabe)
        return vorgabe
    if wert < mindestens:
        log.warning("%s zu klein (%d), nehme %d", name, wert, vorgabe)
        return vorgabe
    return wert


#: Modellwahl-Karte (02.10.2026): die 24.000/60.000-Grenzen oben sind an Kimi
#: kalibriert (SPEC-Faustwert, nie an einem 1-Mio-Kontext gemessen). Opus hat
#: davon ein Vielfaches Platz -- ein Zug ab Phase 4 mit Einwilligung bekommt
#: deshalb EIN eigenes, groesseres Budget (``IT_OPUS_PROMPT_ZEICHEN``), das
#: fuer Koerper UND Gesamtsumme gleichermassen gilt (ein Knopf, kein zweiter).
#: Die Kimi-Grenzen bleiben dabei unveraendert (``ueber_claude=False`` ist
#: der Rueckfall jedes bestehenden Aufrufers).
OPUS_ZEICHEN_GRENZE_VORGABE = 400_000


def zeichengrenze(ueber_claude: bool = False) -> int:
    """Die geltende harte Obergrenze des **Koerpers** in Zeichen
    (``IT_PROMPT_ZEICHEN``, oder -- ab Phase 4 mit Einwilligung --
    ``IT_OPUS_PROMPT_ZEICHEN``). Die Gesamtgrenze steht in ``gesamtgrenze()``."""
    if ueber_claude:
        return _aus_umgebung(
            "IT_OPUS_PROMPT_ZEICHEN", OPUS_ZEICHEN_GRENZE_VORGABE, 20_000
        )
    return _aus_umgebung("IT_PROMPT_ZEICHEN", ZEICHEN_GRENZE_VORGABE, 2_000)


def gesamtgrenze(ueber_claude: bool = False) -> int:
    """Die geltende harte Obergrenze fuer **System + Koerper** in Zeichen
    (``IT_PROMPT_ZEICHEN_GESAMT``, Auftrag 4; oder ``IT_OPUS_PROMPT_ZEICHEN``,
    Modellwahl-Karte)."""
    if ueber_claude:
        return _aus_umgebung(
            "IT_OPUS_PROMPT_ZEICHEN", OPUS_ZEICHEN_GRENZE_VORGABE, 20_000
        )
    return _aus_umgebung(
        "IT_PROMPT_ZEICHEN_GESAMT", GESAMT_ZEICHEN_GRENZE_VORGABE, 4_000
    )

#: Ab dieser Zeitspanne zwischen zwei Nachrichten im Fenster wird eine
#: Pausenzeile eingeschoben (§ 6.2 "Pausenmarkierung").
PAUSE_AB_MINUTEN = 60

#: Feste Reihenfolge des Prompt-Koerpers (ohne SYSTEM, das separat verschickt
#: wird): stabil nach vorn, fluechtig nach hinten.
_REIHENFOLGE = (
    "verdichtungen", "transkripte", "kernpaket", "arbeitsstand", "festlegungen",
    "diskussion", "begriffe_detail", "board", "mitgehoert", "phasenhinweis",
    "figurenhinweis", "szene",
    "journal", "fenster", "ausloeser", "erstkontakt",
)


#: Die Koepfe und Zeilenbeschriftungen des Nutzertexts (W3: ein englischer
#: Systemprompt mit deutschem Nutzertext liesse das Modell deutsch
#: antworten). Jede steht genau einmal hier, die Blockfunktionen lesen sie
#: zur Aufrufzeit ueber ``T``.
#:
#: ``_SPRECHER_BOT``: so heisst der Bot im Verlauf (``sprecherzeile``) -- das
#: Modell liest seine eigenen frueheren Aeusserungen in der zweiten Person.
_SPRECHER_BOT = "Du"
#: Wie ein Mitglied der Gruppe im Prompt heisst, wenn das Profil Pseudonyme
#: verlangt (E8, Karte A1). In Dortmund nie benutzt -- die deutsche Tabelle
#: braucht trotzdem einen Wert.
_PSEUDONYM = "Mitglied {nummer}"
_PSEUDONYM_UNBEKANNT = "Mitglied"
#: Hinweistext fuer eine Nachricht, die das Sprachmodell nicht sehen kann
#: (Padua Hotfix Befund 2, 02.10.2026): ein Bildanhang, ein Sticker oder ein
#: sonstiger Dateianhang erschien vorher wortgleich mit seinem internen
#: Telegram-Typnamen -- das ist sowohl unuebersetzt (immer deutsch, egal in
#: welcher Chatsprache) als auch irrefuehrend, weil es nicht sagt, dass das
#: Modell den Anhang gar nicht wahrnimmt. Siehe ``_TYPEN_NICHT_SICHTBAR``.
_HINWEIS_NICHT_SICHTBAR = "Datei -- fuer mich nicht sichtbar"
#: Padua Hotfix Befund 1 (02.10.2026): die Markierung hinter dem Sprecher, wenn
#: der Text das Transkript einer Sprachnachricht ist (``nachricht.gesprochen``)
#: -- "Mitglied 1 (Sprachnachricht): ...". Live hielt das Modell ein
#: Transkript fuer getippt und behauptete auf "verstehst du mich?", es koenne
#: die Sprachnachricht nicht abtippen. Nur im Gespraechs-Prompt, siehe
#: ``sprecherzeile``.
_MARKE_GESPROCHEN = "Sprachnachricht"
#: Padua Hotfix Befund 3 (02.10.2026, Live-Fall web_post 6/8/10): das
#: englische Profil antwortete auf deutsche Gruppennachrichten auf Deutsch --
#: "Write in English" in system.md stand nur einmal, ganz am Anfang des
#: Zuges, und verlor gegen das Recency-Gewicht der zuletzt gelesenen
#: fremdsprachigen Nachricht. Deutsch bleibt leer (die Gruppe schreibt hier
#: ohnehin deutsch, eine Erinnerung waere Laerm); die englische Tabelle
#: traegt den Satz, und ``_baue_ausloeser`` haengt ihn an den Ausloeser-Block
#: an -- den einen Block, der jede Kuerzung ueberlebt (§ 7.2) und im
#: normalen Gespraechszug (kein Erstkontakt) der zuletzt gelesene Text vor
#: der Antwort ist.
_AUSLOESER_SPRACHREGEL = ""
_PAUSE_STUNDE = "[Pause: {stunden} Stunde]"
_PAUSE_STUNDEN = "[Pause: {stunden} Stunden]"
_ZEILE_KERNTHEMA = "Kernthema: {kernthema}"
_ZEILE_BEGRUENDUNG = " (Begruendung: {begruendung})"
_BEZEICHNUNG_AUFNAHME = "Aufnahme {id}"
_VERDICHTUNGEN_KOPF = "Verdichtungen:\n"
_ZEILE_VOLLTRANSKRIPT = "--- {name} (Volltranskript) ---\n{transkript}"
_VOLLTRANSKRIPTE_KOPF = "Volltranskripte:\n"
_GESCHICHTE_KOPF = "Geschichte:\n"
_KERNFRAGE_KOPF = "Kernfrage:\n"
_ZEILE_SETTING_RAHMEN = "Setting (Rahmen): {rahmen}"
_STELLEN_KOPF = "Passende Stellen aus den Interviews (die Ausarbeitungsgrundlage):"
_KERNZITATE_KOPF = "Kernzitate (woertlich, geprueft):"
_FIGUREN_KOPF = "Figuren:"
_ZEILE_SPRACHDUKTUS = "    Sprachduktus: {profil}"
_ZEILE_AUS_INTERVIEW = '    Aus {name}: {thema} -- "{zitat}"'
_GESCHAERFT_KOPF = "Geschaerft am Material, je Szene:\n"
_SZENE_MIT_NUMMER = "Szene {nummer}"
_SZENE_OHNE_NUMMER = "Szene"
_ZEILE_AKTUELLE_PHASE = "Aktuelle Phase: {phase}"
_ZEILE_BEGRIFFE = "Begriffe: {wert}"
_ZEILE_FRAGEN = "Fragen: {wert}"
_ZEILE_RAHMEN = "Rahmen: {wert}"
_ZEILE_HAUPTKONFLIKT = "Hauptkonflikt: {wert}"
_ZEILE_FIGUR = "Figur {name}{beschreibung}"
_ARBEITSSTAND_KOPF = "Arbeitsstand:\n"
_TEXT_AKTUELLE_SZENE = "Aktuelle Szene ({szene}):\n{volltext}"
_JOURNAL_KOPF = "Journal:\n"

#: Wie die Art eines Journaleintrags (``journal.art``, ein Datenbankwert) in
#: einer Journalzeile des Nutzertexts steht. Deutsch: der Wert selbst
#: (``- [notiert] …``, zeichengleich zum Stand vor Aufgabe 30); die englische
#: Tabelle uebersetzt ihn wie ``web.JOURNALART_BESCHRIFTUNG`` -- sonst stand
#: im englischen Gespraechs- und Journal-Prompt "[notiert]" (Render-Pruefer,
#: Quelle c2). Unbekannte Arten bleiben roh.
JOURNALART_BESCHRIFTUNG = {
    "vorgeschlagen": "vorgeschlagen",
    "verworfen": "verworfen",
    "entschieden": "entschieden",
    "offen": "offen",
    "notiert": "notiert",
}
_AUSLOESER_KOPF = "Aktuell:\n"


def kernthema_zeile(stand) -> str:
    """Die Zeile "Kernthema: … (Begruendung: …)" aus einem Arbeitsstand.

    Sie stand am 06.09.2026 wortgleich an drei Stellen (zweimal hier, einmal
    in ``szene._thema_text``) -- und ein Fakt hat genau eine Stelle im Prompt,
    also auch genau eine im Code, die ihn formt. Ohne Kernthema: leerer
    String, der Aufrufer haengt nichts an."""
    if not stand["kernthema"]:
        return ""
    zeile = T._ZEILE_KERNTHEMA.format(kernthema=stand["kernthema"])
    if stand["kernthema_begruendung"]:
        zeile += T._ZEILE_BEGRUENDUNG.format(begruendung=stand["kernthema_begruendung"])
    return zeile


def schaetze(text: str) -> int:
    """Schaetzt die Tokenzahl eines Textes: Zeichen ÷ 3, kein Tokenizer (§ 7.1)."""
    return len(text) // _ZEICHEN_JE_TOKEN


def pseudonyme(conn, chat_id: int, zeilen=()) -> dict[str, str] | None:
    """{Vorname: "Member N"} nach erstem Auftreten, oder None, wenn das
    Profil keine Pseudonyme verlangt (dann bleibt alles, wie es war).
    ``zeilen`` ergaenzt Namen, die (noch) nicht in der Datenbank stehen --
    der Korpuslauf fuettert den Erkenner mit Zeilen ohne DB (pruefe_prompts).

    "Ein Modell kann keinen Namen verwenden, den es nie sieht" (E8): die
    Regel steht im Prompt, dieser Schalter sorgt dafuer, dass der Code gar
    keinen Vornamen hineinlegt. Stabil ist die Nummer, weil sie aus der
    Reihenfolge des ersten Auftretens kommt (``repo.absender_in_reihenfolge``)
    -- wer als Erste geschrieben hat, bleibt "Member 1", auch wenn sie
    laengst aus dem Fenster gefallen ist."""
    if not sprache.pseudonyme():
        return None
    namen = list(repo.absender_in_reihenfolge(conn, chat_id))
    for n in zeilen:
        absender = n["absender"]
        if not n["ist_bot"] and absender and absender not in namen:
            namen.append(absender)
    return {name: T._PSEUDONYM.format(nummer=i) for i, name in enumerate(namen, start=1)}


#: Nachrichtentypen (Telegram-Rohwerte aus ``telegram._bestimme_typ``, siehe
#: ``db.py``), die das Sprachmodell nicht sehen kann -- es bekommt nur Text
#: (Padua Hotfix Befund 2, 02.10.2026: "das Modell kann in dieser Konfig
#: keine Bilder sehen, entsprechend soll es das auch nicht anbieten"). Feste
#: Telegram-Typnamen, keine Nutzertexte -- deshalb nicht ueber ``T``.
#: ``"dokument"`` (Review-Nachbesserung Befund 2): jeder Datei-Upload ohne
#: Bildunterschrift (PDF, Word, ein beliebiger Anhang) lief sonst weiterhin
#: als "(dokument)" durch -- derselbe Fehler wie bei "foto", nur ueber den
#: anderen Telegram-Nachrichtentyp. ``"sprache"`` bleibt bewusst aussen vor:
#: eine Sprachnachricht bekommt binnen Sekunden ihr Transkript, "dokument"
#: dagegen nie (Whisper transkribiert keine PDFs). Der Web-Kanal
#: (``web_kanal.py``) erzeugt nie "foto"/"sticker"/"dokument" -- er kennt nur
#: Text, Knopf, Befehl und "sprache" (Segment/PTT); diese Typen sind reiner
#: Telegram-Weg.
_TYPEN_NICHT_SICHTBAR = frozenset({"foto", "sticker", "sonstiges", "dokument"})


def _ist_gesprochen(n) -> bool:
    """``nachricht.gesprochen`` -- tolerant gegen Zeilen und Dicts ohne die
    Spalte (Korpusfaelle, Testdicts, eine noch nicht migrierte Kopie)."""
    try:
        return bool(n["gesprochen"])
    except (KeyError, IndexError):
        return False


def sprecherzeile(n, namen: dict[str, str] | None = None,
                  gesprochen_markieren: bool = False) -> str:
    """Formatiert eine ``nachricht``-Zeile als ``"Sprecher: Text"``.

    Bot-Nachrichten erscheinen als Sprecher ``Du`` (``_SPRECHER_BOT``,
    englisch ``You``): das Sprachmodell bekommt
    den Verlauf als einen zusammenhaengenden Text, nicht als mehrteiligen
    Chat mit eigener Rolle je Zug, und liest darin seine eigenen frueheren
    Aeusserungen in der zweiten Person. Menschliche Nachrichten tragen den
    Vornamen aus ``nachricht.absender``.

    Nachrichten ohne Text (Sprache ohne Transkript, ...) erscheinen als
    ``"Name: (typ)"`` statt als leere Zeile -- die Gruppe hat etwas
    geschickt, und das Modell soll das wissen. Ein Typ aus
    ``_TYPEN_NICHT_SICHTBAR`` (Bildanhang, Sticker, Dokument-Upload,
    sonstiger Anhang) bekommt stattdessen den lokalisierten Hinweis
    ``_HINWEIS_NICHT_SICHTBAR`` ("Datei -- fuer mich nicht sichtbar" /
    "file -- not visible to you"): das reine Text-Modell bekommt solche
    Anhaenge nie, und der blosse Telegram-Typname waere sowohl unuebersetzt
    als auch eine falsche Behauptung ueber das, was es wahrnimmt (Befund 2).

    ``namen`` (E8, Karte A1): steht dort ein Mapping (``pseudonyme()``),
    ersetzt es den Vornamen; ein Name, der darin fehlt, wird nie
    durchgereicht, sondern heisst "Member". ``None`` ist das alte Verhalten.

    ``gesprochen_markieren`` (Padua Hotfix Befund 1): ist der Text das
    Transkript einer Sprachnachricht, steht ``_MARKE_GESPROCHEN`` in Klammern
    hinter dem Sprecher ("Mitglied 1 (Sprachnachricht): ..."). Eingeschaltet
    nur im Gespraechs-Prompt (Fenster und Ausloeser); Erkenner und Journal
    rufen ohne, weil ihre Few-Shot-Prompts gegen den Korpus gemessen sind und
    die Herkunft eines Beitrags dort nichts entscheidet.
    """
    if n["ist_bot"]:
        sprecher = T._SPRECHER_BOT
    elif namen is None:
        sprecher = n["absender"]
    else:
        sprecher = namen.get(n["absender"], T._PSEUDONYM_UNBEKANNT)
    text = n["text"]
    if text:
        if gesprochen_markieren and _ist_gesprochen(n):
            return f"{sprecher} ({T._MARKE_GESPROCHEN}): {text}"
        return f"{sprecher}: {text}"
    if n["typ"] in _TYPEN_NICHT_SICHTBAR:
        return f"{sprecher}: ({T._HINWEIS_NICHT_SICHTBAR})"
    return f"{sprecher}: ({n['typ']})"


def _pausenzeile(vorher_iso: str, nachher_iso: str) -> str | None:
    """Baut ``"[Pause: N Stunden]"``, wenn zwischen zwei Zeitstempeln mehr als
    PAUSE_AB_MINUTEN liegen -- sonst None. Die Zeitstempel sind ISO-8601 mit
    Zeitzone (repo._jetzt()); datetime.fromisoformat vergleicht sie ueber
    Zeitzonen hinweg korrekt, ohne dass wir selbst normalisieren muessten."""
    vorher = datetime.fromisoformat(vorher_iso)
    nachher = datetime.fromisoformat(nachher_iso)
    minuten = (nachher - vorher).total_seconds() / 60
    if minuten <= PAUSE_AB_MINUTEN:
        return None
    stunden = max(1, round(minuten / 60))
    muster = T._PAUSE_STUNDE if stunden == 1 else T._PAUSE_STUNDEN
    return muster.format(stunden=stunden)


def interviewbezeichnung(conn, chat_id: int, aufnahme_id: int | None) -> str:
    """'Interview 2' -- die Nummer in der Reihenfolge der langen Aufnahmen
    der Gruppe. NIE der Aufnahmename (Birk 05.09.): der ist oft ein
    Klarname oder nur der Telegram-Name dessen, der das Handy hielt, und er
    gehoert weder ins Modell (das ihn als 'spricht wie Birk' nachplappert)
    noch aufs Dashboard. Ohne Treffer: 'Interview' plus id."""
    if aufnahme_id is None:
        return ""
    lange = [a for a in repo.transkripte(conn, chat_id) if a["klasse"] == "lang"]
    for n, a in enumerate(lange, start=1):
        if a["id"] == aufnahme_id:
            return f"Interview {n}"
    return f"Interview {aufnahme_id}"


def _baue_verdichtungen(conn, chat_id: int) -> str:
    bloecke = []
    for v in repo.verdichtungen(conn, chat_id):
        name = (interviewbezeichnung(conn, chat_id, v["aufnahme_id"])
                or T._BEZEICHNUNG_AUFNAHME.format(id=v["aufnahme_id"]))
        zeilen = [f"{name}: {v['zusammenfassung']}"]
        for thema in repo.themen_zu(conn, v["id"]):
            if thema["beleg_zitat"]:
                zeilen.append(f'  - {thema["thema"]}: "{thema["beleg_zitat"]}"')
            else:
                zeilen.append(f'  - {thema["thema"]}')
        bloecke.append("\n".join(zeilen))
    if not bloecke:
        return ""
    return T._VERDICHTUNGEN_KOPF + "\n\n".join(bloecke)


def _baue_transkripte(conn, chat_id: int) -> str:
    """Volltranskripte -- nur wenn der Schalter ``gruppe.wortlaut_modus``
    gesetzt ist (SPEC § 6.2 Block 3). Ohne ihn waeren Transkripte ab
    Samstagmittag 5.000 Token Dauerlast, die jede Antwort unschaerfer macht;
    die Kuerzung (§ 7.2) faengt das nicht zuverlaessig ab, weil sie erst ab
    ZIEL greift und ein Nachmittag mit drei bis fuenf Interviews oft darunter
    bleibt. NULL/leer heisst kein Block, ``'*'`` heisst alle, jeder andere
    Wert ist ein Name und filtert grosszuegig wie ``repo.transkripte``.

    Der Slash-Befehl ``/wortlaut`` selbst (der dieses Feld setzt) wird erst
    in einer spaeteren Aufgabe gebaut (``befehle.py``); das Datenbankfeld
    existiert aber bereits seit Aufgabe 1 und wird hier rein lesend
    ausgewertet.

    Nur Aufnahmen der Klasse ``'lang'`` zaehlen als Material im Sinne von
    § 10.1 -- kurze Gespraechsbeitraege (Zurufe, Regieanweisungen) stehen
    ohnehin schon im Fenster; sie hier zusaetzlich als Volltranskript
    aufzufuehren wuerde denselben Inhalt verdoppeln und einen Zuruf
    faelschlich zu Interview-Material erklaeren.

    Je Interview EIN Transkript (§ 10.6, ``repo.zusammengefuegtes_transkript``):
    die Teile werden zusammengefuegt, in Reihenfolge, durch eine Leerzeile
    getrennt. Ein Interview aus fuenf Sprachnachrichten ist ein Gespraech, und
    als fuenf Bloecke gelesen zerfiele es genau dort, wo es interessant wird.
    Das gilt auch fuer ein noch laufendes Interview -- die Gruppe soll den
    Wortlaut mitlesen koennen, waehrend er entsteht.
    """
    gruppe = repo.hole_gruppe(conn, chat_id)
    modus = gruppe["wortlaut_modus"] if gruppe else None
    if not modus:
        return ""
    name = None if modus == "*" else modus

    zeilen = []
    for a in repo.transkripte(conn, chat_id, name=name):
        if a["klasse"] != "lang":
            continue
        transkript = repo.zusammengefuegtes_transkript(conn, a["id"])
        if transkript:
            # E8: in einem Profil mit Pseudonymen nie der Aufnahmename (oft
            # ein Klarname), sondern die Nummer wie bei den Verdichtungen.
            anzeige = (interviewbezeichnung(conn, chat_id, a["id"])
                       if sprache.pseudonyme() else a["name"])
            zeilen.append(T._ZEILE_VOLLTRANSKRIPT.format(name=anzeige, transkript=transkript))
    if not zeilen:
        return ""
    return T._VOLLTRANSKRIPTE_KOPF + "\n\n".join(zeilen)


# --- Das Kernpaket (05.09.2026 abends) ------------------------------------
#
# **Warum es das gibt.** Bis zu diesem Abend bekam der Figuren-Prompt alle
# Verdichtungen und alle Transkripte, und ``prompts/phasen/4.md`` verlangte
# Figuren, "die sich auf Interviewstellen stuetzen". Die Figuren kamen damit
# aus den Interviews statt aus dem, was die Gruppe selbst festgelegt hatte,
# und sie konnte den Weg dorthin nicht nachvollziehen (Birk, nach dem
# Regie-Test). Damals hiess dieses Festgelegte "Kernthema".
#
# Ab den Figuren steht deshalb an der Stelle von Verdichtungen und
# Transkripten EIN Block: das Kernpaket. Es enthaelt die **Geschichte**
# (Bogen und Ende), Kernfrage und Kernthema, solange eine Gruppe eines
# gesetzt hat, die ausgewaehlten Kernzitate, die gefilterten Verdichtungen
# (nur die markierten Themen, mit Interview-Nummer), die Figuren mit ihrem
# Sprachprofil und den Rahmen. Die Verdichtungen fliegen also nicht raus --
# sie werden gefiltert, genau wie die Zitate.
#
# **Die Geschichte ist die Quelle, nicht das Kernthema** (06.09.2026, Umbau
# der Phasen; englisch seit c8, deutsch seit Karte P2-Fix am 02.10.2026):
# ``_baue_kernpaket`` setzt ``arbeitsstand.geschichte`` an den Anfang, das
# Kernthema steht nur darunter und nur, wenn es gesetzt ist.

KERNPAKET_KOPF = (
    "Das Kernpaket - hieraus arbeitest du. Figuren und Szenen kommen aus der "
    "Geschichte und dieser Auswahl, nicht aus den Interviews (die stehen dir "
    "hier bewusst nicht mehr im Wortlaut zur Verfuegung):"
)


def _baue_kernpaket(conn, chat_id: int) -> str:
    """Der Block, der ab den Figuren an die Stelle von Verdichtungen und
    Transkripten tritt.

    Datengetrieben wie alles: jeder Teil faellt weg, solange seine Daten leer
    sind, und erst wenn ALLE leer sind, gibt es gar keinen Block. Das
    Kernthema ist dabei kein Schalter mehr: die Geschichte
    (``arbeitsstand.geschichte``) steht vorn und traegt den Block allein,
    ebenso Setting, Themen, Kernzitate, Figuren oder Schaerfungen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen: list[str] = []
    # Die Geschichte steht vorn: sie hat die Rolle uebernommen, die bis zum
    # Umbau vom 05.09.2026 nachts das Kernthema hatte -- der Bogen, an dem
    # alles haengt. Das Kernthema bleibt darunter stehen, solange eine alte
    # Gruppe eines gesetzt hat (rueckwaertskompatibel).
    if "geschichte" in stand.keys() and stand["geschichte"]:
        zeilen.append(T._GESCHICHTE_KOPF + stand["geschichte"].strip())
    kernthema = kernthema_zeile(stand)
    if kernthema:
        zeilen.append(kernthema)
    if stand["kernfrage"]:
        zeilen.append(T._KERNFRAGE_KOPF + stand["kernfrage"].strip())
    if stand["rahmen"]:
        zeilen.append(T._ZEILE_SETTING_RAHMEN.format(rahmen=stand["rahmen"]))

    themen = repo.kernthemen_themen(conn, chat_id)
    if themen:
        block = [T._STELLEN_KOPF]
        # Die Zusammenfassung gehoert der VERDICHTUNG, nicht dem Thema:
        # ``kernthemen_themen`` liefert sie je Zeile mit, und ein Interview mit
        # elf markierten Themen schrieb sie deshalb elfmal in den Prompt --
        # gemessen am 06.09.2026: derselbe 700-Zeichen-Absatz 11x, allein
        # 7.700 Zeichen Dublette (Audit-Befund G1). Jetzt einmal je Interview,
        # danach nur noch die Themenzeilen.
        gesehen: set[str] = set()
        for thema in themen:
            name = interviewbezeichnung(conn, chat_id, thema["aufnahme_id"])
            block.append(f"- {name}: {thema['thema']}")
            zusammenfassung = (thema["zusammenfassung"] or "").strip()
            if zusammenfassung and zusammenfassung not in gesehen:
                gesehen.add(zusammenfassung)
                block.append(f"    {zusammenfassung}")
        zeilen.append("\n".join(block))

    zitate = repo.kernzitate(conn, chat_id)
    if zitate:
        block = [T._KERNZITATE_KOPF]
        for eintrag in zitate:
            name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
            zeile = f'- {name}: "{eintrag["zitat"]}"'
            if eintrag["begruendung"]:
                zeile += f" ({eintrag['begruendung']})"
            block.append(zeile)
        zeilen.append("\n".join(block))

    figuren = repo.figuren(conn, chat_id)
    if figuren:
        block = [T._FIGUREN_KOPF]
        for figur in figuren:
            kopf = figur["name"]
            if figur["beschreibung"]:
                kopf += f" -- {figur['beschreibung']}"
            block.append(f"- {kopf}")
            if figur["sprachprofil"]:
                block.append(T._ZEILE_SPRACHDUKTUS.format(profil=figur["sprachprofil"].strip()))
            for eintrag in repo.schaerfungen(conn, chat_id, figur_id=figur["id"]):
                name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
                block.append(T._ZEILE_AUS_INTERVIEW.format(
                    name=name, thema=eintrag["thema"], zitat=eintrag["zitat"],
                ))
        zeilen.append("\n".join(block))

    # Die Schaerfungen je Szene (Phase 6): jede Szene mit den Stellen, die
    # ihr zugeordnet wurden. Datengetrieben wie alles -- ohne Zuordnung kein
    # Block.
    szenenbloecke: list[str] = []
    for szene in repo.hole_szenen(conn, chat_id):
        eintraege = repo.schaerfungen(conn, chat_id, szene_id=szene["id"])
        if not eintraege:
            continue
        block = [szenenzeile(szene)]
        for eintrag in eintraege:
            name = interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
            zeile = f'  - {name}: {eintrag["thema"]} -- "{eintrag["zitat"]}"'
            if eintrag["begruendung"]:
                zeile += f" ({eintrag['begruendung']})"
            block.append(zeile)
        szenenbloecke.append("\n".join(block))
    if szenenbloecke:
        zeilen.append(T._GESCHAERFT_KOPF + "\n".join(szenenbloecke))

    if not zeilen:
        return ""
    return T.KERNPAKET_KOPF + "\n" + "\n".join(zeilen)


#: Die Erfindungsphase (Umbau 05.09.2026 nachts, zusammengelegt am
#: 06.09.2026): 4 Setting, Figuren & Geschichte. Dort sieht der Bot **kein**
#: Material -- keine Verdichtungen, keine Transkripte, kein Kernpaket.
#: Vorschlaege kommen ausschliesslich aus Begriffen, Fragen und dem, was die
#: Gruppe schon festgelegt hat.
#:
#: Ein Tupel und keine einzelne Zahl: bis heute waren es zwei Stationen, und
#: die Filter unten fragen nach dem Bereich, nicht nach einer Nummer -- eine
#: kuenftige zweite Erfindungsphase braucht dann nur diese Zeile.
PHASEN_ERFINDEN = (4,)

#: Ab dieser Phase arbeitet der Bot aus dem Kernpaket (mit den Schaerfungen).
PHASE_KERNPAKET = 5


def material_erlaubt(conn, chat_id: int) -> bool:
    """Duerfen Verdichtungen und Transkripte in den Prompt?

    Ja bis einschliesslich Phase 3: dort wird aufgenommen und ausgewertet,
    und die Verdichtung gehoert in den Chat. **Nein in 4** -- das ist
    der Kern des Umbaus vom 05.09.2026 nachts: Setting, Figuren und
    Geschichte erfindet die Gruppe frei, und ein Bot, der dabei alle
    Interviews vor sich hat, schlaegt nichts anderes vor als die Interviews.
    Nein auch ab 5, aber aus dem alten Grund: dort traegt das Kernpaket.

    Eine reine Leseabfrage aus einem Feld, kein gespeicherter Zustand --
    geht die Gruppe zurueck nach 3, ist das Material wieder da."""
    return phasen.aktuelle(conn, chat_id) < min(PHASEN_ERFINDEN)


def kernpaket_erlaubt(conn, chat_id: int) -> bool:
    """Darf das Kernpaket in den Prompt? Erst ab der Schaerfung (Phase 5).

    In 4 waere es dasselbe Leck wie die Verdichtungen: das Kernpaket
    traegt Zitate und gefilterte Verdichtungen, und genau die sollen dort
    nicht auf dem Tisch liegen."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_KERNPAKET


def szenenzeile(s) -> str:
    """Eine Szene als eine Zeile: Nummer, Titel, Kurzbeschreibung (SPEC § 6.2
    Block 4). Fehlt eines der Felder, faellt nur dieser Teil weg -- die Zeile
    bleibt lesbar, auch wenn das Sprachmodell einmal keinen Titel geliefert
    hat und ``interview_theater.szene`` auf 'Szene N' zurueckgefallen ist."""
    kopf = (T._SZENE_MIT_NUMMER.format(nummer=s["nummer"])
            if s["nummer"] is not None else T._SZENE_OHNE_NUMMER)
    if s["titel"]:
        kopf += f": {s['titel']}"
    if s["kurzbeschreibung"]:
        return f"{kopf} - {s['kurzbeschreibung']}"
    return kopf


def _baue_arbeitsstand(conn, chat_id: int, ohne_kernpaket_felder: bool = False) -> str:
    """Der Arbeitsstand -- was die Gruppe festgelegt hat.

    ``ohne_kernpaket_felder`` laesst die Felder weg, die im selben Prompt
    schon im Kernpaket stehen (Audit-Befund G2, 06.09.2026): Geschichte,
    Kernthema, Kernfrage, Rahmen und die Figurenzeilen standen an beiden
    Stellen wortgleich -- Kernthema und Rahmen sogar dreimal, weil das
    Kernpaket den Rahmen als "Setting (Rahmen)" fuehrt. Ein Fakt, der zweimal
    dasteht, ist kein Fakt mehr, sondern eine Betonung, und das Modell hat sie
    am 05.09. um 21:50 als solche gelesen. **Eine Quelle je Fakt**: steht das
    Kernpaket im Prompt, gehoeren diese Felder ihm; sonst dem Arbeitsstand.

    Begriffe, Fragen, Hauptkonflikt und die Szenenliste bleiben immer hier --
    sie stehen im Kernpaket nicht."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    figuren = repo.figuren(conn, chat_id)
    szenen = repo.hole_szenen(conn, chat_id)

    zeilen = []
    # Die Phase steht ganz vorn im Arbeitsstand -- aber nur, wenn sie
    # tatsaechlich gesetzt wurde. Ein NULL-Feld ist kein Wissen: solange
    # niemand eine Phase genannt hat, gibt es nichts zu berichten, und der
    # Block bleibt weg wie jeder andere leere Block (SPEC § 6.1). Den Fokus
    # bekommt der Bot in diesem Fall trotzdem, ueber prompts/phasen/1.md
    # (anweisungen.system).
    gespeicherte_phase = repo.hole_phase(conn, chat_id)
    if gespeicherte_phase is not None:
        zeilen.append(T._ZEILE_AKTUELLE_PHASE.format(phase=phasen.bezeichnung(gespeicherte_phase)))
    if stand:
        if stand["begriffe"]:
            zeilen.append(T._ZEILE_BEGRIFFE.format(wert=stand["begriffe"]))
        if stand["fragen"]:
            zeilen.append(T._ZEILE_FRAGEN.format(wert=stand["fragen"]))
        kernthema = kernthema_zeile(stand)
        if kernthema and not ohne_kernpaket_felder:
            zeilen.append(kernthema)
        if stand["kernfrage"] and not ohne_kernpaket_felder:
            zeilen.append(T._KERNFRAGE_KOPF + stand["kernfrage"].strip())
        # Die Geschichte im Groben (Phase 5): Bogen und Ende.
        if ("geschichte" in stand.keys() and stand["geschichte"]
                and not ohne_kernpaket_felder):
            zeilen.append(T._GESCHICHTE_KOPF + stand["geschichte"].strip())
        # Der Rahmen (Phase 5, seit 05.09.2026). Datengetrieben wie alles
        # andere: der Hauptkonflikt steht nur da, wenn die Gruppe einen wollte
        # -- er ist eine Rahmen-Entscheidung, keine Pflicht. Ein "Format" des
        # Stuecks steht hier seit dem Abend des 05.09.2026 nicht mehr: es
        # wird nicht mehr gefragt, also wird es auch nicht mehr vorgehalten.
        if stand["rahmen"] and not ohne_kernpaket_felder:
            zeilen.append(T._ZEILE_RAHMEN.format(wert=stand["rahmen"]))
        if stand["hauptkonflikt"]:
            zeilen.append(T._ZEILE_HAUPTKONFLIKT.format(wert=stand["hauptkonflikt"]))
    if not ohne_kernpaket_felder:
        for figur in figuren:
            beschreibung = f": {figur['beschreibung']}" if figur["beschreibung"] else ""
            zeilen.append(T._ZEILE_FIGUR.format(name=figur["name"], beschreibung=beschreibung))
    # Szenenliste: Teil des Arbeitsstands, nicht ein eigener Block -- SPEC
    # § 6.2 fuehrt sie woertlich in Block 4 auf ("Begriffe, Fragen, Kernthema +
    # Begruendung, Figuren, Konflikt, Szenenliste"). Nur Titel und die eine
    # Kurzbeschreibungszeile; die Volltexte waeren bei sechs Szenen rund 6.000
    # Token Dauerlast, deshalb geht davon nur die zuletzt geaenderte mit
    # (Block 5, _baue_szene).
    for szene in szenen:
        zeilen.append(szenenzeile(szene))

    if not zeilen:
        return ""
    return T._ARBEITSSTAND_KOPF + "\n".join(zeilen)


#: Die Kopfzeile des Festlegungs-Blocks. Bewusst "weitere": der Arbeitsstand
#: steht direkt darueber, und das Modell soll den Block als seine Fortsetzung
#: lesen -- nicht als eine zweite, konkurrierende Wahrheit.
FESTLEGUNGEN_KOPF = "Weitere Festlegungen der Gruppe (gelten wie der Arbeitsstand):"

#: Wie viele Festlegungen hoechstens in den Prompt gehen (Analyse § 4.2).
#: Zusammen mit ``BUDGETS["festlegungen"]`` der Deckel gegen Risiko 1
#: (Prompt-Inflation durch einen uebererfassenden Erkenner).
FESTLEGUNGEN_ZEILEN = 20


def _baue_festlegungen(conn, chat_id: int) -> str:
    """Die Auffangtabelle als Block, direkt hinter dem Arbeitsstand.

    **Die aeltesten Zeilen bleiben** -- und das ist der eine Punkt, an dem
    dieser Block sich vom Journal unterscheidet (``_baue_journal`` behaelt
    die letzten N). Der Grund steht in der Analyse: eine fruehe
    Grundfestlegung ("nur eine Szene, erste Folge einer Serie") wiegt mehr
    als eine spaete Detailnotiz -- und genau diese Grundfestlegung ist am
    06.09. aus dem Prompt gefallen, wonach das System sechs Szenen baute.

    Zwei Deckel, weil zwei Fehler drohen: ``FESTLEGUNGEN_ZEILEN`` gegen
    viele kurze Zeilen, ``BUDGETS["festlegungen"]`` gegen wenige lange. Die
    Tabelle selbst bleibt unangetastet -- gekuerzt wird nur die Sicht des
    Modells, wie beim Journal.

    Datengetrieben wie jeder Block: keine Festlegung, kein Block."""
    eintraege = repo.festlegungen(conn, chat_id)
    if not eintraege:
        return ""
    grenze = BUDGETS["festlegungen"] * _ZEICHEN_JE_TOKEN
    zeilen: list[str] = []
    kopf = T.FESTLEGUNGEN_KOPF
    laenge = len(kopf)
    for eintrag in eintraege[:FESTLEGUNGEN_ZEILEN]:
        zeile = "- " + repo.festlegungszeile(
            eintrag["bereich"], eintrag["bezug"], eintrag["text"]
        )
        if zeilen and laenge + 1 + len(zeile) > grenze:
            break
        zeilen.append(zeile)
        laenge += 1 + len(zeile)
    return kopf + "\n" + "\n".join(zeilen)


#: Die Kopfzeile des Diskussions-Blocks (Padua Phase 1+2 Umbau, 03.10.2026).
DISKUSSION_KOPF = "Aus eurer Begriffs-Diskussion:"


def _baue_diskussion_block(conn, chat_id: int) -> str:
    """Die Verdichtung der Hintergrund-Diskussion aus Phase 1 (Padua Phase
    1+2 Umbau, 03.10.2026, ``interview_theater.diskussion``) -- direkt hinter
    den Festlegungen, weil sie denselben Rang hat: etwas, das die Gruppe vor
    dem eigentlichen Gespraech gesagt hat und das sonst nirgends im Prompt
    stuende.

    Kein eigenes Zeichenbudget noetig wie bei ``_baue_festlegungen``: der
    Verdichtungs-Prompt selbst deckelt den Text auf rund 150 Woerter.

    Datengetrieben wie jeder Block: keine Verdichtung -- noch keine
    Diskussion gelaufen, oder das Profil hat ``diskussion.aktiv`` nie gesetzt
    -- kein Block. Die Gating-Entscheidung liegt damit allein in den Daten,
    nicht in einer zusaetzlichen ``workshop.diskussion_aktiv()``-Abfrage
    hier: ohne das Profil entsteht nie eine Zeile in ``diskussion_verdichtung``
    (Dortmund bleibt unberuehrt)."""
    text = repo.diskussion_verdichtung_text(conn, chat_id)
    if not text:
        return ""
    return f"{T.DISKUSSION_KOPF}\n\n{text}"


#: Die Kopfzeile des Begriffs-Blocks (Karte t_4517d4ad, 04.10.2026).
BEGRIFFE_DETAIL_KOPF = "Warum ihr diese Begriffe gewaehlt habt:"


#: Die Koepfe der zwei Bloecke vom 05.10.2026 (Birk, Nachtrag 5): das Board,
#: das die Gruppe auf dem zweiten Handy sieht, und der Wortlaut alles
#: Mitgehoerten. Der Satz zum Board traegt die Rahmung, die die
#: Systemanweisung nur noch einmal allgemein nennt.
BOARD_KOPF = (
    "Das CoThinker-Board -- die Begriffe, die die Gruppe live auf dem zweiten "
    "Handy sieht, nach Rang (die ersten fuenf sind als ihre Begriffe "
    "gespeichert). Bezieh dich darauf; Aenderungen (ein Begriff falsch "
    "verstanden, andere Reihenfolge, einer fehlt) nimmst du im Chat entgegen:"
)
_BOARD_ZEILE = "{nr}. {begriff}{favorit}{grund}"
_BOARD_FAVORIT = " (Favorit)"
_BOARD_GRUND = " -- {begruendung}"
MITGEHOERT_KOPF = (
    "Was die Gruppe gesagt hat, waehrend du mitgehoert hast (Diskussion/"
    "Brainstorm, aelteste zuerst, sehr Altes kann fehlen):"
)
_MITGEHOERT_DISKUSSION = "[Diskussion]"
_MITGEHOERT_BRAINSTORM = "[Brainstorm]"
#: Steht im Verlauf statt "(sprache)" fuer eine Folge mitgehoerter Segmente
#: ohne eigenen Text -- ihr Wortlaut steht im Block oben.
_MARKE_MITGEHOERT = "{anzahl} mitgehoerte Sprachaufnahme(n), Wortlaut im Block oben"

#: Obergrenze des Mitgehoert-Blocks in Zeichen: das JUENGSTE bleibt, aeltere
#: Segmente fallen vorn weg. Padua 06.10.2026 (Birk 13:50): "das komplette
#: Rohtranskript aus Phase 4 soll in Phase 5" -- 6.000 Zeichen kappten schon
#: die Phase-1-Diskussion (gemessen 10.900-22.200 Zeichen je Gruppe), ein
#: Brainstorm haette den Rest verdraengt. 60.000 Zeichen (~15k Token) passen
#: ab Phase 4 locker ins Opus-Budget (``OPUS_ZEICHEN_GRENZE_VORGABE``); fuer
#: kleinere Budgets greift weiter die Kuerzungsleiter (``_zu_lang``, aelteste
#: Zeile zuerst). Ueber ``IT_MITGEHOERT_ZEICHEN`` ohne Neustart umstellbar.
MITGEHOERT_ZEICHEN = 60_000


def mitgehoert_zeichen() -> int:
    """Die geltende Obergrenze des Mitgehoert-Blocks (Umgebung schlaegt
    Vorgabe; liest ``MITGEHOERT_ZEICHEN`` zur Laufzeit, damit Tests es
    weiter per monkeypatch setzen koennen)."""
    return _aus_umgebung("IT_MITGEHOERT_ZEICHEN", MITGEHOERT_ZEICHEN, 1_000)


def _baue_board(conn, chat_id: int) -> str:
    """Das Begriffsboard (alle nicht verworfenen Begriffe nach Rang, mit
    Favorit-Marke und Begruendung) -- in JEDER Phase, sobald es eins gibt
    (05.10.2026, Birk: "auch das, was im CoThinker steht"). Live hatte der
    Bot in Phase 1 geantwortet, er sehe die CoThinker-Seite nicht.
    Datengetrieben: ohne Board (Dortmund, nie mitgehoert) kein Block."""
    from interview_theater import begriffsboard

    board = [e for e in begriffsboard.sortiert(begriffsboard.aktuelles(conn, chat_id))
             if e.get("status") != "verworfen"]
    if not board:
        return ""
    zeilen = [
        T._BOARD_ZEILE.format(
            nr=nr, begriff=e["begriff"],
            favorit=T._BOARD_FAVORIT if e.get("status") == "favorit" else "",
            grund=(T._BOARD_GRUND.format(begruendung=e["begruendung"])
                   if (e.get("begruendung") or "").strip() else ""),
        )
        for nr, e in enumerate(board, 1)
    ]
    return T.BOARD_KOPF + "\n" + "\n".join(zeilen)


def _baue_mitgehoert(conn, chat_id: int) -> str:
    """Der Wortlaut alles Mitgehoerten (Diskussion Phase 1, Brainstorm
    Phase 4), chronologisch -- bei Platznot faellt das AELTESTE vorn weg
    (``MITGEHOERT_ZEICHEN``). Bis 05.10.2026 stand ein Segment im Verlauf
    nur als "(sprache)" ohne Text (``nachricht.text`` bleibt dort NULL,
    ``unterdrueckt`` betrifft nur die Chatanzeige), und der Bot sagte live,
    er bekomme nur den Marker einer Sprachaufnahme. Datengetrieben."""
    zeilen = []
    for row in repo.mitgehoerte_transkripte(conn, chat_id):
        marke = T._MITGEHOERT_DISKUSSION if row["diskussion"] else T._MITGEHOERT_BRAINSTORM
        zeilen.append(f"{marke} {row['transkript'].strip()}")
    grenze = mitgehoert_zeichen()
    behalten, laenge = [], 0
    for zeile in reversed(zeilen):
        if behalten and laenge + len(zeile) + 1 > grenze:
            break
        behalten.insert(0, zeile)
        laenge += len(zeile) + 1
    if not behalten:
        return ""
    return T.MITGEHOERT_KOPF + "\n" + "\n".join(behalten)


def _fasse_marker_zusammen(fenster_eintraege: list) -> None:
    """Ersetzt im Verlauf jede Folge von "(sprache)"-Zeilen ohne Text durch
    EINE Zeile mit ``_MARKE_MITGEHOERT`` -- an Ort und Stelle, damit die
    Kuerzungsleiter dieselbe Liste sieht. Nur gerufen, wenn der
    Mitgehoert-Block steht."""
    endung = ": (sprache)"
    neu, folge, sprecher = [], 0, None
    for eintrag in fenster_eintraege:
        if isinstance(eintrag, str) and eintrag.endswith(endung):
            folge += 1
            sprecher = eintrag[: -len(endung)]
            continue
        if folge:
            neu.append(f"{sprecher}: ({T._MARKE_MITGEHOERT.format(anzahl=folge)})")
            folge = 0
        neu.append(eintrag)
    if folge:
        neu.append(f"{sprecher}: ({T._MARKE_MITGEHOERT.format(anzahl=folge)})")
    fenster_eintraege[:] = neu


def _baue_begriffe_detail(conn, chat_id: int) -> str:
    """Begruendung und Doppelbedeutung je gespeichertem Begriff
    (``arbeitsstand.begriffe_detail``) -- nur das, was der Board-Block
    (``_baue_board``) NICHT schon zeigt (ein Fakt, eine Stelle). Der
    Board-Block zeigt je Begriff nur die Begruendung, nie die
    Doppelbedeutung -- ein Begriff, der dort steht, verliert hier also nur
    seine Begruendung, nie eine vorhandene Doppelbedeutung (MINOR 3, Review
    T3). Ganz fehlt ein Begriff hier nur, wenn er NICHTS Zusaetzliches
    traegt -- allem voran Begriffe, die das Board als "verworfen" fuehrt:
    ``_baue_board`` listet nur nicht verworfene Begriffe, aber eine Gruppe
    kann einen verworfenen trotzdem gespeichert haben -- ohne diesen Block
    verlor er seine Begruendung komplett (R-1).

    **In jeder Phase** (05.10.2026, Birk: "Der Chat muss immer alles
    wissen") -- bis zum 05.10.2026 lief das nur in Phase 2 und ab 4, nie in
    1 oder 3; seit das Board selbst in jeder Phase steht, gilt dieselbe
    Regel fuer die Begriffe, die es nicht zeigt. Nie das Zitat
    (``roadmap.begriffe_detail`` wirft es weg). Datengetrieben: ohne Detail
    (Dortmund) kein Block."""
    from interview_theater import begriffsboard, roadmap

    detail = roadmap.begriffe_detail(repo.hole_arbeitsstand(conn, chat_id))
    gezeigt = {
        begriffsboard.schluessel(e["begriff"])
        for e in begriffsboard.aktuelles(conn, chat_id)
        if e.get("status") != "verworfen"
    }
    bereinigt = []
    for eintrag in detail:
        if begriffsboard.schluessel(eintrag.get("begriff")) in gezeigt:
            if not (eintrag.get("doppelbedeutung") or "").strip():
                continue  # der Board-Block traegt alles, was dieser Eintrag hat
            eintrag = dict(eintrag, begruendung="")  # nur die Begruendung ist dort doppelt
        bereinigt.append(eintrag)
    zeilen = begriffsboard.detail_zeilen(bereinigt)
    if not zeilen:
        return ""
    return T.BEGRIFFE_DETAIL_KOPF + "\n" + "\n".join(zeilen)


#: Der Hinweisblock, mit dem der Bot einen Phasenwechsel zur Sprache bringt.
#:
#: Seit dem 05.09.2026 ist das ausdruecklich eine **Frage**, kein Angebot und
#: erst recht kein Wechsel (Birk, nach dem Probelauf): Datenstand ist nicht
#: Absicht -- eine fertige Verdichtung sagt nicht, ob noch drei Interviews
#: kommen. Der Bot fragt im Fluss, die Gruppe antwortet in einem Satz, und
#: der Erkenner liest daraus ``phase_setzen``. Der Bot selbst schaltet nie um.
_PHASENHINWEIS = (
    "Die Materiallage wuerde Phase {bezeichnung} hergeben. Frag im Fluss "
    "nach, ob die Gruppe schon dorthin will -- ein Satz, keine Ankuendigung "
    '("Kommen noch Interviews, oder gehen wir ans Kernthema?"). Du schaltest '
    "nicht selbst um; das tut die Antwort der Gruppe."
)


def _baue_phasenhinweis(conn, chat_id: int) -> str:
    """Der Hinweis auf eine moegliche naechste Phase -- hoechstens einmal je
    Stufe (interview_theater/phasen.py).

    Die einzige Stelle im Kontextaufbau, die schreibt: ``phase_angeboten``
    merkt sich, welcher Wechsel schon im Prompt stand. Ohne dieses Feld
    stuende der Block in jedem Zug erneut da, und der Bot fragte alle zwei
    Minuten dasselbe -- aus einer Frage wuerde Draengeln. Antwortet die
    Gruppe, aendert sich die Phase, und beim naechsten erreichbaren Schritt
    gibt es eine neue Frage; antwortet sie nicht, bleibt es still.

    **Nie in Phase 1** (P1-L1, Prompt-Check Padua P1/P2, 05.10.2026): dort
    widersprach die Aufforderung "Ask ... whether the group wants to go
    there yet" der Phase-1-Regel "Don't ask what comes next"
    (``workshop/padua-2026/prompts/phasen/1.md``) -- und die Abschluss-
    nachricht nach "Discussion done" fragt ohnehin schon "Shall we move
    on?" mit zwei Knoepfen (``knoepfe/basis.biete_board_gespeichert``).
    Kein Merkposten wird hier gesetzt: ``offenes_angebot`` bleibt
    unverbraucht, falls ein anderer Kanal (``knoepfe.biete_phase_proaktiv``)
    das Angebot ausspricht."""
    if phasen.aktuelle(conn, chat_id) == 1:
        return ""
    stufe = phasen.offenes_angebot(conn, chat_id)
    if stufe is None:
        return ""
    # Padua Phasen TEIL 2, Abschlussreview (Fix-Runde 2): die zwei
    # Uebergaenge, die Paduas Zustandsmaschine selbst vollzieht (5->6,
    # 6->7), fragt auch der Prompt nicht an -- dieselbe Wache wie beim
    # proaktiven Angebot (``knoepfe.stationen._springt_selbst``). Ohne den
    # Schalter (Dortmund) immer False.
    from interview_theater.knoepfe import stationen

    if stationen._springt_selbst(conn, chat_id, stufe):
        return ""
    phasen.merke_angebot(conn, chat_id, stufe)
    return T._PHASENHINWEIS.format(bezeichnung=phasen.bezeichnung(stufe))


#: Der Hinweisblock, mit dem der Bot die Interview-Zuordnung einer Figur zur
#: Sprache bringt (05.09.2026, Birk: "Zitate als Few-Shots fuer die
#: Sprechweise je Figur, das ist das Wichtigste").
#:
#: Eine **Frage im Fluss**, kein Formular -- dieselbe Form wie der
#: Phasenhinweis: der Bot schlaegt vor, die Gruppe entscheidet, und erst ihre
#: Antwort loest den Sprachprofil-Aufruf aus (Erkenner-art
#: ``figur_quelle_setzen``). Der Code raet die Zuordnung nie selbst: welche
#: Figur aus wessen Erzaehlung spricht, kann kein Namensvergleich
#: beantworten.
_FIGURENHINWEIS = (
    "Diesen Figuren fehlt noch das Interview, aus dem sie spricht: {namen}. "
    "Wenn es passt, EIN Satz dazu, hoechstens: '<Figurenname> koennte wie "
    "<Interviewname> sprechen -- passt das?' Kein Zitat, keine Begruendung, "
    "keine Erklaerung, wozu die Zuordnung gut ist, und nichts wiederholen, "
    "was schon gesagt oder notiert wurde (Birk, 05.09. abends: die Zuordnung "
    "war zu langatmig). Nur Figurennamen aus der Liste oben und Interviewnamen "
    "aus den Verdichtungen. Sagt die Gruppe, eine Figur sei frei erfunden, "
    "frag fuer sie nicht mehr. Ein Interview darf mehrere Figuren speisen."
)


def _baue_figurenhinweis(conn, chat_id: int) -> str:
    """Der Hinweis auf Figuren ohne Quelle-Interview -- datengetrieben wie
    alles andere: weg, sobald jede Figur eine hat.

    Anders als der Phasenhinweis **ohne Merkposten**: hier verschwindet die
    Frage von selbst, sobald die Gruppe geantwortet hat, weil dann die Quelle
    gesetzt ist. Ein zweites Feld waere ein Merkposten fuer etwas, das die
    Daten schon sagen -- und wuerde die Frage fuer eine spaeter angelegte
    Figur mitverschlucken.

    Nur, wenn es ueberhaupt ein Interview gibt: ohne Material ist die Frage
    unbeantwortbar, und der Bot soll nicht nach etwas fragen, das die Gruppe
    noch gar nicht aufgenommen hat."""
    # Und erst ab der Schaerfung (Phase 6): in 4 und 5 wird erfunden, die
    # Frage nach dem Interview einer Figur waere dort genau die Ruecklenkung
    # aufs Material, die der Umbau vermeiden soll.
    if not kernpaket_erlaubt(conn, chat_id):
        return ""
    ohne = [f["name"] for f in repo.figuren(conn, chat_id) if f["quelle_aufnahme_id"] is None]
    if not ohne:
        return ""
    if not any(a["klasse"] == "lang" for a in repo.transkripte(conn, chat_id)):
        return ""
    return T._FIGURENHINWEIS.format(namen=", ".join(ohne))


#: **Deckel des Szenenblocks in Zeichen** (Audit 06.09.2026, Befund C.4,
#: Auftrag 3). Der Szenenblock war der einzige unbegrenzte Wachstumspfad im
#: Gespraechs-Prompt: ``_baue_szene`` nahm ``szene["volltext"]`` wie er ist,
#: und die Kuerzung nahm ihn ausdruecklich aus. Gemessen blieb der Prompt bei
#: einer zwanzigfachen Szene nach *vollstaendiger* Kuerzung -- Fenster,
#: Journal und Verdichtungen restlos geopfert -- bei 105.988 Zeichen, also
#: 4,4x ueber der Grenze.
#:
#: Der Szenenpfad kennt diesen Deckel laengst (``szene.CONTINUITY_ZEICHEN_MAX``,
#: ``szene._gekuerzter_volltext``); der Gespraechspfad hatte ihn nicht.
#: hermes-agent nennt dieselbe Lektion ausdruecklich: ein geschuetzter Block
#: ohne Deckel laesst das Budget nicht binden (``LEAN_TAIL_CAP_TOKENS``).
#:
#: 6.000 Zeichen sind rund 2.000 Token nach unserer Schaetzung -- etwas mehr,
#: als § 6.2 Block 5 mit 1.500 Token vorsieht, und genug fuer eine
#: ausgewachsene Szene (gemessen: die laengste Szene der Testgruppe hat
#: 5.349 Zeichen und bleibt damit ungekuerzt).
SZENE_ZEICHEN_MAX = 6_000

#: Worauf der Szenenblock in der Kuerzung faellt, bevor Journal und
#: Verdichtungen geopfert werden (Stufe 2 der Leiter in ``baue``).
SZENE_ZEICHEN_NOTFALL = 2_000

#: Wie viel vom Deckel auf den Anfang der Szene entfaellt. Anfang UND Schluss,
#: weil beide etwas anderes tragen: der Anfang die Exposition (wer, wo,
#: worum), der Schluss den Stand, an dem die Gruppe gerade arbeitet. Ein rein
#: hinten abgeschnittener Text saehe fuer das Modell aus wie eine Szene, die
#: mittendrin anfaengt -- deshalb die Auslassungsmarke dazwischen.
_SZENE_ANTEIL_ANFANG = 0.4

_TEXT_SZENE_GEKUERZT = "[... Mittelteil der Szene ausgelassen ...]"


def _gekuerzte_szene(volltext: str, grenze: int) -> str:
    """Anfang + Schluss einer zu langen Szene, mit Auslassungsmarke dazwischen.

    Geschnitten wird an Zeilengrenzen (dieselbe Ueberlegung wie in
    ``szene._gekuerzter_volltext``, das im Szenenpfad nur den Schluss
    behaelt): eine Szene besteht aus Sprecherzeilen, und eine halbe
    Sprecherzeile ist schlechter zu lesen als eine fehlende.

    Die Marke steht IMMER drin, wenn gekuerzt wurde -- ein stillschweigend
    zusammengeschobener Text waere fuer das Modell ein Widerspruch zwischen
    Szenentitel und Inhalt, den es selbst aufzuloesen versuchte."""
    text = volltext.strip()
    if len(text) <= grenze:
        return text
    marke = T._TEXT_SZENE_GEKUERZT
    platz = max(0, grenze - len(marke) - 2)
    kopf_max = int(platz * _SZENE_ANTEIL_ANFANG)
    schluss_max = platz - kopf_max
    zeilen = text.splitlines()

    kopf: list[str] = []
    gezaehlt = 0
    for zeile in zeilen:
        if gezaehlt + len(zeile) + 1 > kopf_max:
            break
        kopf.append(zeile)
        gezaehlt += len(zeile) + 1

    schluss: list[str] = []
    gezaehlt = 0
    for zeile in reversed(zeilen[len(kopf):]):
        if gezaehlt + len(zeile) + 1 > schluss_max:
            break
        schluss.insert(0, zeile)
        gezaehlt += len(zeile) + 1

    if not kopf and not schluss:
        # Eine einzige, sehr lange Zeile: dann eben hart an Zeichen, sonst
        # bliebe vom Szenenblock nur die Marke.
        return f"{text[:kopf_max]}\n{marke}\n{text[len(text) - schluss_max:]}"
    teile = kopf + [marke] + schluss
    return "\n".join(teile)


def _baue_szene(conn, chat_id: int, grenze: int | None = None) -> str:
    """Block 5: die EINE zuletzt geaenderte Szene im Volltext (SPEC § 6.2).

    Datengetrieben wie alle Bloecke, ohne gespeicherten Zustand: woran die
    Gruppe zuletzt gearbeitet hat, ist die Szene, um die es gerade geht --
    springt sie zu einer frueheren zurueck und ueberarbeitet sie, wandert
    diese automatisch hierher (repo.aktualisiere_szene setzt geaendert_am
    neu).

    ``grenze`` deckelt den Volltext (Vorgabe ``SZENE_ZEICHEN_MAX``): darueber
    stehen Anfang und Schluss mit einer Auslassungsmarke dazwischen. Der
    Kopfzeile (Titel, Nummer) passiert nie etwas -- das Modell soll auch bei
    einer gekuerzten Szene wissen, um welche es geht."""
    szene = repo.hole_letzte_szene(conn, chat_id)
    if szene is None or not szene["volltext"]:
        return ""
    grenze = SZENE_ZEICHEN_MAX if grenze is None else grenze
    volltext = _gekuerzte_szene(szene["volltext"], grenze)
    return T._TEXT_AKTUELLE_SZENE.format(szene=szenenzeile(szene), volltext=volltext)


#: Wie viele Journaleintraege in den Prompt gehen -- die letzten N nach
#: Dedupe (Audit-Befund G3, 06.09.2026). Das Journal ist nur-anhaengend und
#: waechst ueber zwei Workshoptage auf Dutzende Zeilen; gemessen standen am
#: 06.09. 15 Zeilen im Prompt, davon "Szene 1 geschrieben: ..." VIERMAL und
#: vier Figurenzeilen mit demselben "basierend auf Interview 1"-Anhang. Ein
#: Modell liest vierfache Wiederholung als Betonung -- es hielt die eine
#: geschriebene Szene fuer vier.
JOURNAL_EINTRAEGE = 8


def _baue_journal(conn, chat_id: int) -> str:
    """Die letzten JOURNAL_EINTRAEGE Journalzeilen, ohne Dubletten.

    **Dedupe vor Kuerzung**: erst fliegen textgleiche Eintraege raus (der
    juengste bleibt, weil er den aktuellen Stand traegt), dann werden die
    letzten N genommen. Andersherum wuerden acht Dubletten acht Plaetze
    besetzen und alles Aeltere verdraengen.

    Das Journal in der Datenbank bleibt unangetastet -- dort steht die volle
    Geschichte, und ein Journal wird nur angehaengt, nie umgeschrieben
    (AGENTS.md). Gekuerzt wird nur die Sicht des Modells."""
    eintraege = repo.journal(conn, chat_id)
    if not eintraege:
        return ""
    # Von hinten durchgehen: der juengste Eintrag eines Textes gewinnt.
    gesehen: set[tuple[str, str]] = set()
    behalten = []
    for e in reversed(eintraege):
        schluessel = (e["art"], (e["text"] or "").strip())
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        behalten.append(e)
    behalten = list(reversed(behalten))[-JOURNAL_EINTRAEGE:]
    zeilen = [journalzeile(e) for e in behalten]
    return T._JOURNAL_KOPF + "\n".join(zeilen)


def journalzeile(eintrag) -> str:
    """Eine Journalzeile im Nutzertext: ``- [<Art>] <Text>`` -- die eine
    Stelle fuer Gespraechs-Prompt und Journal-Extraktor."""
    art = T.JOURNALART_BESCHRIFTUNG.get(eintrag["art"], eintrag["art"])
    return f"- [{art}] {eintrag['text']}"


#: Obergrenze fuer den Nachrichtenpool, aus dem das Fenster gebaut wird --
#: eine reine Performance-Vorkehrung (niemand soll fuer jeden Zug den
#: gesamten Zweitagesverlauf aus der DB laden), kein Budget im Sinne von
#: BUDGETS["fenster"].
_FENSTER_POOL = 1000

#: Wie viele Nachrichten hoechstens ins Fenster kommen (06.09.2026, Birk,
#: gemessen an der Testgruppe um 00:33: der Nutzertext hatte **52 000
#: Zeichen**, und darin standen 700 Zeilen bis in den Vormittag zurueck).
#:
#: Seit dem Audit vom 06.09.2026 (Auftrag 2) ist das die **Obergrenze**, nicht
#: mehr das primaere Mass -- das ist ``FENSTER_ZEICHEN``. Zwanzig ist die
#: Zahl, die eine laufende Arbeitsphase abdeckt, ohne den Vormittag
#: mitzuschleppen. Alles Aeltere, das wirklich zaehlt, steht ohnehin
#: strukturiert im Prompt: Arbeitsstand, Journal, Figuren, Verdichtungen. Das
#: Fenster ist fuer den Ton und den letzten Faden da, nicht als Archiv.
FENSTER_NACHRICHTEN = 20

#: **Das primaere Mass des Fensters, in ZEICHEN** (Audit 06.09.2026,
#: Auftrag 2; SPEC § 6.2 Block 7: *"in Token statt Nachrichten bemessen -- im
#: Gruppenchat koennen 'N Nachrichten' vier Redebeitraege oder vierzig
#: Sekunden Geplaenkel sein"*).
#:
#: 12.000 Zeichen sind nach ``schaetze`` rund 4.000 Token. Die Zahl ist die
#: Haelfte der harten Koerpergrenze (``ZEICHEN_GRENZE_VORGABE`` = 24.000):
#: das Fenster ist der groesste veraenderliche Block, und es soll den Prompt
#: nicht allein reissen koennen, aber auch nicht so klein sein, dass der
#: letzte Faden abreisst.
#:
#: Zeichen und nicht Token, aus demselben Grund wie bei der Zeichengrenze
#: (§ 7.1): wir haben keinen Tokenizer, und die Groesse, die wir ohne einen
#: sicher pruefen koennen, ist die Zeichenzahl. hermes-agent hat dieselbe
#: Entscheidung in dieselbe Richtung getroffen -- *"Token-budget tail
#: protection instead of fixed message count"* (``context_compressor.py:13``).
FENSTER_ZEICHEN = 12_000

#: Und zeitlich: was laenger als das her ist, gehoert nicht mehr zur
#: laufenden Unterhaltung. Seit dem Audit (Auftrag 2) ist das eine **weiche**
#: Grenze -- sie wird von ``FENSTER_MIN_NACHRICHTEN`` unterlaufen.
#:
#: Der Anlass ist gemessen (05.09.2026, 21:50): weil der Vormittag mit im
#: Fenster stand -- und wegen der falschen Sortierung sogar OBEN --, hielt
#: das Modell ihn fuer die Gegenwart und antwortete in Phase 6 mit "Das ist
#: Tag 1 und wir stehen erst am Anfang. Also: Rassismus, Liebe, Spaß,
#: Streit."
FENSTER_MINUTEN = 30

#: **Die Untergrenze: so viele Nachrichten bleiben IMMER im Fenster**, auch
#: wenn sie aelter als ``FENSTER_MINUTEN`` sind (Audit 06.09.2026, Befund
#: C.2, Auftrag 2).
#:
#: Gemessen an der Test-DB: der Ausloeser lag um 23:56, die zwanzig
#: Kandidaten zwischen 21:53 und 22:32 -- die 30-Minuten-Grenze schnitt
#: **alle zwanzig** weg, und der Bot antwortete ohne einen einzigen Satz
#: Gespraechsverlauf. Das ist nach jeder Pause ueber 30 Minuten der Fall:
#: Mittagspause, Nacht, Ortswechsel, Probe.
#:
#: Damit funktioniert auch die Pausenmarkierung aus § 6.2 wieder wie
#: vorgesehen: ``[Pause: 18 Stunden]`` kann nur erscheinen, wenn das, was vor
#: der Pause lag, ueberhaupt noch im Fenster steht. Die Zeitgrenze bemisst,
#: **wie viel** von vorher mitgeht -- nicht mehr, **ob**.
FENSTER_MIN_NACHRICHTEN = 6


def fenster_grenzen() -> dict:
    """**Die eine Quelle der Fenstergrenzen** (Audit 06.09.2026, Befund C.3).

    Gelesen von ``_baue_fenster_eintraege`` (die den Prompt baut) UND von
    ``journal.berechne_verdraengten_abschnitt`` (die ausrechnet, was aus
    genau diesem Fenster gefallen ist). Vorher standen die beiden Zahlen
    nebeneinander statt voneinander abgeleitet: der Extraktor rechnete gegen
    ``BUDGETS["fenster"] = 8000`` Token, waehrend das reale Fenster seit dem
    Fensterumbau 20 Nachrichten / 30 Minuten war. Gemessen hielt er damit
    **31 Nachrichten fuer "noch im Fenster"**, waehrend der Prompt nur 20 sah
    -- ein Loch von elf Nachrichten breit, das mit jedem Zug mitwanderte und
    dessen Inhalt nie journalisiert wurde und danach nirgends mehr stand.

    Eine Funktion und keine Konstante, aus demselben Grund wie bei
    ``zeichengrenze()``: sie wird bei jedem Aufruf gelesen, damit der
    Simulator (``scripts/simulation.py --fenster-klein``) und ein Test die
    Werte zur Laufzeit setzen koennen und **beide** Leser dieselbe Aenderung
    sehen. hermes-agent leitet die zweite Schwelle genauso aus der ersten ab
    (``native_compaction``: *"clamped safely below the local compressor's
    trigger"*), statt sie danebenzusetzen.
    """
    return {
        "zeichen": FENSTER_ZEICHEN,
        "nachrichten": FENSTER_NACHRICHTEN,
        "minuten": FENSTER_MINUTEN,
        "min_nachrichten": FENSTER_MIN_NACHRICHTEN,
    }


def waehle_fenster(nachrichten: list, bezug=None, namen: dict[str, str] | None = None) -> list:
    """Waehlt aus einer chronologisch aufsteigenden Liste die Nachrichten,
    die ins Fenster gehoeren -- **die eine Auswahlregel**, die sowohl der
    Promptbau als auch die Verdraengungsrechnung benutzt.

    Die Regel, in der Reihenfolge ihrer Anwendung:

    1. Hoechstens ``FENSTER_NACHRICHTEN`` (Obergrenze, von hinten).
    2. Von hinten auffuellen, bis ``FENSTER_ZEICHEN`` voll ist -- das
       **primaere** Mass (§ 6.2 Block 7). Die juengste Nachricht gehoert
       immer dazu, auch wenn sie das Budget allein sprengt: ein Fenster ist
       nie leer.
    3. ``FENSTER_MINUTEN`` als **weiche** Grenze gegen ``bezug`` (die
       ausloesende Nachricht, sonst die juengste im Fenster) -- aber nie
       unter ``FENSTER_MIN_NACHRICHTEN``.

    ``bezug`` ist ein ISO-Zeitstempel oder None. Ohne ``gesendet_am`` in den
    Nachrichten (die Verdraengungsrechnung arbeitet auf Rohdicts aus Tests
    ohne Zeitfeld) entfaellt Schritt 3 stillschweigend -- Zeichen- und
    Nachrichtengrenze tragen dann allein.

    ``namen`` (E8): dieselben Pseudonyme wie im Prompt, damit das Fenster
    genau an der Stelle schneidet, an der es misst.
    """
    if not nachrichten:
        return []
    grenzen = fenster_grenzen()

    kandidaten = nachrichten[-grenzen["nachrichten"]:]

    # Schritt 2: von hinten auffuellen. Die juengste ist gesetzt.
    kumuliert = len(sprecherzeile(kandidaten[-1], namen, gesprochen_markieren=True))
    beginnt_bei = len(kandidaten) - 1
    for index in range(len(kandidaten) - 2, -1, -1):
        groesse = len(sprecherzeile(kandidaten[index], namen, gesprochen_markieren=True)) + 1  # +1 Zeilenumbruch
        if kumuliert + groesse > grenzen["zeichen"]:
            break
        kumuliert += groesse
        beginnt_bei = index
    kandidaten = kandidaten[beginnt_bei:]

    # Schritt 3: die weiche Zeitgrenze, mit Untergrenze.
    try:
        zeiten = [n["gesendet_am"] for n in kandidaten]
    except (KeyError, IndexError):
        return kandidaten
    if any(z is None for z in zeiten):
        return kandidaten
    bezugszeit = datetime.fromisoformat(bezug) if bezug else datetime.fromisoformat(
        max(zeiten)
    )
    schwelle = bezugszeit - timedelta(minutes=grenzen["minuten"])
    im_zeitfenster = [
        n for n in kandidaten
        if datetime.fromisoformat(n["gesendet_am"]) >= schwelle
    ]
    # **Nie leer, nie unter der Untergrenze** (Befund C.2). Die Zeitgrenze
    # darf kuerzen, aber nicht abschneiden: nach einer Nacht sieht der Bot
    # sonst beim ersten Zug danach keinen Verlauf und die Pausenzeile, die
    # genau diesen Fall benennen soll, kann nie erscheinen.
    if len(im_zeitfenster) < grenzen["min_nachrichten"]:
        return kandidaten[-grenzen["min_nachrichten"]:]
    return im_zeitfenster


#: Systemzeilen, die nicht ins Fenster gehoeren (06.09.2026). Sie sind
#: Ereignisse, keine Gespraechsbeitraege: was sie festhalten, steht im
#: Journal und im Arbeitsstand, und im Fenster stiften sie nur Verwirrung --
#: am Testabend stand "Bin wieder da" zweimal darin, und das Modell erzaehlte
#: die Notiert-Zeilen nach, statt weiterzuarbeiten.
_SYSTEMANFAENGE = (
    "Bin wieder da.",
    "Notiert:",
    "Aufnahme laeuft.",
    "Aufnahme beendet.",
    "Bereit -",
    "Hinweis: Den Szenentext",
    "Ich schreibe die Szene aus",
    "Ich schreibe gerade noch",
    "Ich werte die offenen Interviews aus",
    "Entfernt:",
)

#: Dieselben Systemzeilen in ihrer englischen Fassung (Karte A1, Aufgabe 24)
#: -- je ein Anfang eines Eintrags aus ``sprachen/en/texte.toml``; ein Test
#: haelt die Rundreise fest. Gelesen wird die Vereinigung beider Tabellen:
#: der Bot erkennt seine eigenen Zeilen, gleich in welcher Sprache sie
#: stehen. "Aufnahme laeuft." hat kein Gegenstueck -- der deutsche Text
#: existiert im Code nicht mehr, der Eintrag oben ist ein Altbestand fuer
#: alte Chatverlaeufe. "Withdrawn:" ist der Anfang von
#: ``erkenner._JOURNAL_ZURUECK``.
#:
#: **Erweitert 05.10.2026 (P1-L6, Prompt-Check Padua P1/P2):** fuenf weitere
#: Bot-Meldungen standen im Fenster als "You:"-Zug, obwohl sie Ereignisse
#: sind -- ``_TEXT_UNDO_ERLEDIGT``/``_TEXT_REDO_ERLEDIGT`` ("Undone:"/
#: "Redone:"), ``_ANTWORT_UNDO_GEAENDERT``/``_ANTWORT_REDO_GEAENDERT``
#: ("Changed since."), ``erkenner._ZEILE_FESTGELEGT`` ("📌 Agreed:") und
#: ``_TEXT_FRAGE_GESCHAERFT`` ("Question reworked").
#:
#: **NICHT** "Question " als Praefix (Review T3, IMPORTANT 2): das verschluckte
#: echte Modellsaetze wie "Question 2 is strong, but ..." komplett. Die
#: Fragenkarte selbst (``_TEXT_FRAGE_KOPF``/``_TEXT_FRAGE_KOPF_OHNE_BEGRIFF``,
#: "Question N/M ...") ist kein Praefix-Treffer hier, sondern eine eigene,
#: engere Regel (``_FRAGENKOPF_MUSTER``/``_ohne_fragenkopf``): nur ihr Kopf
#: faellt weg, nicht die Frage darunter (MINOR 1) -- die ganze Nachricht zu
#: verschlucken waere Inhalt, nicht nur Ereignis.
_SYSTEMANFAENGE_EN = (
    "I'm back.",
    "Noted:",
    "Recording stopped.",
    "Ready -",
    "Note: the scene text",
    "I'm writing out the scene",
    "I'm still writing",
    "I'm analysing the open interviews",
    "Removed:",
    "Withdrawn:",
    "Undone:",
    "Redone:",
    "Changed since.",
    "📌 ",
    "Question reworked",
)


def _ist_systemzeile(n) -> bool:
    """Ist diese Bot-Nachricht eine Systemmeldung und kein Gespraechsbeitrag?

    Nur Bot-Nachrichten: eine Gruppe, die zufaellig "Notiert:" tippt, sagt
    damit etwas -- und was die Gruppe sagt, faellt hier nie weg."""
    if not n["ist_bot"]:
        return False
    text = (n["text"] or "").lstrip()
    return any(text.startswith(anfang)
               for anfang in _SYSTEMANFAENGE + _SYSTEMANFAENGE_EN)


#: Der Kopf der Fragenkarte ("Question 2/5 · Home" oder kopflos "Question
#: 1/1", ``knoepfe/fragen.py:_zeige_frage``) plus die Leerzeile direkt
#: danach -- Review T3, MINOR 1. Verlangt Ziffer/Ziffer direkt hinter
#: "Question ", damit ein echter Modellsatz ("Question 2 is strong, but
#: ...") nicht anschlaegt (IMPORTANT 2); verlangt die Leerzeile DAHINTER,
#: damit ein Kopf ohne Frage (sollte nie vorkommen) nicht versehentlich den
#: ganzen Text wegfrisst.
_FRAGENKOPF_MUSTER = re.compile(
    r"^(?P<praefix>.*?: )Question \d+/\d+(?: · [^\n]*)?\n\n", re.DOTALL,
)


def _ohne_fragenkopf(zeilen: list[str]) -> None:
    """Nimmt einer formatierten Fensterzeile ("Du: Question 2/5 · Home\\n\\n
    <Frage>") nur den Kartenkopf -- die Frage darunter bleibt, sie ist der
    Inhalt, auf den sich die Gruppe gerade bezieht, nicht das Ereignis. Die
    Nummerierung selbst ist redundant (die Werkbank zeigt den Fortschritt
    schon). Aendert ``zeilen`` an Ort und Stelle, wie ``_fasse_marker_zusammen``."""
    for i, zeile in enumerate(zeilen):
        zeilen[i] = _FRAGENKOPF_MUSTER.sub(r"\g<praefix>", zeile, count=1)


def _baue_fenster_eintraege(conn, chat_id: int, ausloeser, namen=None) -> list[str]:
    """Liefert die Eintraege des kurzen Fensters (Nachrichtenzeilen und
    Pausenmarkierungen), **aeltester zuerst** -- nach den Grenzen aus
    ``fenster_grenzen()`` (primaer ``FENSTER_ZEICHEN``, Obergrenze
    ``FENSTER_NACHRICHTEN``, weiche Zeitgrenze ``FENSTER_MINUTEN`` mit
    Untergrenze ``FENSTER_MIN_NACHRICHTEN``), ohne Systemzeilen.

    Die Auswahlregel selbst steht in ``waehle_fenster()`` -- **dieselbe
    Funktion**, die ``journal.berechne_verdraengten_abschnitt`` benutzt, um
    auszurechnen, was aus diesem Fenster gefallen ist (Audit-Befund C.3: die
    beiden liefen auseinander, weil sie zwei Zahlen nebeneinander hatten).

    **Warum das am 06.09.2026 umgebaut wurde.** Gemessen an der Testgruppe:
    der Nutzertext eines Zuges war 52 000 Zeichen lang, das Fenster reichte
    700 Zeilen bis in den Vormittag zurueck -- und es stand **rueckwaerts**
    darin. Der Grund fuer die Reihenfolge war eine falsche
    Sortierannahme: ``repo.letzte_nachrichten`` ordnet nach ``message_id``,
    und eine uebernommene Gruppenhistorie traegt **negative, absteigend
    vergebene** ids. Aufsteigend sortiert stehen die aeltesten dieser
    Nachrichten damit zuletzt und die juengsten zuerst. Sortiert wird deshalb
    hier nach ``gesendet_am``: die Uhrzeit luegt nicht.

    Die Folge des alten Verhaltens ist belegt (05.09.2026, 21:50): das Modell
    hielt den Vormittag fuer die Gegenwart und bot in Phase 6 an, aus den
    Begriffen Interviewfragen zu entwickeln.

    Jeder Listeneintrag bleibt eine atomare Einheit (eine Pausenzeile oder
    eine einzelne Nachricht) -- Grundlage dafuer, dass die Kuerzung in
    ``baue()`` ganze Nachrichten abschneiden kann.

    ``namen``: die Pseudonyme aus ``baue()`` (E8); fehlen sie, holt die
    Funktion sie selbst -- die Messskripte rufen sie ohne."""
    if namen is None:
        namen = pseudonyme(conn, chat_id, ausloeser)
    ausloeser_ids = {n["message_id"] for n in ausloeser}
    roh = [
        n for n in repo.letzte_nachrichten(conn, chat_id, anzahl=_FENSTER_POOL)
        if n["message_id"] not in ausloeser_ids and not _ist_systemzeile(n)
    ]
    # Nach der Uhrzeit, nicht nach der id (siehe Docstring).
    roh.sort(key=lambda n: n["gesendet_am"])

    bezug = _bezugszeit(ausloeser)
    kandidaten = waehle_fenster(roh, bezug, namen)

    eintraege = []
    vorherige_zeit = None
    for n in kandidaten:
        if vorherige_zeit is not None:
            pause = _pausenzeile(vorherige_zeit, n["gesendet_am"])
            if pause:
                eintraege.append(pause)
        eintraege.append(sprecherzeile(n, namen, gesprochen_markieren=True))
        vorherige_zeit = n["gesendet_am"]
    # **Die Pause VOR dem Ausloeser** (06.09.2026, Auftrag 2). Der haeufigste
    # Fall einer langen Pause ist gerade der, in dem die erste Nachricht
    # danach den Zug ausloest: die Gruppe kommt am naechsten Morgen wieder.
    # Der Ausloeser steht in seinem eigenen Block, also faellt der Sprung
    # zwischen dem Fenster und ihm sonst durch -- das Modell saehe "gestern
    # Abend" und direkt darunter "Aktuell:", ohne Hinweis auf die Nacht
    # dazwischen. Genau dafuer hat § 6.2 die Pausenmarkierung erfunden; sie
    # konnte bis heute nie erscheinen, weil vor der Pause nichts mehr im
    # Fenster stand (Befund C.2).
    if vorherige_zeit is not None and bezug:
        pause = _pausenzeile(vorherige_zeit, bezug)
        if pause:
            eintraege.append(pause)
    _ohne_fragenkopf(eintraege)
    return eintraege


def _bezugszeit(ausloeser):
    """Der Bezugspunkt der weichen Zeitgrenze: die ausloesende Nachricht,
    sonst None (dann nimmt ``waehle_fenster`` die juengste im Fenster).
    Nicht ``jetzt``: ein Test und ein Nachlauf sollen dieselbe Antwort
    bekommen wie der Livezug."""
    zeiten = [n["gesendet_am"] for n in ausloeser]
    return max(zeiten) if zeiten else None


def _baue_ausloeser(ausloeser, namen: dict[str, str] | None = None) -> str:
    """Die ausloesende(n) Nachricht(en) -- ueberlebt jede Kuerzung (§ 7.2),
    darum von der Kuerzungslogik in baue() nie angefasst.

    Traegt das aktive Profil eine Sprachregel (``_AUSLOESER_SPRACHREGEL``,
    nur im englischen Profil belegt, siehe dort), steht sie als letzter
    Absatz dahinter -- Padua Hotfix Befund 3: eine Erinnerung direkt neben
    der zuletzt gelesenen Nachricht wiegt mehr als eine am Anfang des
    Systemprompts."""
    if not ausloeser:
        return ""
    zeilen = [sprecherzeile(n, namen, gesprochen_markieren=True) for n in ausloeser]
    text = T._AUSLOESER_KOPF + "\n".join(zeilen)
    regel = T._AUSLOESER_SPRACHREGEL
    if regel:
        text += "\n\n" + regel
    return text


def _zusammen(bloecke: dict) -> str:
    """Fuegt die nichtleeren Bloecke in der festen Reihenfolge zusammen."""
    return "\n\n".join(bloecke[k] for k in _REIHENFOLGE if bloecke.get(k))


#: Beim allerersten Zug einer Gruppe bekommt das Modell diese Anweisung an
#: den Anfang des Koerpers -- statt eines fest verdrahteten Begruessungstexts
#: (Birk 04.09. abends: "der Einstieg reagiert gar nicht auf das, was die
#: Leute als Allererstes sagen"). Der Inhalt (Mitlesen, Interviews, /hilfe,
#: Link) bleibt Pflicht, die Form entsteht aus der ersten Nachricht.
ERSTKONTAKT = (
    "{anlass} Geh zuerst auf das ein, was gerade gesagt "
    "wurde, und nimm dir dann Raum: das ist der Moment, in dem die Gruppe "
    "versteht, wie hier gearbeitet wird. Bring unter, in dieser Reihenfolge "
    "und in ganzen Saetzen, nicht als Liste: wer du bist und was ihr "
    "zusammen macht (aus den Begriffen der Gruppe entstehen Fragen, mit den "
    "Fragen zieht die Gruppe los und macht Interviews, aus den Interviews "
    "wird spaeter das Stueck); dass du alles mitliest und auf alles "
    "antwortest, getippt wie gesprochen; **dass ein Interview mit dem Knopf "
    "\"Interview starten\" beginnt und dass nach jeder Sprachnachricht ein "
    "Knopf fragt, ob es weitergeht oder fertig ist** -- die "
    "Knoepfe unter deiner Nachricht zeigen den Weg, **nenne keinen "
    "Schraegstrich-Befehl**{link}. "
    "**Schliesse mit der Frage nach den Begriffen**: die Gruppe hat im Raum "
    "Begriffe gesammelt -- bitte sie, dir diese Liste zu schicken, getippt "
    "oder als Sprachnachricht. Das ist der erste "
    "Arbeitsschritt, und die Begruessung endet damit. "
    "Kein Formular, keine Aufzaehlung mit Spiegelstrichen -- ein warmer, "
    "ausfuehrlicher Einstieg, der mit dem Gesagten anfaengt und mit der "
    "Bitte um die Begriffe aufhoert."
)

#: Der Anlass-Satz am Anfang von ``ERSTKONTAKT``. Dieselbe Anweisung traegt
#: seit dem 02.10.2026 (Birk, Padua) AUCH den Wiedereintritt in Phase 1
#: (``knoepfe.eintritt_in_phase``): "kein Grund, warum beim Zurueckspringen
#: der Einstieg anders sein sollte" -- statt Kopfzeile + festem Satz schreibt
#: das Modell denselben Einstieg. Nur der Anlass unterscheidet sich.
ERSTKONTAKT_ANLASS_ERSTE = (
    "Dies ist eure allererste Nachricht in dieser Gruppe -- deine Antwort ist "
    "zugleich die Begruessung."
)
ERSTKONTAKT_ANLASS_RUECKKEHR = (
    "Die Gruppe steigt gerade (wieder) in die Phase Begriffe ein -- deine "
    "Antwort ist der Einstieg in diese Phase, genau wie bei der Begruessung."
)

#: Der Satz zum Link, wenn eine Weboberflaeche konfiguriert ist.
ERSTKONTAKT_LINK = (
    "; und dass die Gruppe alles Festgehaltene unter {url} mitlesen kann "
    "(nur fuer diese Gruppe, den Link genau so nennen)"
)

#: Die Begruessungs-Anweisung, wenn das Profil ``diskussion.aktiv`` gesetzt
#: hat (Padua Phase 1+2 Umbau, 03.10.2026). ``ERSTKONTAKT`` selbst bleibt
#: byte-fuer-byte unveraendert -- das ist die Dortmund-Sicherheitsgarantie
#: dieses Umbaus, kein Nebeneffekt dieser Konstante. Gleicher Aufbau
#: (Rollen/Ablauf wie gewohnt erklaeren), aber ein anderer Schluss: statt
#: nach den fuenf Begriffen zu fragen, legt die Gruppe das Handy in die
#: Mitte und bespricht die Begriffe frei -- der Bot hoert nur zu und sagt
#: nichts, bis "Diskussion fertig" gedrueckt wird (siehe
#: ``interview_theater.diskussion``, Aufgabe 7).
ERSTKONTAKT_DISKUSSION = (
    "{anlass} Geh zuerst auf das ein, was gerade gesagt "
    "wurde, und nimm dir dann Raum: das ist der Moment, in dem die Gruppe "
    "versteht, wie hier gearbeitet wird. Bring unter, in dieser Reihenfolge "
    "und in ganzen Saetzen, nicht als Liste: wer du bist und was ihr "
    "zusammen macht (aus den Begriffen der Gruppe entstehen Fragen, mit den "
    "Fragen zieht die Gruppe los und macht Interviews, aus den Interviews "
    "wird spaeter das Stueck); dass du alles mitliest und auf alles "
    "antwortest, getippt wie gesprochen; **dass ein Interview mit dem Knopf "
    "\"Interview starten\" beginnt und dass nach jeder Sprachnachricht ein "
    "Knopf fragt, ob es weitergeht oder fertig ist** -- die "
    "Knoepfe unter deiner Nachricht zeigen den Weg, **nenne keinen "
    "Schraegstrich-Befehl**{link}. "
    "**Schliesse diesmal anders, nicht mit der Frage nach den Begriffen**: "
    "erklaer stattdessen, dass die Gruppe jetzt das Handy in die Mitte legt "
    "und frei bespricht, welche Begriffe ihr wichtig sind -- du hoerst dabei "
    "nur zu und sagst nichts, bis sie auf \"Diskussion fertig\" druecken. "
    "Darunter erscheint der Knopf \"Zuhoeren starten\", mit dem die "
    "Diskussion beginnt. "
    "Kein Formular, keine Aufzaehlung mit Spiegelstrichen -- ein warmer, "
    "ausfuehrlicher Einstieg, der mit dem Gesagten anfaengt und mit der "
    "Erklaerung zur Diskussion aufhoert."
)

#: Dieselben zwei Anlass-Saetze wie ``ERSTKONTAKT_ANLASS_ERSTE``/
#: ``_RUECKKEHR``, als eigene Konstanten: die Erstkontakt-Dreiergruppe bleibt
#: unangetastet, und ein spaeterer Unterschied im Diskussions-Anlass soll
#: nicht versehentlich den klassischen Text mitaendern.
ERSTKONTAKT_DISKUSSION_ANLASS_ERSTE = (
    "Dies ist eure allererste Nachricht in dieser Gruppe -- deine Antwort ist "
    "zugleich die Begruessung."
)
ERSTKONTAKT_DISKUSSION_ANLASS_RUECKKEHR = (
    "Die Gruppe steigt gerade (wieder) in die Phase Begriffe ein -- deine "
    "Antwort ist der Einstieg in diese Phase, genau wie bei der Begruessung."
)


def _baue_erstkontakt(conn, chat_id: int, e, rueckkehr: bool = False) -> str:
    # ueber bot.stelle_link_sicher, nicht ueber repo.gruppenseite_url direkt:
    # der Link muss in der Begruessung stehen, auch wenn die Gruppenzeile
    # gerade erst entsteht (05.09.2026).
    from interview_theater import bot

    url = bot.stelle_link_sicher(conn, e, chat_id)
    link = T.ERSTKONTAKT_LINK.format(url=url) if url else ""
    # Padua Phase 1+2 Umbau, 03.10.2026: nur bei aktivem Profil-Schalter
    # ("diskussion.aktiv") ein anderer Text -- ohne Profil (Dortmund) bleibt
    # dieser Zweig unbetreten und der bestehende Text unveraendert.
    if workshop.diskussion_aktiv():
        anlass = (
            T.ERSTKONTAKT_DISKUSSION_ANLASS_RUECKKEHR if rueckkehr
            else T.ERSTKONTAKT_DISKUSSION_ANLASS_ERSTE
        )
        # Birk, Live-Test 05.10.2026: die Phase-1-Begruessung mit Mithoeren
        # nennt die Gruppenseite nicht (wie ``bot.erstkontakt``) -- sie
        # endet mit "Start listening" fuer den Raumcheck.
        return T.ERSTKONTAKT_DISKUSSION.format(anlass=anlass, link="")
    anlass = T.ERSTKONTAKT_ANLASS_RUECKKEHR if rueckkehr else T.ERSTKONTAKT_ANLASS_ERSTE
    return T.ERSTKONTAKT.format(anlass=anlass, link=link)


def einstieg_begriffe(conn, chat_id: int, e) -> str:
    """Die Anweisung fuer den Einstieg in Phase 1 nach einem Phasenwechsel --
    wortgleich mit der Erstkontakt-Begruessung bis auf den Anlass-Satz."""
    return _baue_erstkontakt(conn, chat_id, e, rueckkehr=True)


#: Der Einstieg in Phase 4 (Padua-Brainstorming-Umbau, 02.10.2026), nach
#: demselben Muster wie ``ERSTKONTAKT``: eine Anweisung, kein fester Text --
#: das Modell schreibt den Einstieg selbst, in seinen eigenen Worten, und
#: traegt dabei fuenf Dinge, egal ob die Gruppe zum ersten Mal hier ist oder
#: zurueckkehrt ("kein Grund, warum beim Zurueckspringen der Einstieg anders
#: sein sollte", dieselbe Haltung wie bei Phase 1).
EINSTIEG_SETTING = (
    "Die Gruppe betritt gerade Phase 4 (Setting, Figuren & Geschichte) -- "
    "egal ob zum ersten Mal oder nach einer anderen Phase zurueck, schreib "
    "denselben Einstieg. Deine Antwort ist eine normale, in sich "
    "geschlossene Chat-Nachricht -- keine Ueberschrift, keine Liste mit "
    "Spiegelstrichen, kein Systemtext. Bring dabei unter, in fliessenden "
    "Saetzen und in deiner eigenen Formulierung:\n\n"
    "- Was jetzt dran ist: die Gruppe erfindet ihr Stueck jetzt selbst --\n"
    "  Setting, Figuren und Geschichte.\n"
    "- WARUM die Interviews hier bewusst nicht benutzt werden: zuerst die\n"
    "  eigene Erfindung, das Material schaerft sie erst in der naechsten\n"
    "  Phase (Schaerfung) -- und erfundene Figuren schuetzen zugleich die,\n"
    "  die interviewt wurden.\n"
    "- Die Themenbereiche als EINEN fliessenden Absatz, KEINE Fragenliste:\n"
    "  wo und wann es spielt und was die Leute zusammenbringt, wer\n"
    "  vorkommt und was sie wollen, worum es im Konflikt geht, wie es\n"
    "  ausgeht, und wie viele Szenen es werden sollen.\n"
    "- Dass alles, was entschieden wird, automatisch gespeichert wird und\n"
    "  im zweiten Tab \"Arbeitsstand\" sichtbar ist.\n"
    "- Schliess mit einer Einladung: sie koennen anfangen, wo sie wollen --\n"
    "  es gibt keine feste Reihenfolge.\n\n"
    "Keine Checkliste, keine Nummerierung in deiner Antwort selbst -- ein "
    "zusammenhaengender, einladender Text."
)


def einstieg_setting(conn, chat_id: int, e) -> str:
    """Die Anweisung fuer den Einstieg in Phase 4 -- Erst- und Wiedereintritt
    teilen sich dieselbe Anweisung, anders als bei Phase 1 (dort gibt es
    einen Anlass-Unterschied zur allerersten Nachricht ueberhaupt; Phase 4
    kennt dieses "allererste Mal" nicht)."""
    return T.EINSTIEG_SETTING


def umrisszeile(stand: dict) -> str:
    """Der Umriss als EINE Logzeile -- Blocknamen mit Token, Gesamt, gekuerzt.

    Bewusst keine Prompt-Inhalte: die Zeile geht ins Betriebslog, und dort
    haben weder Nachrichtentexte noch Transkripte etwas verloren (§ 11, und
    dieselbe Disziplin, mit der ``scripts/erzeuge_prompts.py`` entschaerft).
    Nur Zahlen, damit am Workshoptag jemand mitlesen kann, **was** im Prompt
    stand, ohne den Prompt selbst zu haben.

    Seit Auftrag 4 (Befund C.1) traegt der Umriss auch die Systemanweisung;
    ist sie gemessen, steht sie mit in der Zeile -- ``gesamt`` allein ist nur
    der Koerper, also der kleinere Teil des Prompts."""
    teile = " ".join(
        f"{name}={token}" for name, token in stand["bloecke"].items() if token
    )
    system = ""
    if stand.get("system"):
        system = (
            f"system={stand['system']} "
            f"gesamt_mit_system={stand['gesamt_mit_system']} "
        )
    return (
        f"kontext-umriss gesamt={stand['gesamt']} {system}"
        f"gekuerzt={'ja' if stand['gekuerzt'] else 'nein'} {teile}"
    )


def umriss(bloecke: dict, gekuerzt: bool = False, system_zeichen: int = 0) -> dict:
    """Welcher Block mit wie vielen geschaetzten Token im Prompt stand.

    Reine Buchhaltung ueber dem fertigen Ergebnis, ohne Einfluss darauf.
    Gebraucht wird sie vom Simulator: die Frage "was wird wann injiziert" --
    lag die Verdichtung ueberhaupt im Prompt, als der Bot danebengeantwortet
    hat? -- laesst sich sonst nur beantworten, indem man den ganzen Prompt
    mitschreibt, und der ist bei 20.000 Token keine Berichtszeile mehr.

    Leere Bloecke stehen mit 0 drin und fallen nicht weg: dass die
    Verdichtungen fehlten, ist die interessantere Zeile als dass sie da
    waren.

    ``system_zeichen`` ist seit dem 06.09.2026 (Auftrag 4) dabei: der Umriss
    zeigte bis dahin nur den Koerper -- also ein Viertel des Prompts -- und
    genau diese Teilmessung ist die Wurzel des Befunds C.1."""
    return {
        "bloecke": {name: schaetze(bloecke.get(name, "")) for name in _REIHENFOLGE},
        "system": system_zeichen // _ZEICHEN_JE_TOKEN,
        "gesamt": schaetze(_zusammen(bloecke)),
        "gesamt_mit_system": (
            schaetze(_zusammen(bloecke)) + system_zeichen // _ZEICHEN_JE_TOKEN
        ),
        "gekuerzt": bool(gekuerzt),
    }


def _systemgroesse(conn, chat_id: int, e) -> int:
    """Die Zeichenzahl der Systemanweisung, die zu diesem Zug verschickt wird.

    Der Koerper wird hier gebaut, die Anweisung dort (``ablauf``) -- aber
    gemessen werden muessen sie zusammen (Befund C.1). Statt die Anweisung
    durchzureichen und alle Aufrufer zu aendern, wird sie hier noch einmal
    geholt: ``anweisungen`` cacht sie ohnehin nach mtime, das kostet einen
    stat-Aufruf.

    Faellt das aus irgendeinem Grund aus (fehlende Prompt-Datei am
    Workshoptag), gilt 0: die Gesamtgrenze bremst dann nicht, aber der Bot
    antwortet -- die Koerpergrenze steht ja weiter."""
    try:
        return len(system(getattr(e, "bot_name", None), phasen.aktuelle(conn, chat_id)))
    except Exception:  # pragma: no cover -- Notausgang, siehe Docstring
        log.warning("Systemanweisung fuer die Messung nicht lesbar", exc_info=True)
        return 0


def _bloecke(conn, chat_id: int, ausloeser, e, erstkontakt: bool,
             fenster_eintraege: list, namen: dict[str, str] | None = None) -> dict:
    """Die Bloecke des Nutzertexts, in ihrer Reihenfolge -- datengetrieben:
    jeder Block bleibt leer, solange seine Daten leer sind (SPEC § 6.1)."""
    # Der Kontext-Filter je Phase (05.09.2026 abends): bis zur Kernfrage
    # arbeitet der Bot AM Material (Verdichtungen; Transkripte, wenn der
    # Wortlaut-Schalter steht), danach AUS dem Kernpaket. Datengetrieben wie
    # alles andere -- es gibt keinen gespeicherten Zustand, nur zwei Felder,
    # die die Lage beschreiben.
    material = material_erlaubt(conn, chat_id)
    board = _baue_board(conn, chat_id)
    mitgehoert = _baue_mitgehoert(conn, chat_id)
    if mitgehoert:
        _fasse_marker_zusammen(fenster_eintraege)
    kernpaket = (
        _baue_kernpaket(conn, chat_id) if kernpaket_erlaubt(conn, chat_id) else ""
    )
    return {
        "erstkontakt": _baue_erstkontakt(conn, chat_id, e) if erstkontakt else "",
        "verdichtungen": _baue_verdichtungen(conn, chat_id) if material else "",
        "transkripte": _baue_transkripte(conn, chat_id) if material else "",
        # In 4 und 5 gibt es WEDER Material NOCH Kernpaket: dort wird
        # erfunden (``PHASEN_ERFINDEN``).
        "kernpaket": kernpaket,
        # Kernpaket ODER Arbeitsstand, nie beides fuer denselben Fakt
        # (Audit-Befund G2).
        "arbeitsstand": _baue_arbeitsstand(
            conn, chat_id, ohne_kernpaket_felder=bool(kernpaket)
        ),
        # Direkt dahinter, und **unabhaengig von Phase und Materiallage**:
        # was hier steht, passt in kein Feld und faellt deshalb sonst weg.
        "festlegungen": _baue_festlegungen(conn, chat_id),
        # Gleich daneben: die Hintergrund-Diskussion aus Phase 1, falls das
        # Profil sie faehrt (``workshop.diskussion_aktiv``) -- datengetrieben
        # ueber die Tabelle, keine eigene Abfrage hier noetig.
        "diskussion": _baue_diskussion_block(conn, chat_id),
        # 05.10.2026 (Birk: "Der Chat muss immer ueber alles Bescheid
        # wissen"): das Board in jeder Phase und der Wortlaut alles
        # Mitgehoerten.
        "board": board,
        "mitgehoert": mitgehoert,
        # Direkt dahinter: warum die Gruppe ihre Begriffe gewaehlt hat --
        # nur die Begriffe, die der Board-Block NICHT schon zeigt (ein
        # Fakt, eine Stelle; R-1: ein verworfener, aber gespeicherter
        # Begriff fehlt dort und braucht diesen Block, in jeder Phase).
        "begriffe_detail": _baue_begriffe_detail(conn, chat_id),
        "phasenhinweis": _baue_phasenhinweis(conn, chat_id),
        "figurenhinweis": _baue_figurenhinweis(conn, chat_id),
        "szene": _baue_szene(conn, chat_id),
        "journal": _baue_journal(conn, chat_id),
        "fenster": "\n".join(fenster_eintraege),
        "ausloeser": _baue_ausloeser(ausloeser, namen),
    }


def _kuerze_auf_budget(conn, chat_id: int, e, bloecke: dict,
                       fenster_eintraege: list, system_zeichen: int = 0,
                       ueber_claude: bool = False) -> bool:
    """Die Kuerzungsleiter aus § 7.2. Aendert ``bloecke`` an Ort und Stelle und
    liefert, ob ueberhaupt gekuerzt wurde.

    ``ueber_claude`` (Modellwahl-Karte): das Zielbudget kommt dann aus
    ``IT_OPUS_PROMPT_ZEICHEN`` statt den Kimi-Grenzen -- fuer Koerper- UND
    Gesamtgrenze UND das Token-Ziel (``ZIEL`` ist sonst ein Kimi-Wert und
    wuerde die groessere Zeichengrenze sofort wieder einfangen).

    ``system_zeichen`` ist die Groesse der Systemanweisung dieses Zuges
    (``_systemgroesse``, Auftrag 4): sie wird nie gekuerzt, zaehlt aber gegen
    die Gesamtgrenze. ``baue`` holt sie einmal und reicht sie hierher und in
    den Umriss -- zwei Messungen derselben Zahl waeren zwei Wahrheiten.

    Reihenfolge (praezisiert im Audit 06.09.2026; Auftrag 3 hat sie
    korrigiert -- bis dahin schuetzte sie den groessten Block und opferte
    die kleinsten):

    1. Volltranskripte -- der groesste einzelne Brocken, und ihr Inhalt steht
       verdichtet ohnehin da.
    2. Der Szenenblock auf ``SZENE_ZEICHEN_NOTFALL`` -- **vor** Fenster,
       Journal und Verdichtungen. Begruendung: in Phase 6/7 arbeitet die
       Gruppe an einer Szene und ruft Korrekturen zu; den Text zu behalten,
       den der Bot ohnehin gerade schreibt, und dafuer zu verlieren, was die
       Gruppe dazu gesagt hat, ist die Umkehrung der gewuenschten Prioritaet
       (Befund C.4).
    3. Der Verlauf von vorn -- das Aelteste zuerst, eine ganze Nachricht je
       Schritt.
    4. Das Journal von vorn -- die aeltesten Notizen.
    5. Die Festlegungen von HINTEN -- die juengsten Details zuerst
       (06.09.2026). Sie sind der vorletzte opferbare Block vor dem Material:
       klein, stabil und genau das, was ohne diese Tabelle gar nicht erst im
       Prompt stuende. Und anders als beim Journal faellt hier das Juengste
       zuerst, damit die Grundfestlegung als letzte geht.
    6. Die Diskussion im Ganzen (Padua Phase 1+2, 03.10.2026) -- anders als
       die Festlegungen nicht zeilenweise, sondern in einem Schritt: der
       Verdichtungstext ist durch seinen eigenen Prompt schon auf rund 150
       Woerter gedeckelt und hat keine innere Zeilenstruktur, an der sich
       schneiden liesse.
    7. Die Verdichtungen -- weil sie das Material selbst sind.
    8. Die Garantie: passt es dann immer noch nicht, wird der Szenenblock auf
       genau den Platz zusammengezogen, der uebrig ist (bis hin zu leer). Bis
       zum 06.09.2026 konnte die Kuerzung ihr Ziel verfehlen -- gemessen
       blieben bei einer 20-fachen Szene 105.988 Zeichen stehen.

    Nie angetastet: Kernpaket, Arbeitsstand, Hinweise und die ausloesende
    Nachricht. Es gibt keinen Zustand, in dem der Bot wegen des Budgets nicht
    antworten koennte. Reissen diese allein die Grenze, bleibt der Vorfall
    ``kontext_kuerzung_erfolglos`` (Auftrag 1) -- die Garantie aus Stufe 7
    reicht nur so weit, wie es opferbare Bloecke gibt."""
    grenze = zeichengrenze(ueber_claude)
    gesamt = gesamtgrenze(ueber_claude)
    ziel = gesamt // _ZEICHEN_JE_TOKEN if ueber_claude else ZIEL

    def _zu_lang() -> bool:
        """Ueber Koerpergrenze ODER Token-Ziel ODER Gesamtgrenze -- alle drei
        bremsen.

        Drei Masse, weil sie verschiedene Fehler fangen: ZIEL faengt den
        Koerper, der insgesamt zu gross wird, die Zeichengrenze den, der es in
        Token knapp nicht wird und trotzdem unlesbar ist (der Fall vom
        06.09.2026), und die Gesamtgrenze den Prompt, dessen **Anweisung**
        gewachsen ist -- bis zum Audit (Befund C.1) war das der ungemessene
        Dreiviertelanteil: 26.365 Zeichen System gegen 8.810 Zeichen Koerper.
        """
        text = _zusammen(bloecke)
        return (
            len(text) > grenze
            or schaetze(text) > ziel
            or system_zeichen + len(text) > gesamt
        )

    if not _zu_lang():
        return False

    vorher = len(_zusammen(bloecke))
    bloecke["transkripte"] = ""
    if _zu_lang() and bloecke["szene"]:
        bloecke["szene"] = _baue_szene(conn, chat_id, SZENE_ZEICHEN_NOTFALL)
    while _zu_lang() and fenster_eintraege:
        fenster_eintraege = fenster_eintraege[1:]
        bloecke["fenster"] = "\n".join(fenster_eintraege)
    if _zu_lang() and bloecke["journal"]:
        journalzeilen = bloecke["journal"].split("\n")
        # Zeile 0 ist die Ueberschrift "Journal:" -- sie bleibt, solange
        # noch eine Notiz darunter steht.
        while _zu_lang() and len(journalzeilen) > 2:
            journalzeilen = [journalzeilen[0]] + journalzeilen[2:]
            bloecke["journal"] = "\n".join(journalzeilen)
        if _zu_lang():
            bloecke["journal"] = ""
    if _zu_lang() and bloecke["festlegungen"]:
        festlegungszeilen = bloecke["festlegungen"].split("\n")
        while _zu_lang() and len(festlegungszeilen) > 2:
            festlegungszeilen = festlegungszeilen[:-1]
            bloecke["festlegungen"] = "\n".join(festlegungszeilen)
        if _zu_lang():
            bloecke["festlegungen"] = ""
    # Die Diskussion faellt im Ganzen weg, nicht zeilenweise: der
    # Verdichtungstext ist bereits klein (eigener Prompt-Deckel bei rund 150
    # Woertern) und hat keine Zeilenstruktur wie die Festlegungen, an der
    # sich ein stufenweises Kappen lohnen wuerde.
    if _zu_lang() and bloecke["diskussion"]:
        bloecke["diskussion"] = ""
    if _zu_lang() and bloecke["mitgehoert"]:
        mitzeilen = bloecke["mitgehoert"].split("\n")
        # Zeile 0 ist der Kopf; das Aelteste faellt zuerst.
        while _zu_lang() and len(mitzeilen) > 2:
            mitzeilen = [mitzeilen[0]] + mitzeilen[2:]
            bloecke["mitgehoert"] = "\n".join(mitzeilen)
        if _zu_lang():
            bloecke["mitgehoert"] = ""
    if _zu_lang() and bloecke["board"]:
        bloecke["board"] = ""
    if _zu_lang() and bloecke["begriffe_detail"]:
        bloecke["begriffe_detail"] = ""
    if _zu_lang():
        bloecke["verdichtungen"] = ""
    if _zu_lang() and bloecke["szene"]:
        # Die Garantie. Wieviel Platz bleibt dem Szenenblock, wenn alles
        # andere steht? Genau der wird ihm gegeben -- nicht geschaetzt,
        # sondern ausgerechnet.
        ohne_szene = dict(bloecke, szene="")
        fest = len(_zusammen(ohne_szene))
        platz = min(
            grenze - fest - 2,
            ZIEL * _ZEICHEN_JE_TOKEN - fest - 2,
            gesamt - system_zeichen - fest - 2,
        )
        if platz < 200:
            bloecke["szene"] = ""
        else:
            bloecke["szene"] = _baue_szene(conn, chat_id, platz)
            if _zu_lang():
                bloecke["szene"] = ""
    nachher = len(_zusammen(bloecke))
    repo.merke_vorfall(
        conn, chat_id, getattr(e, "bot_name", None), "kontext_gekuerzt",
        f"Nutzertext von {vorher} auf {nachher} Zeichen gekuerzt "
        f"(Grenze {grenze}, Ziel {ZIEL} Token, System {system_zeichen} "
        f"Zeichen, Gesamtgrenze {gesamt})",
    )
    # **Der zweite Vorfalltyp** (Audit 06.09.2026, Auftrag 1; Vorbild
    # hermes-agent ``should_compress_info`` mit Grund-Rueckgabe:
    # *"Without this signal an over-threshold session fails opaquely."*).
    # Alle Kuerzungsstufen sind durch, alles Opferbare ist geopfert -- seit
    # Auftrag 3 auch die Szene, bis hin zu leer -- und der Prompt ist immer
    # noch zu gross, weil Kernpaket, Arbeitsstand, Hinweise und Ausloeser nie
    # angetastet werden (oder die Systemanweisung allein die Gesamtgrenze
    # frisst). Ohne diese Zeile steht auf dem Dashboard "gekuerzt", nicht
    # "reicht nicht" -- und ein Mechanismus, der sein Ziel verfehlt, ist von
    # einem, der es erreicht, nicht unterscheidbar.
    if _zu_lang():
        uebrig = umriss(bloecke, True, system_zeichen=system_zeichen)
        log.warning("Kuerzung erfolglos, chat_id=%s: %s", chat_id,
                    umrisszeile(uebrig))
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None),
            "kontext_kuerzung_erfolglos",
            f"Nutzertext nach vollstaendiger Kuerzung noch {nachher} Zeichen "
            f"(Grenze {grenze}, System {system_zeichen} Zeichen, Gesamtgrenze "
            f"{gesamt}) -- alle Kuerzungsstufen durchlaufen, ungekuerzte "
            f"Bloecke zu gross: {umrisszeile(uebrig)}",
        )
    return True


def baue(conn, chat_id: int, ausloeser, e, erstkontakt: bool = False,
         protokoll: list | None = None, ueber_claude: bool = False) -> str:
    """Baut den Koerper des Gespraechs-Prompts (ohne SYSTEM, das getrennt
    verschickt wird).

    ``ausloeser`` ist die Liste der Nachrichten, die diesen Zug ausgeloest
    haben (alles seit ``letzte_beantwortete_message_id``, § 1.3) -- vom
    Aufrufer ermittelt, hier nur formatiert.

    ``protokoll`` ist rein additiv: ist es eine Liste, wird ein ``umriss()``
    des fertigen Prompts angehaengt (der Simulator misst damit, was wann im
    Prompt stand). **Unabhaengig davon** schreibt jeder Aufruf seit dem
    06.09.2026 eine Umriss-Zeile ins Log -- nur Zahlen, kein Prompt-Inhalt.

    Passt der Koerper nicht ins Zielbudget ZIEL, unter die Koerpergrenze oder
    -- zusammen mit der Systemanweisung -- unter die Gesamtgrenze, greift die
    Kuerzung aus § 7.2 in der Reihenfolge Transkripte -> Szenenblock ->
    Fenster -> Journal -> Festlegungen -> Verdichtungen -> Szenenblock auf
    den Restplatz (``_kuerze_auf_budget``). Das Fenster wird von vorn
    beschnitten -- eine ganze Nachricht (oder Pausenzeile) je Schritt, nie
    nur eine physische Zeile eines mehrzeiligen Beitrags. Arbeitsstand,
    Kernpaket, Hinweise und Ausloeser sind von der Kuerzung grundsaetzlich
    ausgenommen; es gibt keinen Zustand, in dem der Bot wegen des Budgets
    nicht antworten koennte."""
    # E8: die Pseudonyme einmal je Prompt, fuer Fenster UND Ausloeser.
    namen = pseudonyme(conn, chat_id, ausloeser)
    fenster_eintraege = _baue_fenster_eintraege(conn, chat_id, ausloeser, namen)
    bloecke = _bloecke(conn, chat_id, ausloeser, e, erstkontakt, fenster_eintraege, namen)
    # Einmal gemessen, zweimal gebraucht: in der Kuerzung (Gesamtgrenze) und
    # im Umriss (Auftrag 4, Befund C.1).
    system_zeichen = _systemgroesse(conn, chat_id, e)
    gekuerzt = _kuerze_auf_budget(
        conn, chat_id, e, bloecke, fenster_eintraege, system_zeichen,
        ueber_claude=ueber_claude,
    )

    stand = umriss(bloecke, gekuerzt, system_zeichen=system_zeichen)
    # **Im Betrieb mitschreiben** (Audit 06.09.2026, Auftrag 1). Bis hierher
    # lieferte ``umriss()`` genau die Aufschluesselung, die hermes-agent in
    # ``context_breakdown.py`` fuer die Anzeige baut -- aber nur, wenn
    # ``protokoll`` uebergeben wurde, und das tat im Betrieb niemand
    # (Befund B, Zeile "Verlust sichtbar machen": *"Wir haben das Werkzeug und
    # schalten es im Betrieb ab."*). Die Zeile steht hier und nicht beim
    # Aufrufer, damit sie **jeden** Pfad erfasst -- Gespraechszug, Auftragszug,
    # Erstkontakt, Messskript: ein durchgereichter Parameter waere genau der
    # Weg gewesen, auf dem sie beim naechsten neuen Aufrufer wieder fehlt.
    # Am Workshoptag ist die wichtigste Faehigkeit, einen Fehler zu SEHEN,
    # waehrend er passiert. Eine Logzeile je Zug, nur Zahlen, kein Inhalt.
    log.info("%s chat_id=%s", umrisszeile(stand), chat_id)

    if protokoll is not None:
        protokoll.append(stand)
    return _zusammen(bloecke)


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)

T = sprache.Texte(__name__)

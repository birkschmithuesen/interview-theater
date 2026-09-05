"""Szenentexte schreiben -- der erste Aufruf mit aktivem Reasoning
(SPEC-kontext-architektur.md § 4.5, § 6.2 Block 4/5).

Das Hauptziel des ganzen Werkzeugs ist ein guter Theatertext. Genau dort
hoerte der Code bisher auf: die Tabelle ``szene`` stand leer im Schema,
``LLM.prosa`` war toter Code. Bekaeme die Gruppe ihren Szenentext im normalen
Gespraechszug, bekaeme sie ihn von einem Aufruf, der auf Dialog optimiert ist
-- Reasoning aus, erzwungenes Schema ``{"antwort"}``, Systemanweisung "fass
dich kurz". Deshalb ein eigener Weg.

**Warum hier Reasoning AN ist und sonst nirgends.** Die Entscheidung folgt
der Matrix in ``reasoning-stufen-entscheidungshilfe.md`` § 4.2, nicht dem
Gefuehl, dass Szenentext "wichtiger" waere: nicht die Wichtigkeit einer
Aufgabe entscheidet, sondern ob ein Mensch auf die Antwort wartet und ob die
Aufgabe strukturell profitiert. Beim Szenentext ist beides guenstig --
dramaturgische Abwaegung ueber viele Interviewstellen hinweg, und **niemand
wartet**, weil dieser Aufruf ausdruecklich nicht im Gespraechszug laeuft,
sondern in einem eigenen Thread. Extraktion, Klassifikation und der
Gespraechszug bleiben unveraendert bei ``"none"``; dort kostete Reasoning nur
Latenz (Faktor 7-23) und koennte bei Regeln mit Ausnahmen sogar schaden.

Zwei gemessene Randbedingungen, die daran haengen (dieselbe Wissensdatei
§ 3.2, § 4.3): bei aktivem Reasoning ``max_tokens >= 12.000``, sonst endet
der Lauf im Denken und liefert HTTP 200 mit leerem Inhalt; und ein
Zeitbudget, das nicht der 30-Sekunden-Klient aus ``bot.main`` vorgibt.

**Ablauf.** Der Absichtserkenner (art ``szene_schreiben``) oder der Befehl
``/szene`` rufen ``starte()``. Das **prueft zuerst** (siehe unten), schickt
dann eine Zeile in die Gruppe -- sie soll wissen, dass etwas laeuft, und
derweil weiterarbeiten koennen -- und gibt den eigentlichen Aufruf an einen
Thread ab (Muster: der Nachhol-Arbeiter in ``aufnahme.py``). Der baut den
Prompt, ruft ``LLM.prosa``, trennt TITEL/KURZ vom Text, speichert die Szene,
schreibt einen ``entschieden``-Journaleintrag und schickt Titel samt Anfang in
die Gruppe.

**Eine Szene wird geplant, bevor sie geschrieben wird** (05.09.2026). Fehlt
ein Pflichtfeld (``PFLICHTFELDER``: form, ort, figuren, was_passiert) oder hat
eine Figur dieser Szene kein Sprachprofil, gibt es **keinen Aufruf** --
stattdessen eine Nachricht, die in einem Satz sagt, was fehlt
(``sperrtext``). Der Grund ist gemessen: ein Modell, dem Ort und Besetzung
fehlen, scheitert nicht, es erfindet welche. Im Probelauf entstand so eine
Szene in einer Kueche statt im Polizeikessel, mit NINA und MORITZ statt Mira,
Pola und Pal. Daneben steht ein **Hinweis, der keine Sperre ist**: eine Figur,
die in dieser Szene zum ersten Mal auftaucht, bekommt eine Zeile im Chat --
geschrieben wird trotzdem (``neue_figuren_hinweis``).

**Eine Szene je Gruppe gleichzeitig** (Sperre je ``chat_id``, wie in
``ablauf.py``). Anders als dort wird aber nichts gesammelt: ein zweiter
Auftrag waehrend eines laufenden Laufs bekommt eine kurze Zeile und wird
verworfen. Zwei parallele Szenenlaeufe waeren zwei teure, langsame Aufrufe,
deren Ergebnisse einander in ``geaendert_am`` ueberholen -- die Gruppe saehe
zwei Szenen und wuesste nicht, welche gilt.

**Fehler werden gemeldet** (SPEC § 11.1): anders als beim Absichtserkenner
wartet die Gruppe hier tatsaechlich, sie hat gerade eine Ankuendigung
bekommen. Also eine kurze, ehrliche Zeile plus ``vorfall``
``szene_fehlgeschlagen``. Kein eigener Wiederholungsversuch ueber die drei
aus ``llm.py`` hinaus -- ein vierter Anlauf an einem 90-Sekunden-Aufruf
haette die Gruppe minutenlang hingehalten.
"""

from __future__ import annotations

import logging
import re
import threading

import httpx

from interview_theater import anweisungen, repo, szene_claude

log = logging.getLogger(__name__)

#: Art dieses Aufrufs in der Tabelle ``aufruf`` (Modus B setzt ``LLM.prosa``).
ART = "szene"

#: Ausgabebudget. Aktives Reasoning verbraucht es VOR dem eigentlichen
#: Inhalt; unter 12.000 endet der Lauf im Denken und liefert HTTP 200 mit
#: leerem Inhalt (gemessen 04.09.2026, reasoning-stufen-entscheidungshilfe.md
#: § 3.2 Fussnote 1 und § 4.3). Deutlich groesser als llm.MAX_TOKENS = 9000,
#: das fuer Aufrufe ohne Reasoning bemessen ist.
#: Nachtrag 04.09. abends: mit dem erweiterten Prompt (13 Dramaturgie-Regeln,
#: 30 Tells) liefen zwei Live-Versuche in 12.000 Token *nur Denken* leer
#: (finish_reason=length, 86 s und 95 s, kein Inhalt); der erste erfolgreiche
#: Lauf brauchte 19.410. Das Budget ist eine OBERGRENZE gegen Durchdrehen,
#: kein Zielwert: was das Modell nicht braucht, kostet nichts. Deshalb weit
#: ueber der Messung -- ein Deckel knapp ueber dem letzten Lauf programmiert
#: den naechsten Abbruch vor (Birk). Nicht das ganze Fenster: Infomaniak
#: rechnet max_tokens + Eingabe gegen max_total_tokens=249.984 (HTTP 400 bei
#: 250k, gemessen 04.09. 22:11); 200k liess Platz fuer ~50k Eingabe.
MAX_TOKENS = 200_000

#: Zeitbudget des einzelnen Versuchs. Der httpx.Client aus ``bot.main`` hat
#: 30 s -- das reicht fuer einen Reasoning-Lauf nicht: gemessen wurden 33,8 s
#: fuer freien Prosatext bei Kimi und 20-50 s bei Qwen, ohne die zusaetzliche
#: Laenge eines Szenentextes. Die Wissensdatei nennt 60 s als Untergrenze fuer
#: Reasoning-Aufrufe (§ 4.4), der Auftrag 90 s; hier grosszuegiger, weil ein
#: Timeout hier nichts spart -- niemand wartet aktiv, und ein abgebrochener
#: Lauf ist trotzdem bezahlt.
TIMEOUT_S = 600.0

#: So viele nichtleere Zeilen der Szene gehen als Vorschau in die Gruppe.
VORSCHAU_ZEILEN = 6

#: Nur in den ersten paar Zeilen der Modellantwort wird nach TITEL/KURZ
#: gesucht -- weiter unten waere ein "TITEL:" Teil der Szene, nicht ihr Kopf.
_KOPFZEILEN = 6

_TEXT_ANGEKUENDIGT = (
    "Ich schreibe die Szene aus, das dauert eine Minute - ihr koennt derweil "
    "weiterarbeiten."
)
_TEXT_BESETZT = "Ich schreibe gerade noch an einer Szene, gleich."
_TEXT_FEHLER = (
    "Die Szene ist mir nicht gelungen. Sagt es nochmal, dann versuche ich es neu."
)
_TEXT_VOLLSTAENDIG = "Vollstaendig auf eurer Gruppenseite."
#: Birk 05.09.: "schaltet Opus als Modell ein ab /szene mit einer Warnung,
#: dass ab nun die Daten nach Amerika abfliessen." Steht VOR der
#: Ankuendigung, jedes Mal -- nicht nur beim ersten Mal, weil die Gruppe
#: wechselt und weil es um Daten geht.
_TEXT_WARNUNG_USA = (
    "Hinweis: Den Szenentext schreibt ein Modell von Anthropic (USA). Dafuer "
    "gehen jetzt euer Arbeitsstand, die Figuren mit ihren Zitaten und die "
    "Szenenangaben an einen Server in den USA -- keine Audioaufnahmen, keine "
    "vollstaendigen Interviews, keine Namen aus diesem Chat. Alles andere "
    "bleibt in der Schweiz."
)
#: Das Angebot, einmal je Gruppe, vor der ersten Szene. Die Gruppe antwortet
#: im Chat; der Erkenner liest es (art szene_usa, wert ja/nein).
_TEXT_ANGEBOT_USA = (
    "Bevor ich die erste Szene schreibe, eine Entscheidung fuer euch.\n\n"
    "Bis jetzt lief alles in der Schweiz: eure Aufnahmen, die Interviews, "
    "alles mit Namen. Das bleibt so.\n\n"
    "Fuer den Szenentext gibt es ein besseres Modell -- von Anthropic, in den "
    "USA. Wir haben es heute frueh verglichen: es schreibt deutlich bessere "
    "Buehnentexte. Wenn ihr es nehmt, gehen dafuer euer Kernthema, die "
    "Figuren mit ihren Zitaten und die Szenenangaben an einen Server in den "
    "USA -- also das, was spaeter ohnehin auf der Buehne steht. Keine "
    "Aufnahmen, keine ganzen Interviews, keine Namen aus diesem Chat.\n\n"
    "Wollt ihr das? Sagt ja oder nein. Bei nein schreibe ich die Szene in "
    "der Schweiz -- das geht auch, der Text wird einfacher."
)
_TEXT_USA_JA = "Gut, Szenen kommen ab jetzt vom US-Modell. Ich sage es vor jeder Szene nochmal."
_TEXT_USA_NEIN = "Verstanden, alles bleibt in der Schweiz. Ich frage nicht wieder."
_TEXT_USA_ERINNERUNG = (
    "Die Szene kommt, sobald ihr die Frage von oben beantwortet habt: "
    "US-Modell ja oder nein? Schreibt einfach /szene usa ja oder "
    "/szene usa nein."
)
#: Nach so vielen vergeblichen Erinnerungen wird nicht weiter erinnert,
#: sondern in der Schweiz geschrieben (05.09.2026, in der Simulation
#: gemessen): Birk sagte dreimal "jetzt endlich die szene schreiben" und
#: "ja stimmt alles" -- der Erkenner las das als Zustimmung zu den FIGUREN,
#: nicht als Antwort auf die USA-Frage, und der Bot wiederholte siebenmal
#: dieselbe Zeile. Eine unbeantwortete Einwilligung darf die Arbeit nicht
#: dauerhaft blockieren; das Vorsichtige ist hier das Schweizer Modell,
#: nicht das Warten.
USA_ERINNERUNGEN_MAX = 2
_TEXT_USA_KEINE_ANTWORT = (
    "Ihr habt die Frage nach dem US-Modell nicht beantwortet - ich schreibe "
    "die Szene deshalb in der Schweiz. Wollt ihr es doch anders, sagt "
    "/szene usa ja."
)


class SzeneFehler(Exception):
    """Der Szenen-Aufruf lieferte nichts Verwertbares."""


# Eine Sperre je chat_id, genau wie in ablauf.py -- Szenenlaeufe verschiedener
# Gruppen duerfen sich nie gegenseitig blockieren. Sie wird im aufrufenden
# Thread genommen (in starte(), damit ein zweiter Auftrag SOFORT eine Antwort
# bekommt) und im Arbeitsthread wieder freigegeben; das ist der Grund fuer
# threading.Lock statt RLock -- ein RLock liesse sich vom fremden Thread gar
# nicht freigeben.
_sperren: dict[int, threading.Lock] = {}
_sperren_schutz = threading.Lock()

#: Wie oft je Gruppe schon vergeblich an die USA-Frage erinnert wurde.
#: Bewusst im Prozess und nicht in der Datenbank: es ist ein Zaehler fuer die
#: laufende Sitzung, kein Zustand des Workshops -- nach einem Neustart darf
#: der Bot wieder zweimal fragen, bevor er selbst entscheidet.
_usa_erinnerungen: dict[int, int] = {}


def _sperre_fuer(chat_id: int) -> threading.Lock:
    """Liefert die (ggf. neu angelegte) Sperre fuer eine chat_id."""
    with _sperren_schutz:
        sperre = _sperren.get(chat_id)
        if sperre is None:
            sperre = threading.Lock()
            _sperren[chat_id] = sperre
        return sperre


#: Die Formen, fuer die es einen eigenen Regelblock gibt
#: (``prompts/formen/<name>.md``). ``dialog`` ist der Rueckfall: eine Gruppe,
#: die nichts anderes gesagt hat, bekommt Dialog.
FORMEN = ("dialog", "lied", "rap", "monolog", "chor", "stumm")

#: Woerter, unter denen eine Form gemeint sein kann -- wie
#: ``phasen.STICHWOERTER``: das Feld ``szene.form`` ist frei (die Gruppe
#: entscheidet, nicht der Code), und "gesungen" muss trotzdem beim Lied
#: landen. Verglichen wird in beide Richtungen, deshalb genuegen Wortstaemme.
FORM_STICHWOERTER = {
    "lied": ("lied", "song", "gesang", "gesungen", "singen", "musik", "arie"),
    "rap": ("rap", "sprechgesang", "beat", "reim"),
    "monolog": ("monolog", "soloszene", "solo"),
    "chor": ("chor", "chorisch", "wir-form", "sprechchor"),
    "stumm": ("stumm", "pantomime", "ohne worte", "wortlos"),
    "dialog": ("dialog", "gespraech", "gespräch", "gesprochen", "sprechtheater"),
}


def formdatei(form: str | None) -> str:
    """Uebersetzt das freie Feld ``szene.form`` in den Namen eines
    Regelblocks. Kennt der Code die Form nicht, gilt ``dialog``.

    Der Rueckfall ist eine Entscheidung, kein Notbehelf: eine unbekannte Form
    ("Bewegungsszene") ist im Zweifel gesprochenes Theater, und ein Prompt
    ohne jeden Formenblock haette gar keine Dramaturgieregeln mehr -- die
    stehen seit dem 05.09.2026 alle in ``prompts/formen/``.

    **Dialog wird zuletzt geprueft**, nicht in Listenreihenfolge: das Wort
    "Szene" steht in "stumme Szene" genauso wie in jeder anderen Angabe, und
    Dialog ist ohnehin der Rueckfall -- er braucht keinen Vorrang, er braucht
    den Rest."""
    text = (form or "").strip().lower()
    if not text:
        return "dialog"
    for name in FORMEN:
        if name == "dialog":
            continue
        for stichwort in FORM_STICHWOERTER.get(name, ()):
            if stichwort in text:
                return name
    return "dialog"


def systemanweisung(form: str | None = None) -> str:
    """Die Systemanweisung des Szenen-Aufrufs, dreiteilig und heiss
    nachgeladen: ``prompts/szene.md`` (was fuer jede Form gilt), der
    Regelblock zur Form (``prompts/formen/<form>.md``) und die Negativliste
    ``prompts/theater-tells.md``.

    **Die Form-Verzweigung** ist seit dem 05.09.2026 dabei: ein Lied hat
    andere Regeln als ein Dialog, und die dreizehn Dialogregeln auf ein Lied
    anzuwenden hiesse, ein Lied wie einen Dialog zu schreiben. Was fuer jede
    Form gilt, steht in ``szene.md``; was nur fuer eine, in ihrer Datei.

    Die Tells stehen ausdruecklich in einer eigenen Datei und werden erst
    hier im Code angehaengt: sie sind der Teil, den die Gruppe im Workshop
    laufend erweitert ("das klingt schon wieder wie ChatGPT"), waehrend die
    Anweisung selbst stehen bleibt. Drei Dateien, drei Aenderungsrhythmen --
    und dank des Hot-Reloads in ``anweisungen.py`` wirkt eine Ergaenzung ohne
    Neustart, beim naechsten Szenen-Auftrag."""
    teile = [anweisungen.hole("szene")]
    regeln = anweisungen.hole_optional(f"formen/{formdatei(form)}")
    if regeln and regeln.strip():
        teile.append(regeln.strip())
    teile.append(anweisungen.hole("theater-tells"))
    return "\n\n".join(teile)


# ---------------------------------------------------------------------------
# Auftrag lesen
# ---------------------------------------------------------------------------

#: Erkennt eine Szenennummer im Auftrag ("Szene 2: ...", "schreib Szene 3
#: nochmal", "szene nr. 4"). Ausgeschriebene Zahlwoerter ("die zweite Szene")
#: erkennt das bewusst nicht: ein falsch geratener Treffer wuerde eine
#: bestehende Szene ueberschreiben, ein verpasster legt nur eine neue an. Die
#: Fehlerrichtung ist damit die harmlose.
_NUMMER = re.compile(r"\bszene\s*(?:nr\.?|nummer)?\s*(\d{1,3})\b", re.IGNORECASE)


def nummer_aus_auftrag(auftrag: str) -> int | None:
    """Liest die Szenennummer aus dem Auftrag, oder None.

    Nennt der Auftrag eine Nummer, zu der es schon eine Szene gibt, wird
    diese ueberschrieben (der Normalfall "Szene 2 nochmal, aber kuerzer");
    sonst entsteht eine neue."""
    treffer = _NUMMER.search(auftrag or "")
    return int(treffer.group(1)) if treffer else None


# ---------------------------------------------------------------------------
# Szenenplanung: die Felder, die vor dem Text feststehen
# ---------------------------------------------------------------------------

#: Ohne diese vier wird **nicht geschrieben** (Sperre, T5): ohne Form weiss
#: das Modell nicht, ob Dialog oder Lied; ohne Ort, Besetzung und Handlung
#: erfindet es welche -- genau das ist im Probelauf passiert (Kueche statt
#: Demo, NINA und MORITZ statt Mira, Pola und Pal). ``figuren`` steht dabei
#: fuer die Verknuepfung, nicht fuer eine Spalte.
PFLICHTFELDER = ("form", "ort", "figuren", "was_passiert")

#: Pflichtfelder, die nicht an der Szene haengen, sondern am Arbeitsstand der
#: Gruppe: die Ergebnisse von Phase 5 (Format & Rahmen). Ohne sie ist nicht
#: entschieden, WAS entsteht und WORIN es spielt -- das Modell erfindet dann
#: beides, und zwar je Szene neu. Birk 05.09.2026, nachdem eine Szene ohne
#: gesetztes Format und ohne Rahmen geschrieben wurde.
ARBEITSSTAND_PFLICHTFELDER = ("format", "rahmen")

#: Wie ein Feld in einer Nachricht an die Gruppe heisst.
FELDNAMEN = {
    "form": "Form",
    "ort": "Ort",
    "zeit": "Zeit",
    "anlass": "Anlass",
    "figuren": "Wer",
    "was_passiert": "Was passiert",
    "was_anders": "Was anders ist",
    "kernsaetze": "Kernsaetze",
    "ton": "Ton",
    "titel": "Titel",
    "kurzbeschreibung": "Kurz",
    # Aus dem Arbeitsstand (ARBEITSSTAND_PFLICHTFELDER), nicht aus der Szene:
    # so benannt, dass die Gruppe erkennt, wonach sie noch nicht gefragt wurde.
    "format": "das Format des Stuecks (Phase 5)",
    "rahmen": "der Rahmen: Ort, Zeit, Anlass des Abends (Phase 5)",
}

#: Schluessel, unter denen ein Feld in einer ``szene_planen``-Angabe stehen
#: darf. Der Prompt schreibt die Spaltennamen vor; die Aliase daneben kosten
#: nichts und fangen die naheliegenden Varianten ab, bevor ein ganzes Feld
#: stillschweigend verloren geht.
FELD_ALIASE = {
    "form": "form",
    "ort": "ort",
    "orte": "ort",
    "zeit": "zeit",
    "anlass": "anlass",
    "figuren": "figuren",
    "figur": "figuren",
    "wer": "figuren",
    "was_passiert": "was_passiert",
    "was passiert": "was_passiert",
    "passiert": "was_passiert",
    "handlung": "was_passiert",
    "was_anders": "was_anders",
    "was anders": "was_anders",
    "anders": "was_anders",
    "kernsaetze": "kernsaetze",
    "kernsätze": "kernsaetze",
    "kernsatz": "kernsaetze",
    "ton": "ton",
    "titel": "titel",
    "kurz": "kurzbeschreibung",
    "kurzbeschreibung": "kurzbeschreibung",
}

#: Trennt die Angaben einer Planung. Bewusst die Pipe und nicht das Komma:
#: in "figuren: Mira, Pola, Pal" und in einem Handlungssatz stehen Kommas.
PLANUNG_TRENNER = "|"

#: "Szene 1", "szene nr. 2", "2" -- der Kopf einer Planungsangabe.
_PLANUNG_NUMMER = re.compile(r"^\s*(?:szene\s*(?:nr\.?|nummer)?\s*)?(\d{1,3})\s*$",
                             re.IGNORECASE)


def feldname(wort: str) -> str | None:
    """Uebersetzt ein Wort in einen Szenenfeldnamen, oder None.

    Die eine Stelle, an der ``FELD_ALIASE`` ausgewertet wird -- der Befehl
    ``/szene <n> <feld> <wert>`` und die Erkennerangabe ``szene_planen``
    sollen dieselben Woerter verstehen."""
    return FELD_ALIASE.get((wort or "").strip().lower())


def zerlege_planung(wert: str) -> tuple[int | None, dict[str, str]]:
    """Liest eine ``szene_planen``-Angabe: ``"Szene 1 | form: Dialog | ort:
    Polizeikessel | figuren: Mira, Pola | was_passiert: ..."``.

    Liefert ``(nummer, felder)``. ``nummer`` ist None, wenn keine genannt
    wurde -- der Aufrufer entscheidet dann, welche Szene gemeint ist. In
    ``felder`` steht nur, was **dasteht**: ein fehlender Schluessel bleibt
    unberuehrt, damit ein spaeterer Lauf einzelne Felder nachtragen kann, ohne
    die frueheren zu loeschen. Ein leerer Wert zaehlt dabei als "nicht
    genannt" und nicht als "loeschen" -- weggenommen wird ausschliesslich ueber
    ``entfernen``.

    ``figuren`` bleibt hier ein roher String; wer daraus Figuren macht, muss
    den Arbeitsstand kennen (``erkenner._wende_szene_planen_an``)."""
    felder: dict[str, str] = {}
    nummer = None
    for teil in (wert or "").split(PLANUNG_TRENNER):
        teil = teil.strip()
        if not teil:
            continue
        kopf, trenner, rest = teil.partition(":")
        schluessel = feldname(kopf)
        if trenner and schluessel:
            if rest.strip():
                felder[schluessel] = rest.strip()
            continue
        # Kein bekanntes Feld: dann ist es der Kopf mit der Szenennummer.
        treffer = _PLANUNG_NUMMER.match(teil.split(":", 1)[0])
        if treffer and nummer is None:
            nummer = int(treffer.group(1))
    return nummer, felder


# ---------------------------------------------------------------------------
# Die Sperre: was fehlt, wird gefragt statt geraten
# ---------------------------------------------------------------------------

_TEXT_FEHLENDE_FELDER = "Fuer {kopf} fehlt noch: {felder}."
_TEXT_OHNE_PROFIL_EINE = (
    "Und {namen} hat noch kein Sprachprofil - aus welchem Interview spricht sie?"
)
_TEXT_OHNE_PROFIL_MEHRERE = (
    "Und {namen} haben noch kein Sprachprofil - aus welchen Interviews sprechen "
    "sie?"
)

#: Der Hinweis, der KEINE Sperre ist: eine Figur taucht zum ersten Mal auf.
#: Die Szene wird trotzdem geschrieben -- die Gruppe darf eine Figur
#: einfuehren, wo sie will, sie soll es nur merken.
_TEXT_NEUE_FIGUR_EINE = (
    "{namen} taucht in Szene {nummer} zum ersten Mal auf - wo war sie vorher?"
)
_TEXT_NEUE_FIGUR_MEHRERE = (
    "{namen} tauchen in Szene {nummer} zum ersten Mal auf - wo waren sie vorher?"
)


def _und(namen: list[str]) -> str:
    """"Mira, Pola und Pal" -- eine Aufzaehlung, wie man sie spricht."""
    if len(namen) <= 1:
        return "".join(namen)
    return ", ".join(namen[:-1]) + " und " + namen[-1]


def _kopf(zeile) -> str:
    return f"Szene {zeile['nummer']}" if zeile["nummer"] is not None else "die Szene"


def fehlendes(conn, ziel) -> tuple[list[str], list[str]]:
    """Was diese Szene noch braucht: ``(fehlende Pflichtfelder, Figuren ohne
    Sprachprofil)``.

    Rein aus der Datenbank, kein Modellaufruf. Beides zusammen, weil beides
    dieselbe Antwort verhindert: ein Szenentext, den das Modell aus dem
    Nichts erfindet. Im Probelauf fehlten Ort und Besetzung, und heraus kam
    eine Kueche mit NINA und MORITZ; ohne Sprachprofil klingen alle Figuren
    gleich.

    Seit 05.09.2026 zaehlen ``format`` und ``rahmen`` aus dem Arbeitsstand
    mit (Birk: "es wurde gerade szene geschrieben, ohne dass nach setting,
    format, stil gefragt wurde -- diese variablen muessen alle vorher vom
    user gesetzt sein, bevor eine szene geschrieben werden darf"). Sie
    gehoeren zu Phase 5 und standen deshalb nicht in PFLICHTFELDER, das nur
    die Felder der Szene selbst kennt -- gemessen an Szene 1 der Gruppe 1:
    alle vier Szenenfelder gesetzt, format und rahmen leer, Szene lief."""
    figuren = repo.szene_figuren(conn, ziel["id"])
    felder = []
    for feld in PFLICHTFELDER:
        if feld == "figuren":
            if not figuren:
                felder.append(feld)
        elif not ziel[feld]:
            felder.append(feld)
    stand = repo.hole_arbeitsstand(conn, ziel["chat_id"])
    for feld in ARBEITSSTAND_PFLICHTFELDER:
        if stand is None or not (stand[feld] or "").strip():
            felder.append(feld)
    ohne_profil = [f["name"] for f in figuren if not f["sprachprofil"]]
    # 05.09. spaeter: eine Figur OHNE Interview darf existieren ("Kati und
    # Hannah sind erfunden, fuellst du frei" -- Birk in der Simulation, und der
    # Bot sperrte trotzdem dreimal). Sperre nur, wenn die Figur weder
    # Sprachprofil NOCH Beschreibung hat; mit Beschreibung schreibt das Modell
    # die Stimme aus ihr (szene.md: "verteile die Sprechweise bewusst").
    ohne_profil = [
        f["name"] for f in figuren
        if not f["sprachprofil"] and not (f["beschreibung"] or "").strip()
    ]
    return felder, ohne_profil


def sperrtext(conn, ziel) -> str | None:
    """Die eine Nachricht, mit der der Bot sagt, was fehlt -- oder None, wenn
    nichts fehlt und geschrieben werden darf.

    **Eine Nachricht, keine Rueckfragenkette.** Im Probelauf fragte der Bot
    vier Mal hintereinander nach einer weiteren Klarstellung (Nachrichten 84,
    98, 108, 114) und schrieb am Ende trotzdem die falsche Szene. Was fehlt,
    steht hier vollstaendig in einem Satz, und die Gruppe antwortet in
    einem."""
    felder, ohne_profil = fehlendes(conn, ziel)
    if not felder and not ohne_profil:
        return None
    teile = []
    if felder:
        teile.append(_TEXT_FEHLENDE_FELDER.format(
            kopf=_kopf(ziel), felder=", ".join(FELDNAMEN[f] for f in felder),
        ))
    if ohne_profil:
        vorlage = (
            _TEXT_OHNE_PROFIL_EINE if len(ohne_profil) == 1
            else _TEXT_OHNE_PROFIL_MEHRERE
        )
        teile.append(vorlage.format(namen=_und(ohne_profil)))
    return " ".join(teile)


def neue_figuren_hinweis(conn, chat_id: int, ziel) -> str | None:
    """Der Hinweis, der **keine** Sperre ist: eine Figur kommt in dieser Szene
    vor, war aber in keiner frueheren.

    Die Szene wird trotzdem geschrieben -- eine Figur darf auftreten, wo die
    Gruppe will. Sie soll es nur merken, bevor jemand im Durchlauf fragt, wo
    diese Person die letzten zwei Szenen war.

    Nur, wenn es ueberhaupt eine fruehere Szene gibt: in der ersten Szene
    taucht jede Figur zum ersten Mal auf, und das ist keine Beobachtung."""
    if ziel["nummer"] is None:
        return None
    frueher = set()
    gab_es = False
    for szene in repo.hole_szenen(conn, chat_id):
        if szene["nummer"] is None or szene["nummer"] >= ziel["nummer"]:
            continue
        gab_es = True
        frueher.update(f["id"] for f in repo.szene_figuren(conn, szene["id"]))
    if not gab_es:
        return None
    neue = [f["name"] for f in repo.szene_figuren(conn, ziel["id"]) if f["id"] not in frueher]
    if not neue:
        return None
    vorlage = _TEXT_NEUE_FIGUR_EINE if len(neue) == 1 else _TEXT_NEUE_FIGUR_MEHRERE
    return vorlage.format(namen=_und(neue), nummer=ziel["nummer"])


def planungszeile(conn, zeile) -> str:
    """Eine Szenenplanung in einer Zeile, fuer eine Nachricht an die Gruppe:
    ``"Szene 1 · Dialog · Polizeikessel · Mira, Pola, Pal"``.

    Nur die Felder, die es gibt -- datengetrieben wie alles andere. Sie ist
    absichtlich kuerzer als der Prompt-Block aus ``_diese_szene_text``: im
    Chat soll die Gruppe auf einen Blick erkennen, welche Szene gemeint ist,
    nicht die ganze Planung noch einmal lesen."""
    nummer = zeile["nummer"]
    stuecke = [f"Szene {nummer}" if nummer is not None else "Szene"]
    for feld in ("form", "ort"):
        if zeile[feld]:
            stuecke.append(zeile[feld])
    namen = [f["name"] for f in repo.szene_figuren(conn, zeile["id"])]
    if namen:
        stuecke.append(", ".join(namen))
    return " · ".join(stuecke)


def _szene_mit_nummer(szenen, nummer: int | None):
    if nummer is None:
        return None
    return next((s for s in szenen if s["nummer"] == nummer), None)


def ziel_fuer(conn, chat_id: int, auftrag: str):
    """Die Szene, die dieser Auftrag meint -- und wenn es sie noch nicht gibt,
    eine neue, leere mit dieser Nummer.

    Drei Faelle, in dieser Reihenfolge:

    * der Auftrag nennt eine Nummer, zu der es eine Szene gibt -> die;
    * er nennt eine Nummer ohne Szene -> eine neue, leere mit dieser Nummer
      (die Sperre unten sagt dann, was ihr fehlt -- und die Gruppe hat einen
      Platz, an dem sie es nachtraegt);
    * er nennt keine -> die zuletzt bearbeitete Szene, sonst Szene 1.

    Der dritte Fall ist am 05.09.2026 umgedreht worden: frueher entstand ohne
    Nummer eine neue Szene mit der naechsten freien Nummer. Seit eine Szene
    erst geplant und dann geschrieben wird, ist das falsch -- "Go, mach den
    Text" meint die Szene, ueber die die Gruppe gerade geredet hat, und eine
    neue, leere haette gar keine Angaben und wuerde von der Sperre sofort
    aufgehalten. Dieselbe Regel wie in ``erkenner._wende_szene_planen_an``."""
    nummer = nummer_aus_auftrag(auftrag)
    ziel = _szene_mit_nummer(repo.hole_szenen(conn, chat_id), nummer)
    if ziel is not None:
        return ziel
    if nummer is None:
        letzte = repo.hole_letzte_szene(conn, chat_id)
        if letzte is not None:
            return letzte
        nummer = 1
    return repo.hole_szene(conn, repo.stelle_szene_sicher(conn, chat_id, nummer))


# ---------------------------------------------------------------------------
# Prompt-Zusammenbau (eigener, nicht kontext.baue)
# ---------------------------------------------------------------------------


def _format_rahmen_text(conn, chat_id: int) -> str:
    """Block 1: Format und Rahmen (Phase 5).

    Zuerst, weil er ueber allem steht: er entscheidet, ob ueberhaupt ein
    Dialog entsteht oder ein Lied, und worin das Ganze spielt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen = []
    if stand["format"]:
        zeilen.append(f"Format des Stuecks: {stand['format']}")
    if stand["rahmen"]:
        zeilen.append(f"Rahmen: {stand['rahmen']}")
    return "\n".join(zeilen)


def _thema_text(conn, chat_id: int) -> str:
    """Block 2: Kernthema samt Begruendung, Hauptkonflikt nur, wenn es einen
    gibt.

    Der Hauptkonflikt ist seit dem 05.09.2026 optional (Birk: "Es muss nicht
    immer einen Konflikt geben") -- eine leere Zeile "Hauptkonflikt: -" wuerde
    das Modell einen erfinden lassen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen = []
    if stand["kernthema"]:
        zeile = f"Kernthema: {stand['kernthema']}"
        if stand["kernthema_begruendung"]:
            zeile += f" (Begruendung: {stand['kernthema_begruendung']})"
        zeilen.append(zeile)
    if stand["hauptkonflikt"]:
        zeilen.append(f"Hauptkonflikt: {stand['hauptkonflikt']}")
    return "\n".join(zeilen)


#: Ueberschrift von Block 3 -- die wichtigste Zeile des ganzen Prompts (Birk,
#: 05.09.2026: "Zitate als Few-Shots fuer die Sprechweise je Figur, das ist
#: das Wichtigste"). Sie sagt ausdruecklich, was mit den Zitaten zu tun ist:
#: nicht sie einbauen, sondern die Sprechweise daraus kopieren.
FIGUREN_KOPF = (
    "So spricht jede Figur (aus ihrem Interview, woertlich -- kopiere diese "
    "Sprechweise):"
)


def _figuren_text(conn, chat_id: int) -> str:
    """Block 3: je Figur Beschreibung, Sprachprofil und woertliche Zitate.

    **Das ist der Ersatz fuer die Volltranskripte.** Bis zum 05.09.2026 gingen
    alle Interviews im Wortlaut mit, und das Modell sollte daraus selbst
    heraushoeren, wer wie spricht -- der Probelauf lieferte drei Figuren, die
    alle gleich klangen. Umgekehrt ist es richtig: destilliert je Figur, kurz
    und direkt vor dem Auftrag.

    Eine Figur ohne Sprachprofil steht trotzdem hier, mit ihrer Beschreibung:
    die Sperre (``fehlendes``) laesst einen Lauf ohne Profil zwar gar nicht
    erst los, aber wer ``schreibe()`` direkt ruft (Tests, ein kuenftiger
    Stapellauf), soll keinen namenlosen Prompt bekommen."""
    bloecke = []
    for figur in repo.figuren(conn, chat_id):
        zeilen = [f"{figur['name']}"]
        if figur["beschreibung"]:
            zeilen[0] += f" -- {figur['beschreibung']}"
        if figur["sprachprofil"]:
            zeilen.append(figur["sprachprofil"].strip())
        for satz in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
            if satz.strip():
                zeilen.append(f'  "{satz.strip()}"')
        bloecke.append("\n".join(zeilen))
    if not bloecke:
        return ""
    return FIGUREN_KOPF + "\n\n" + "\n\n".join(bloecke)


#: Ueberschrift von Block 4. Continuity kommt **mechanisch aus der Datenbank**
#: (T5) -- kein Modellaufruf, keine Zusammenfassung: Nummer, Titel, Ort, Wer,
#: Was passiert, Was anders, je frueherer Szene eine Zeile.
CONTINUITY_KOPF = "Was bisher geschah:"


def _szenenfelder_zeilen(conn, zeile, felder) -> list[str]:
    """Die genannten Felder einer Szene als "Name: Wert"-Zeilen, leere weg.
    Die eine Stelle, an der Szenenfelder formatiert werden -- Continuity und
    "Diese Szene" sollen nie auseinanderlaufen."""
    zeilen = []
    for feld in felder:
        if feld == "figuren":
            namen = [f["name"] for f in repo.szene_figuren(conn, zeile["id"])]
            if namen:
                zeilen.append(f"{FELDNAMEN['figuren']}: {', '.join(namen)}")
            continue
        if zeile[feld]:
            zeilen.append(f"{FELDNAMEN[feld]}: {zeile[feld]}")
    return zeilen


#: Was aus einer frueheren Szene mitgeht. Bewusst nicht der Volltext: sechs
#: ausgeschriebene Szenen waeren einige tausend Token, und was die naechste
#: Szene braucht, ist die Lage, nicht der Wortlaut.
_CONTINUITY_FELDER = ("ort", "figuren", "was_passiert", "was_anders")

#: Was in "Diese Szene" steht: alles, was die Gruppe entschieden hat.
_DIESE_SZENE_FELDER = (
    "form", "ort", "zeit", "anlass", "figuren", "was_passiert", "was_anders",
    "kernsaetze", "ton", "titel",
)


def _continuity_text(conn, chat_id: int, nummer: int | None) -> str:
    """Block 4: die frueheren Szenen, mechanisch aus der Datenbank.

    **Nur Szenen mit kleinerer Nummer** -- was danach kommt, ist fuer diese
    Szene keine Vorgeschichte, und eine Szene 5 als "bisher" zu lesen waere
    schlicht falsch. Ohne genannte Nummer (ein Auftrag ohne Szenenzahl) zaehlt
    alles Vorhandene als bisher."""
    zeilen = []
    for szene in repo.hole_szenen(conn, chat_id):
        if szene["nummer"] is None:
            continue
        if nummer is not None and szene["nummer"] >= nummer:
            continue
        kopf = f"Szene {szene['nummer']}"
        if szene["titel"]:
            kopf += f": {szene['titel']}"
        angaben = _szenenfelder_zeilen(conn, szene, _CONTINUITY_FELDER)
        zeilen.append(kopf + ("\n  " + "\n  ".join(angaben) if angaben else ""))
    if not zeilen:
        return ""
    return CONTINUITY_KOPF + "\n" + "\n".join(zeilen)


#: Ueberschrift von Block 6. Der Satz dahinter ist der Kern der Umstellung:
#: die Felder sind bindend, das Modell erfindet sie nicht neu.
DIESE_SZENE_KOPF = (
    "Diese Szene sollst du schreiben. Die Angaben sind bindend -- nichts "
    "ersetzen, nichts hinzuerfinden, was ihnen widerspricht:"
)


def _diese_szene_text(conn, ziel) -> str:
    """Block 6: alle Felder der zu schreibenden Szene, und bei einer
    Ueberarbeitung ihr bisheriger Text.

    Der Volltext geht nur bei einer Ueberarbeitung mit -- also dann, wenn es
    schon einen gibt. Bei einer neuen Szene waere ein fremder Volltext vor
    allem eine Vorlage zum Abschreiben."""
    if ziel is None:
        return ""
    kopf = f"Szene {ziel['nummer']}" if ziel["nummer"] is not None else "Szene"
    zeilen = [DIESE_SZENE_KOPF, kopf]
    zeilen += _szenenfelder_zeilen(conn, ziel, _DIESE_SZENE_FELDER)
    if ziel["volltext"]:
        zeilen.append("")
        zeilen.append("Bisheriger Text dieser Szene, er soll ueberarbeitet werden:")
        zeilen.append(ziel["volltext"])
    return "\n".join(zeilen)


def _verworfen_text(conn, chat_id: int) -> str:
    """Die ``verworfen``-Zeilen des Journals -- damit Verworfenes nicht durch
    die Hintertuer im Szenentext wiederkommt. Das Journal ist der einzige Ort,
    an dem eine Ablehnung samt Grund ueberhaupt festgehalten ist (SPEC § 2)."""
    zeilen = [
        f"- {e['text']}" for e in repo.journal(conn, chat_id) if e["art"] == "verworfen"
    ]
    if not zeilen:
        return ""
    return (
        "Das hat die Gruppe verworfen, es kommt nicht wieder vor:\n" + "\n".join(zeilen)
    )


#: Reihenfolge des Nutzertextes. Wie in kontext.py: stabil nach vorn,
#: entscheidend nach hinten -- was am Ende des Prompts steht, wiegt am
#: schwersten (SPEC § 6.1). Der Auftrag steht deshalb zuletzt, die Angaben zu
#: dieser einen Szene direkt davor.
#:
#: Umgestellt am 05.09.2026 (Birk, nach dem Probelauf): *"Genau andersrum ist
#: richtig: moeglichst praezise destillierte Begriffe und klare Strukturen
#: rein -- was in den Szenen vorkommt, wo, wer, was gesagt wird. Continuity
#: mechanisch."* Vorher standen hier alle Volltranskripte; heraus kam eine
#: Szene in einer Kueche mit erfundenen Figuren.
_REIHENFOLGE = (
    "format_rahmen", "thema", "figuren", "continuity", "verworfen",
    "diese_szene", "auftrag",
)


def _zusammen(bloecke: dict) -> str:
    return "\n\n".join(bloecke[k] for k in _REIHENFOLGE if bloecke.get(k))


def baue_nutzertext(conn, chat_id: int, auftrag: str, ziel=None) -> str:
    """Baut den Nutzertext des Szenen-Aufrufs -- **Struktur statt Transkript**
    (Birk, 05.09.2026).

    Sieben Bloecke, in dieser Reihenfolge: Format & Rahmen; Kernthema (und
    Hauptkonflikt, falls es einen gibt); die Figuren mit Sprachprofil und
    woertlichen Zitaten; Continuity aus der Datenbank; was die Gruppe
    verworfen hat; die Felder DIESER Szene; der Auftrag.

    **Was hier nicht mehr steht:** Volltranskripte und Verdichtungen. Sie
    waren der falsche Reflex -- "der Text soll aus dem Material kommen" hiess
    im Ergebnis, dass das Modell aus 40.000 Token selbst heraussuchen sollte,
    wer wie spricht und was in der Szene vorkommt. Beides steht jetzt
    destilliert da: die Sprechweise als Sprachprofil je Figur (T3), die
    Szenenlage als Felder (T2).

    Damit entfaellt auch der Deckel-Mechanismus: alle Bloecke sind kurz, es
    gibt nichts mehr, was gekuerzt werden muesste. Jeder Block faellt weg,
    solange seine Daten leer sind -- dasselbe datengetriebene Prinzip wie in
    ``kontext.baue``."""
    nummer = ziel["nummer"] if ziel is not None else nummer_aus_auftrag(auftrag)
    bloecke = {
        "format_rahmen": _format_rahmen_text(conn, chat_id),
        "thema": _thema_text(conn, chat_id),
        "figuren": _figuren_text(conn, chat_id),
        "continuity": _continuity_text(conn, chat_id, nummer),
        "verworfen": _verworfen_text(conn, chat_id),
        "diese_szene": _diese_szene_text(conn, ziel),
        "auftrag": f"Euer Auftrag:\n{auftrag.strip()}",
    }
    return _zusammen(bloecke)


# ---------------------------------------------------------------------------
# Antwort lesen
# ---------------------------------------------------------------------------


def _kopfwert(zeile: str, schluessel: str) -> str | None:
    """Liest ``TITEL: ...`` bzw. ``KURZ: ...`` aus einer Zeile, oder None.

    Fuehrende Sternchen, Rauten und Backticks werden abgeraeumt, bevor
    verglichen wird: das Modell setzt seine Kopfzeilen gern in Markdown
    (``**TITEL:** Am Bahnhof``), und daran soll das Auslesen nicht scheitern."""
    nackt = zeile.strip().lstrip("*#`> ").strip()
    if not nackt.upper().startswith(schluessel):
        return None
    rest = nackt[len(schluessel):].lstrip("*` ")
    if not rest.startswith(":"):
        return None
    return rest[1:].strip().strip("*` ").strip()


def zerlege(text: str) -> tuple[str | None, str | None, str]:
    """Trennt ``TITEL:``/``KURZ:`` vom eigentlichen Szenentext.

    Liefert ``(titel, kurzbeschreibung, volltext)``; die ersten beiden koennen
    None sein. Fehlt der Kopf ganz, ist der gesamte Text die Szene -- ein
    fehlender Titel ist kein Grund, einen fertigen Szenentext wegzuwerfen. Der
    Aufrufer setzt dann 'Szene N' ein."""
    zeilen = text.splitlines()
    titel = kurz = None
    ab = 0
    for i, zeile in enumerate(zeilen[:_KOPFZEILEN]):
        if not zeile.strip():
            ab = i + 1
            continue
        wert = _kopfwert(zeile, "TITEL")
        if wert is not None and titel is None:
            titel, ab = wert, i + 1
            continue
        wert = _kopfwert(zeile, "KURZ")
        if wert is not None and kurz is None:
            kurz, ab = wert, i + 1
            continue
        break

    volltext = "\n".join(zeilen[ab:]).strip()
    return (titel or None), (kurz or None), volltext


def _vorschau(nummer: int, titel: str, volltext: str) -> str:
    """Titel, die ersten VORSCHAU_ZEILEN nichtleeren Zeilen, der Verweis auf
    die Gruppenseite. Nicht der ganze Text: ein bis drei Seiten Dialog in
    einer Telegram-Nachricht waeren auf dem Handy unlesbar, und die Szene
    stuende danach mitten im Verlaufsfenster jedes weiteren Aufrufs."""
    zeilen = [z for z in volltext.splitlines() if z.strip()][:VORSCHAU_ZEILEN]
    return "\n".join([f"Szene {nummer}: {titel}", "", *zeilen, "", _TEXT_VOLLSTAENDIG])


# ---------------------------------------------------------------------------
# Der Lauf
# ---------------------------------------------------------------------------


def _sende_und_merke(conn, tg, e, chat_id: int, text: str) -> None:
    """Schickt eine Zeile und schreibt sie als Bot-Nachricht mit -- wie
    ``ablauf.antworte`` und ``erkenner._melde_interviewmodus``, damit sie im
    Verlaufsfenster des naechsten Gespraechszugs steht. Ein Fehlschlag beim
    Senden wird nur geloggt: er darf den Szenenlauf nicht mitreissen."""
    try:
        message_id = tg.sende(chat_id, text)
        repo.merke_nachricht(
            conn, chat_id, message_id, getattr(e, "bot_name", None), 1, "text",
            text, repo._jetzt(),
        )
    except Exception:
        log.exception("Szenen-Nachricht fehlgeschlagen, chat_id=%s", chat_id)


def _sende_usa_angebot(conn, tg, e, chat_id: int) -> None:
    """Schickt das USA-Angebot MIT den beiden Einwilligungsknoepfen
    (05.09.2026).

    Der Text geht wie bisher durch ``_sende_und_merke`` -- er soll im
    Verlaufsfenster stehen. Die Knoepfe haengen an einer zweiten, kurzen
    Nachricht darunter, statt an der ersten: ``_sende_und_merke`` merkt sich
    die Nachricht ueber ``tg.sende``, und daraus eine Sendung mit Tastatur zu
    machen haette den Merkweg fuer alle Szenen-Nachrichten umgebaut. Zwei
    Nachrichten sind hier der kleinere Eingriff -- und die Gruppe sieht die
    Knoepfe direkt unter der Frage.

    Ein Fehlschlag beim Anhaengen der Knoepfe darf den Szenenlauf nicht
    mitreissen: der Angebotstext steht dann trotzdem, und ``/szene usa ja``
    bleibt der Weg (dieselbe Fehlerhaltung wie in ``_sende_und_merke``)."""
    # Import erst hier: ``knoepfe`` greift seinerseits auf ``szene`` zu
    # (FORMEN, planungszeile) -- ein Modulimport oben waere ein Zyklus.
    # Derselbe Grund wie beim befehle-Import in knoepfe._wirke.
    from interview_theater import knoepfe

    _sende_und_merke(conn, tg, e, chat_id, _TEXT_ANGEBOT_USA)
    try:
        knoepfe.biete_szene_usa(conn, tg, chat_id)
    except Exception:
        log.exception("USA-Knoepfe fehlgeschlagen, chat_id=%s", chat_id)


def schreibe(conn, tg, klm, e, chat_id: int, auftrag: str) -> int:
    """Der eigentliche Szenen-Aufruf: Prompt bauen, Modell fragen, Szene
    speichern, Journal schreiben, Vorschau in die Gruppe schicken. Liefert
    die Nummer der geschriebenen Szene.

    Laeuft im Thread aus ``starte()``; wer sie direkt aufruft (Tests, ein
    kuenftiger Stapellauf), bekommt sie synchron und muss sich selbst um die
    Sperre kuemmern. Fehler fliegen heraus -- ``_lauf()`` faengt sie."""
    ziel = ziel_fuer(conn, chat_id, auftrag)
    nummer = ziel["nummer"]

    nutzer = baue_nutzertext(conn, chat_id, auftrag, ziel)
    if szene_claude.ist_aktiv(e, conn, chat_id):
        antwort = szene_claude.prosa(
            conn, e, getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
            chat_id, systemanweisung(ziel["form"]),
            nutzer, ART, timeout=TIMEOUT_S,
        )
    else:
        antwort = klm.prosa(
            chat_id, systemanweisung(ziel["form"]),
            nutzer, ART, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
        )

    titel, kurz, volltext = zerlege(antwort)
    if not volltext:
        raise SzeneFehler("Antwort des Sprachmodells enthielt keinen Szenentext")

    # Immer ein UPDATE: die Szene existiert an dieser Stelle bereits, weil
    # ``ziel_fuer`` sie notfalls angelegt hat. Die Planungsfelder bleiben
    # dabei stehen -- ``aktualisiere_szene`` fasst nur Titel, Kurzform und
    # Volltext an.
    repo.aktualisiere_szene(conn, ziel["id"], titel or ziel["titel"], kurz, volltext)

    titel = titel or f"Szene {nummer}"
    # Das Journal haelt fest, was gilt (SPEC § 2) -- eine geschriebene Szene
    # ist eine Festlegung der Gruppe, kein Vorschlag. Der Eintrag steht
    # danach im Gespraechs-Prompt und im Szenen-Prompt jedes weiteren Laufs.
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Szene {nummer} geschrieben: {titel}",
        quelle="szene",
    )
    _sende_und_merke(conn, tg, e, chat_id, _vorschau(nummer, titel, volltext))
    return nummer


def _lauf(conn, tg, klm, e, chat_id: int, auftrag: str, sperre: threading.Lock) -> None:
    """Der Thread-Rumpf: ``schreibe()`` mit Fehlerbehandlung und garantierter
    Freigabe der Sperre. Bliebe sie bei einem Fehlschlag liegen, koennte die
    Gruppe fuer den Rest des Workshops keine Szene mehr schreiben lassen."""
    try:
        schreibe(conn, tg, klm, e, chat_id, auftrag)
    except Exception:
        log.exception("Szenen-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "szene_fehlgeschlagen",
                "Szenen-Aufruf fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zum Szenen-Fehler nicht schreibbar, chat_id=%s", chat_id)
        # Anders als beim Absichtserkenner erfaehrt die Gruppe davon: sie hat
        # gerade die Ankuendigung bekommen und wartet (SPEC § 11.1).
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_FEHLER)
    finally:
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, auftrag: str) -> threading.Thread | None:
    """Prueft, kuendigt an und gibt den Aufruf an einen eigenen Thread ab.

    Liefert den gestarteten Thread, oder None, wenn nichts angestossen wurde
    (leerer Auftrag, es laeuft schon eine Szene fuer diese Gruppe, oder die
    Sperre unten hat gegriffen). Der Rueckgabewert ist fuer Tests da, die auf
    das Ende warten wollen -- im Betrieb interessiert sich niemand dafuer, das
    ist der Sinn der Sache.

    **Die Sperre (05.09.2026).** Fehlt ein Pflichtfeld oder hat eine Figur
    dieser Szene kein Sprachprofil, gibt es **keinen Aufruf** -- stattdessen
    eine Nachricht, die sagt, was fehlt. Damit wird ``szene_schreiben`` zu
    Pruefung plus gegebenenfalls einer Rueckfrage und nie mehr zu "Die Szene
    ist mir nicht gelungen": ein Modell, dem Ort und Besetzung fehlen,
    scheitert nicht, es erfindet welche. Genau das war der Probelauf.

    Die Pruefung steht **vor** der Ankuendigung und vor der Sperre je
    chat_id: eine Gruppe, der etwas fehlt, soll keine Zeile bekommen, in der
    steht, dass jetzt eine Minute lang etwas laeuft."""
    auftrag = (auftrag or "").strip()
    if not auftrag:
        return None

    ziel = ziel_fuer(conn, chat_id, auftrag)
    fehlt = sperrtext(conn, ziel)
    if fehlt:
        _sende_und_merke(conn, tg, e, chat_id, fehlt)
        return None

    # Birk 05.09.: der Wechsel aufs US-Modell wird VORGESCHLAGEN, mit Warnung
    # und Bestaetigung -- nicht vom Betreiber gesetzt. Solange die Gruppe
    # nicht geantwortet hat, wird keine Szene geschrieben: die Frage steht,
    # und "sagt ja oder nein" ist die einzige Rueckfrage, die hier erlaubt
    # ist. Ein Nein heisst Infomaniak, und der Bot fragt nicht wieder.
    if szene_claude.angebot_faellig(e, conn, chat_id):
        repo.merke_szene_usa_angeboten(conn, chat_id, auftrag)
        _sende_usa_angebot(conn, tg, e, chat_id)
        return None
    if szene_claude.wartet_auf_antwort(e, conn, chat_id):
        # Nach USA_ERINNERUNGEN_MAX vergeblichen Anlaeufen wird nicht weiter
        # erinnert, sondern in der Schweiz geschrieben: eine Einwilligung, die
        # nicht als solche erkannt wird, darf die Arbeit nicht dauerhaft
        # blockieren (siehe USA_ERINNERUNGEN_MAX). Das Schweizer Modell ist
        # dabei die vorsichtige Seite -- es gehen keine Daten in die USA, und
        # die Gruppe hat der Uebermittlung nie zugestimmt.
        erinnerungen = _usa_erinnerungen.get(chat_id, 0) + 1
        _usa_erinnerungen[chat_id] = erinnerungen
        if erinnerungen <= USA_ERINNERUNGEN_MAX:
            repo.merke_szene_usa_angeboten(conn, chat_id, auftrag)
            _sende_und_merke(conn, tg, e, chat_id, _TEXT_USA_ERINNERUNG)
            return None
        repo.setze_szene_usa(conn, chat_id, False)
        _usa_erinnerungen.pop(chat_id, None)
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_USA_KEINE_ANTWORT)

    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_BESETZT)
        return None

    if szene_claude.ist_aktiv(e, conn, chat_id):
        _sende_und_merke(conn, tg, e, chat_id, _TEXT_WARNUNG_USA)
    _sende_und_merke(conn, tg, e, chat_id, _TEXT_ANGEKUENDIGT)
    # Hinweis, keine Sperre: die Szene wird trotzdem geschrieben.
    hinweis = neue_figuren_hinweis(conn, chat_id, ziel)
    if hinweis:
        _sende_und_merke(conn, tg, e, chat_id, hinweis)
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, auftrag, sperre), daemon=True,
    )
    try:
        thread.start()
    except Exception:
        # Kommt der Thread nicht hoch, gibt ihn auch niemand mehr frei --
        # dann bliebe die Sperre bis zum Prozessende liegen.
        sperre.release()
        raise
    return thread

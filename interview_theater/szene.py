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
import os
import re
import threading

import httpx

from interview_theater import anweisungen, repo, strom, szene_claude, workshop

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

#: Nur in den ersten paar Zeilen der Modellantwort wird nach TITEL/KURZ
#: gesucht -- weiter unten waere ein "TITEL:" Teil der Szene, nicht ihr Kopf.
_KOPFZEILEN = 6

_TEXT_ANGEKUENDIGT = "Ich schreibe die Szene aus, das dauert eine Minute."
_TEXT_BESETZT = "Ich schreibe gerade noch an einer Szene, gleich."
#: Die Chronologie-Sperre in einer Zeile (05.09.2026, Testgruppe 22:05: Szene
#: 3 wurde vor Szene 1 und 2 geschrieben). Kein Sperrtext, keine Rueckfrage --
#: der Bot sagt, was er stattdessen tut, und tut es.
_TEXT_ERST_FRUEHERE = (
    "Szene {nummer} kommt nach Szene {vorher} - die schreibe ich zuerst."
)
_TEXT_FEHLER = (
    "Die Szene ist mir nicht gelungen. Sagt es nochmal, dann versuche ich es neu."
)
#: Der fertige Szenentext im Chat: Kopf, Leerzeile, Text.
_TEXT_SZENENTEXT = "Szene {nummer}: {titel}\n\n{volltext}"

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
    "US-Modell ja oder nein? Tippt einen der beiden Knoepfe an."
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
    "die Szene deshalb in der Schweiz. Wollt ihr es doch anders, sagt es mir."
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


def laeuft(chat_id: int) -> bool:
    """Laeuft fuer diese Gruppe gerade ein Szenenlauf?

    Die Sperre ist ohnehin da (sie verhindert zwei gleichzeitige Laeufe); hier
    wird sie nur gelesen. Der Gespraechszug fragt danach: waehrend ein Auftrag
    laeuft, kommentiert der Gespraechs-Bot ihn nicht (05.09.2026, Testgruppe
    22:05 -- der Bot fragte parallel zu den Systemzeilen des Szenen-Threads
    'wollt ihr die Reihenfolge behalten?' und 'Szene 1 und 2 fehlen -- wollt
    ihr die vorher?').

    Ohne Sperre fuer diese chat_id laeuft nichts -- sie wird erst beim ersten
    Auftrag angelegt, und ``_sperre_fuer`` wuerde hier eine anlegen, die nie
    jemand braucht."""
    sperre = _sperren.get(chat_id)
    return bool(sperre is not None and sperre.locked())


#: Die Formen, die eine Szene haben kann -- je eine mit eigenem Regelblock
#: (``prompts/formen/<name>.md``). Die Reihenfolge ist die der Knopfleiste
#: (``knoepfe.biete_szenenform``): erst die Sprechformen, dann die
#: musikalischen.
#:
#: Ein "Format des Stuecks" gibt es seit dem 05.09.2026 abends nicht mehr
#: (Birk: "wir wollen immer zuerst ein Textbuch; wie wir inszenieren, ist
#: unser Ding") -- die Form haengt deshalb ausschliesslich an der EINZELNEN
#: Szene und ist dort Pflichtfeld. "stumm" ist gestrichen: ein stummes Bild
#: ist Inszenierung, nicht Textbuch.
#:
#: **Seit dem 06.09.2026 kommt die Liste aus dem Workshop-Profil**
#: (``workshop/<name>/formen.toml``, sonst ``workshop.VORGABE_FORMEN`` mit
#: genau den fuenf Werten, die vorher hier standen). ``FORMEN`` und
#: ``FORM_STICHWOERTER`` bleiben als Namen bestehen und werden ueber
#: ``__getattr__`` bei jedem Zugriff frisch beantwortet -- nicht einmal beim
#: Import: zwei Profile in einem Prozess bekaemen sonst dieselbe Liste
#: (D.5 der Analyse).


def __getattr__(name: str):
    """``szene.FORMEN`` und ``szene.FORM_STICHWOERTER`` aus dem aktiven
    Profil. Als Modul-``__getattr__`` (PEP 562), damit die rund zwanzig
    Leser im Code und in den Tests unveraendert weiterlesen koennen."""
    if name == "FORMEN":
        return workshop.formen()
    if name == "FORM_STICHWOERTER":
        return workshop.form_stichwoerter()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

#: Die Formvariante der Phase 6 (06.09.2026, 10:30, Birk): erst entsteht die
#: Szene als **Geschichte**, wie man sie in einem Buch liest -- kein
#: Theaterskript. Sie steht bewusst NICHT in ``FORMEN``: die Gruppe waehlt
#: sie nie, und sie taucht auf keinem Formknopf auf. Sie ist der Schritt
#: davor, den der Code setzt.
PROSA = "prosa"

#: Die Phase, in der die Szenen als Geschichte entstehen (06.09.2026,
#: 10:30). Ab Phase 7 (\"Feinschliff\") wird die Prosa in die gewaehlte Form
#: uebersetzt.
PHASE_PROSA = 6


def schreibt_prosa(conn, chat_id: int) -> bool:
    """Schreibt dieser Lauf eine **Geschichte** (Phase 6) oder einen
    **Theatertext** (Phase 7 und alles danach)?

    Die eine Stelle, an der die Verzweigung haengt -- Systemanweisung,
    Zielspalte und Vorlage lesen sie alle hier ab. An der Phase und nicht an
    einem eigenen Schalter: die Gruppe entscheidet mit dem Phasenwechsel,
    dass die Geschichten stehen (``phasen.voraussetzungen[7]``).

    Faellt die Phase nicht zu lesen (fehlende Zeile, alte Datenbank), gilt
    Prosa: eine Gruppe, die zu frueh einen Theatertext bekommt, verliert den
    Schritt, um den es hier geht."""
    from interview_theater import phasen

    try:
        return phasen.aktuelle(conn, chat_id) <= PHASE_PROSA
    except Exception:  # pragma: no cover -- Verteidigung, kein Weg
        log.exception("Phase fuer den Szenenlauf nicht lesbar, chat_id=%s", chat_id)
        return True

#: Woerter, unter denen eine Form gemeint sein kann -- wie
#: ``phasen.STICHWOERTER``: das Feld ``szene.form`` ist frei (die Gruppe
#: entscheidet, nicht der Code), und "gesungen" muss trotzdem beim Lied
#: landen. Verglichen wird in beide Richtungen, deshalb genuegen Wortstaemme.
#: Steht seit dem 06.09.2026 in ``formen.toml``; siehe ``__getattr__`` oben.


def formdatei(form: str | None) -> str:
    """Uebersetzt das freie Feld ``szene.form`` in den Namen eines
    Regelblocks (``prompts/formen/<name>.md``). Rueckfall bei leerer oder
    unbekannter Form: ``dialog``.

    Der Rueckfall ist eine Entscheidung, kein Notbehelf: eine unbekannte Form
    ("Bewegungsszene") ist im Zweifel gesprochenes Theater, und ein Prompt
    ohne jeden Formenblock haette gar keine Dramaturgieregeln mehr -- die
    stehen seit dem 05.09.2026 alle in ``prompts/formen/``. ``dialog.md``
    traegt seit dem Abend des 05.09.2026 den am Herkules-Textbuch gemessenen
    Regelblock.

    **Es gibt keinen Format-Parameter mehr** (Birk, 05.09.2026 abends): das
    Format des Stuecks ist keine Frage mehr, die der Bot stellt. Was zaehlt,
    ist die Form JE SZENE.

    **Die Rueckfall-Form wird zuletzt geprueft**, nicht in
    Listenreihenfolge: das Wort "Szene" steht in fast jeder Formangabe, und
    Dialog ist ohnehin der Rueckfall -- er braucht keinen Vorrang, er
    braucht den Rest. Welche Form der Rueckfall ist, sagt seit dem
    06.09.2026 das Profil (``formen.toml``, ``vorgabe``)."""
    rueckfall = workshop.form_vorgabe()
    text = (form or "").strip().lower()
    if not text:
        return rueckfall
    stichwoerter = workshop.form_stichwoerter()
    for name in workshop.formen():
        if name == rueckfall:
            continue
        for stichwort in stichwoerter.get(name, ()):
            if stichwort in text:
                return name
    return rueckfall


def systemanweisung(form: str | None = None, stil: str | None = None) -> str:
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
    Neustart, beim naechsten Szenen-Auftrag.

    **Die Prosafassung (Phase 6) ist die Ausnahme** (06.09.2026, 10:30,
    Birk): dort gilt ``prompts/formen/prosa.md`` ALLEIN. Weder ``szene.md``
    (Repliken, Regieanweisungen, Sprecherzeilen) noch ein Herkules-Regelblock
    gehen mit -- sie beschreiben Sprechtheater, und hier entsteht eine
    Geschichte. Die Tells bleiben: sie sind Sprachhygiene und gelten fuer
    jeden Text.

    **Der Stil-Block** (06.09.2026, 12:50, Birk) haengt hinter dem
    Formen-Regelblock und VOR den Tells: er verschiebt, wie der Text klingt,
    und kollidiert er mit der Form, gilt die Formdatei -- deshalb steht er
    dahinter. Er kommt nur bei ``form != prosa`` mit: die Prosafassung ist
    eine Geschichte, kein Buehnentext, und ein Rap-Mass darauf waere eine
    Regel ueber eine Textsorte, die es hier nicht gibt."""
    if (form or "").strip().lower() == PROSA:
        return "\n\n".join(
            [anweisungen.hole(f"formen/{PROSA}"), anweisungen.hole("theater-tells")]
        )
    teile = [anweisungen.hole("szene")]
    regeln = anweisungen.hole_optional(f"formen/{formdatei(form)}")
    if regeln and regeln.strip():
        teile.append(regeln.strip())
    from interview_theater import stile as stile_modul

    stilblock = stile_modul.regelblock(stil)
    if stilblock:
        teile.append(stilblock)
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

#: Dasselbe auf Englisch (Karte A1, K5): "write scene 2", "scene no. 4".
#: Ausgabeparser -- beide werden probiert, deutsch zuerst.
_NUMMER_EN = re.compile(r"\bscene\s*(?:no\.?|number)?\s*(\d{1,3})\b", re.IGNORECASE)


def nummer_aus_auftrag(auftrag: str) -> int | None:
    """Liest die Szenennummer aus dem Auftrag, oder None.

    Nennt der Auftrag eine Nummer, zu der es schon eine Szene gibt, wird
    diese ueberschrieben (der Normalfall "Szene 2 nochmal, aber kuerzer");
    sonst entsteht eine neue."""
    for muster in (_NUMMER, _NUMMER_EN):
        treffer = muster.search(auftrag or "")
        if treffer:
            return int(treffer.group(1))
    # Eine nackte Zahl ("/szene 1" kommt hier als "1" an) meint die Szene mit
    # dieser Nummer. Live-Fall Testgruppe 05.09. 22:20: "/szene 1" schrieb
    # Szene 3, weil "1" als "keine Nummer" gelesen wurde und dann die zuletzt
    # bearbeitete Szene dran war.
    nackt = re.fullmatch(r"\s*(\d{1,3})\s*", auftrag or "")
    return int(nackt.group(1)) if nackt else None


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
#: Gruppe: das Ergebnis von Phase 5 (Rahmen). Ohne ihn ist nicht entschieden,
#: WORIN das Stueck spielt -- das Modell erfindet es dann je Szene neu. Birk
#: 05.09.2026, nachdem eine Szene ohne Rahmen geschrieben wurde.
#:
#: ``format`` stand hier bis zum Abend des 05.09.2026 daneben und ist raus:
#: das Format ist keine Frage mehr (die Spalte bleibt in der Datenbank, wird
#: aber fuer keine Entscheidung mehr gelesen). Was jede Szene braucht, ist
#: ihre eigene ``form`` -- die steht in ``PFLICHTFELDER``.
ARBEITSSTAND_PFLICHTFELDER = ("rahmen",)

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

#: Dieselben Aliase auf Englisch (Karte A1, K5) -- Ziel sind die deutschen
#: Spaltennamen (Protokoll). ``feldname`` sucht erst deutsch, dann englisch.
#: Abweichung vom Plan: "summary" zeigt auf ``kurzbeschreibung`` (die Spalte,
#: auf die das deutsche "kurz" zeigt), weil es keine Spalte ``kurz`` gibt.
FELD_ALIASE_EN = {
    "place": "ort",
    "location": "ort",
    "time": "zeit",
    "occasion": "anlass",
    "characters": "figuren",
    "cast": "figuren",
    "who": "figuren",
    "what happens": "was_passiert",
    "plot": "was_passiert",
    "what's different": "was_anders",
    "what is different": "was_anders",
    "key lines": "kernsaetze",
    "tone": "ton",
    "title": "titel",
    "summary": "kurzbeschreibung",
}

#: Trennt die Angaben einer Planung. Bewusst die Pipe und nicht das Komma:
#: in "figuren: Mira, Pola, Pal" und in einem Handlungssatz stehen Kommas.
PLANUNG_TRENNER = "|"

#: "Szene 1", "szene nr. 2", "2" -- der Kopf einer Planungsangabe.
_PLANUNG_NUMMER = re.compile(r"^\s*(?:szene\s*(?:nr\.?|nummer)?\s*)?(\d{1,3})\s*$",
                             re.IGNORECASE)

#: Dasselbe mit "scene" (Karte A1, K5): "Scene 1", "scene no. 2".
_PLANUNG_NUMMER_EN = re.compile(
    r"^\s*(?:(?:szene|scene)\s*(?:nr\.?|nummer|no\.?|number)?\s*)?(\d{1,3})\s*$",
    re.IGNORECASE)


def feldname(wort: str) -> str | None:
    """Uebersetzt ein Wort in einen Szenenfeldnamen, oder None.

    Die eine Stelle, an der ``FELD_ALIASE`` ausgewertet wird -- der Befehl
    ``/szene <n> <feld> <wert>`` und die Erkennerangabe ``szene_planen``
    sollen dieselben Woerter verstehen. Erst deutsch, dann englisch
    (``FELD_ALIASE_EN``)."""
    schluessel = (wort or "").strip().lower()
    return FELD_ALIASE.get(schluessel) or FELD_ALIASE_EN.get(schluessel)


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
        kopfteil = teil.split(":", 1)[0]
        treffer = (_PLANUNG_NUMMER.match(kopfteil)
                   or _PLANUNG_NUMMER_EN.match(kopfteil))
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


#: Die Bausteine, aus denen Szenenkoepfe und Aufzaehlungen im Chat und im
#: Szenen-Prompt entstehen (Karte A1: ueber ``T`` gelesen).
_UND = " und "
_SZENE_MIT_NUMMER = "Szene {nummer}"
_SZENE_OHNE_NUMMER = "Szene"
_DIE_SZENE = "die Szene"


def _und(namen: list[str]) -> str:
    """"Mira, Pola und Pal" -- eine Aufzaehlung, wie man sie spricht."""
    if len(namen) <= 1:
        return "".join(namen)
    return ", ".join(namen[:-1]) + T._UND + namen[-1]


def _szenenkopf(nummer) -> str:
    """"Szene 3" -- oder "Szene", wenn die Szene keine Nummer hat."""
    if nummer is None:
        return T._SZENE_OHNE_NUMMER
    return T._SZENE_MIT_NUMMER.format(nummer=nummer)


def _kopf(zeile) -> str:
    if zeile["nummer"] is not None:
        return T._SZENE_MIT_NUMMER.format(nummer=zeile["nummer"])
    return T._DIE_SZENE


#: Wie das Setting (``arbeitsstand.rahmen``) auf die Szenenfelder abgebildet
#: wird (06.09.2026, Birk 12:00/12:05). Das Setting IST Ort, Zeit und Anlass
#: des Abends -- eine Szene danach noch einmal nach dem Ort zu fragen ("fehlt
#: noch: Ort") war eine Frage nach etwas, das schon dasteht.
_RAHMEN_FELD = re.compile(
    r"(?:^|[,;\n])\s*(Ort|Zeit|Anlass)\s*:\s*([^,;\n]+)", re.IGNORECASE
)

#: Dasselbe auf Englisch (Karte A1, K5); ``_RAHMEN_ZUORDNUNG_EN`` bildet auf
#: die deutschen Spaltennamen ab.
_RAHMEN_FELD_EN = re.compile(
    r"(?:^|[,;\n])\s*(Place|Time|Occasion)\s*:\s*([^,;\n]+)", re.IGNORECASE
)
_RAHMEN_ZUORDNUNG_EN = {"place": "ort", "time": "zeit", "occasion": "anlass"}


def rahmenfelder(rahmen: str | None) -> dict[str, str]:
    """Ort, Zeit und Anlass aus dem Setting-Freitext.

    Zwei Formen, beide gemessen: ``"Ort: Treppenhaus, Zeit: nachts, Anlass:
    eine Party"`` wird auseinandergenommen; alles andere ist als Ganzes der
    **Ort** -- ein Setting ohne Doppelpunkte ("Ein Treppenhaus, nachts")
    beschreibt genau das, und geraten wird an ihm nichts."""
    roh = (rahmen or "").strip()
    if not roh:
        return {}
    treffer = {
        name.lower(): wert.strip()
        for name, wert in _RAHMEN_FELD.findall(roh)
        if wert.strip()
    }
    if treffer:
        return treffer
    treffer = {
        _RAHMEN_ZUORDNUNG_EN[name.lower()]: wert.strip()
        for name, wert in _RAHMEN_FELD_EN.findall(roh)
        if wert.strip()
    }
    if treffer:
        return treffer
    return {"ort": roh}


def uebernimm_rahmen(conn, chat_id: int, szene_id: int) -> None:
    """Schreibt Ort, Zeit und Anlass aus dem Setting in eine Szene -- nur,
    wo das Feld noch leer ist.

    Additiv wie ``repo.setze_szenenfeld``: was die Gruppe je Szene selbst
    gesagt hat, bleibt stehen."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    felder = rahmenfelder(stand["rahmen"] if stand else None)
    if not felder:
        return
    zeile = repo.hole_szene(conn, szene_id)
    if zeile is None:
        return
    for feld, wert in felder.items():
        if feld in ("ort", "zeit", "anlass") and not (zeile[feld] or "").strip():
            repo.setze_szenenfeld(conn, szene_id, feld, wert)


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
    # **In Phase 6 ist die Form kein Pflichtfeld** (06.09.2026, 10:30): dort
    # entsteht die Szene als Geschichte, und welche Form daraus wird -- Dialog,
    # Monolog, Rap, Lied --, entscheidet die Gruppe erst im Feinschliff. Eine
    # Sperre auf ein Feld, nach dem gar nicht mehr gefragt wird, waere eine
    # Sackgasse.
    pflicht = tuple(
        f for f in PFLICHTFELDER
        if not (f == "form" and schreibt_prosa(conn, ziel["chat_id"]))
    )
    for feld in pflicht:
        if feld == "figuren":
            if not figuren:
                felder.append(feld)
        elif not ziel[feld]:
            felder.append(feld)
    # **Das Setting ist die Vorgabe fuer ort/zeit/anlass** (06.09.2026, Birk
    # 12:00): steht ein Rahmen, ist der Ort entschieden -- "fehlt noch: Ort"
    # waere eine Frage nach etwas, das die Gruppe schon gesagt hat. Pflicht
    # bleibt allein ``was_passiert``.
    stand_vorab = repo.hole_arbeitsstand(conn, ziel["chat_id"])
    if rahmenfelder(stand_vorab["rahmen"] if stand_vorab else None):
        felder = [f for f in felder if f != "ort"]
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
        feldnamen = T.FELDNAMEN
        teile.append(T._TEXT_FEHLENDE_FELDER.format(
            kopf=_kopf(ziel), felder=", ".join(feldnamen[f] for f in felder),
        ))
    if ohne_profil:
        vorlage = (
            T._TEXT_OHNE_PROFIL_EINE if len(ohne_profil) == 1
            else T._TEXT_OHNE_PROFIL_MEHRERE
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
    vorlage = T._TEXT_NEUE_FIGUR_EINE if len(neue) == 1 else T._TEXT_NEUE_FIGUR_MEHRERE
    return vorlage.format(namen=_und(neue), nummer=ziel["nummer"])


def planungszeile(conn, zeile) -> str:
    """Eine Szenenplanung in einer Zeile, fuer eine Nachricht an die Gruppe:
    ``"Szene 1 · Dialog · Polizeikessel · Mira, Pola, Pal"``.

    Nur die Felder, die es gibt -- datengetrieben wie alles andere. Sie ist
    absichtlich kuerzer als der Prompt-Block aus ``_diese_szene_text``: im
    Chat soll die Gruppe auf einen Blick erkennen, welche Szene gemeint ist,
    nicht die ganze Planung noch einmal lesen."""
    nummer = zeile["nummer"]
    stuecke = [_szenenkopf(nummer)]
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


def kleinste_offene(conn, chat_id: int, vor: int | None = None) -> int | None:
    """Die kleinste (nicht entfernte) Szene ohne Volltext, oder None.

    ``vor`` grenzt auf Szenen mit kleinerer Nummer ein -- genau das, was die
    Chronologie-Sperre braucht: gibt es vor der angefragten Szene noch eine
    ungeschriebene, ist die dran.

    "Offen" heisst hier **ohne Volltext**, nicht "nicht abgenommen": eine
    geschriebene, aber noch nicht abgenommene Szene ist geschrieben, und ihre
    Ueberarbeitung darf die naechste nicht aufhalten.

    In Phase 6 zaehlt die **Prosafassung** als geschrieben (06.09.2026,
    10:30): dort ist die Geschichte das Ergebnis, und die Chronologie-Sperre
    haengt an dem, was die Phase gerade herstellt."""
    prosa_lauf = schreibt_prosa(conn, chat_id)
    for szene in repo.hole_szenen(conn, chat_id):
        if szene["nummer"] is None:
            continue
        if vor is not None and szene["nummer"] >= vor:
            continue
        geschrieben = (
            _prosa_von(szene) if prosa_lauf else (szene["volltext"] or "").strip()
        )
        if not geschrieben:
            return szene["nummer"]
    return None


def vorzuziehen(conn, chat_id: int, ziel) -> int | None:
    """Die Nummer der Szene, die VOR ``ziel`` geschrieben werden muss -- oder
    None, wenn ``ziel`` selbst dran ist (Chronologie-Sperre, 05.09.2026).

    Der Anlass (Testgruppe 05.09. 22:05): Szene 3 wurde geschrieben, waehrend
    Szene 1 und 2 leer waren. Ein Szenentext, der an nichts anschliesst, ist
    keine dritte Szene, sondern eine erste an falscher Stelle -- und der
    Volltext-Block (``_continuity_text``) haette nichts zu zeigen.

    **Eine bereits geschriebene Szene bleibt jederzeit ueberarbeitbar**: hat
    ``ziel`` einen Volltext, ist der Auftrag eine Neufassung und keine
    Vorwegnahme. Nur eine noch leere Szene wird zurueckgestellt."""
    if ziel is None or ziel["nummer"] is None:
        return None
    fertig = (
        _prosa_von(ziel) if schreibt_prosa(conn, chat_id)
        else (ziel["volltext"] or "").strip()
    )
    if fertig:
        return None
    return kleinste_offene(conn, chat_id, vor=ziel["nummer"])


def ziel_fuer(conn, chat_id: int, auftrag: str, chronologisch: bool = True):
    """Die Szene, die dieser Auftrag meint -- und wenn es sie noch nicht gibt,
    eine neue, leere mit dieser Nummer.

    ``chronologisch`` (Vorgabe an): fehlt vor der gemeinten Szene noch der
    Volltext einer frueheren, liefert diese Funktion **die frueheste offene**
    statt der gemeinten (``vorzuziehen``). Damit gilt die Sperre auf jedem
    Weg -- Befehl, Knopf, Erkenner -- und ``schreibe()`` und ``starte()``
    kommen nie zu verschiedenen Zielen. ``chronologisch=False`` gibt es fuer
    Aufrufer, die nur wissen wollen, WOVON die Gruppe gesprochen hat.

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
    if ziel is None:
        if nummer is None:
            letzte = repo.hole_letzte_szene(conn, chat_id)
            ziel = letzte
        if ziel is None:
            ziel = repo.hole_szene(
                conn, repo.stelle_szene_sicher(conn, chat_id, nummer or 1)
            )
    if not chronologisch:
        return ziel
    vorher = vorzuziehen(conn, chat_id, ziel)
    if vorher is None:
        return ziel
    return repo.hole_szene(conn, repo.stelle_szene_sicher(conn, chat_id, vorher))


# ---------------------------------------------------------------------------
# Prompt-Zusammenbau (eigener, nicht kontext.baue)
# ---------------------------------------------------------------------------


def _format_rahmen_text(conn, chat_id: int) -> str:
    """Block 1: der Rahmen (Phase 5).

    Zuerst, weil er ueber allem steht: er sagt, worin das Ganze spielt.

    Das Format des Stuecks stand hier bis zum Abend des 05.09.2026 darueber
    und ist raus (Birk): es entsteht immer zuerst ein Textbuch, die
    Inszenierung macht das Team in der Probe. Was eine einzelne Szene zum
    Dialog oder zum Lied macht, ist ihr Feld ``form``."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen = []
    if stand["rahmen"]:
        zeilen.append(T._RAHMEN_BLOCK.format(rahmen=stand["rahmen"]))
    geschichte = stand["geschichte"] if "geschichte" in stand.keys() else None
    if geschichte:
        zeilen.append(T._BOGEN_BLOCK.format(geschichte=geschichte))
    return "\n\n".join(zeilen)


#: Die Koepfe der ersten beiden Bloecke des Szenen-Prompts (W3: der
#: Nutzertext spricht die Sprache des Profils).
_RAHMEN_BLOCK = (
    "Die Geschichte / der Rahmen des Stuecks -- das ist die Vorgabe der "
    "Gruppe, jede Szene ist ein Teil davon und muss dazu passen:\n"
    "{rahmen}"
)
_BOGEN_BLOCK = "Bogen und Ende:\n{geschichte}"
_KERNFRAGE_KOPF = "Kernfrage:\n"
_ZEILE_HAUPTKONFLIKT = "Hauptkonflikt: {hauptkonflikt}"


def _thema_text(conn, chat_id: int) -> str:
    """Block 2: Kernthema samt Begruendung, Hauptkonflikt nur, wenn es einen
    gibt.

    Der Hauptkonflikt ist seit dem 05.09.2026 optional (Birk: "Es muss nicht
    immer einen Konflikt geben") -- eine leere Zeile "Hauptkonflikt: -" wuerde
    das Modell einen erfinden lassen.

    Seit dem Abend des 05.09.2026 steht hier auch die **Kernfrage** (die
    dramatische Frage samt Gegensatz und Einsatz): sie ist der Faden, an dem
    die Szene haengt, und sie steht vor allem anderen."""
    from interview_theater import kontext

    stand = repo.hole_arbeitsstand(conn, chat_id)
    if not stand:
        return ""
    zeilen = []
    # Die Geschichte steht NICHT hier: sie steht schon einen Block darueber
    # in ``_format_rahmen_text`` als "Bogen und Ende" (Audit-Befund S1,
    # 06.09.2026 -- wortgleich zweimal im selben Prompt, 260 Zeichen). Ein
    # Fakt, eine Stelle.
    kernthema = kontext.kernthema_zeile(stand)
    if kernthema:
        zeilen.append(kernthema)
    if stand["kernfrage"]:
        zeilen.append(T._KERNFRAGE_KOPF + stand["kernfrage"].strip())
    if stand["hauptkonflikt"]:
        zeilen.append(T._ZEILE_HAUPTKONFLIKT.format(hauptkonflikt=stand["hauptkonflikt"]))
    return "\n".join(zeilen)


#: Ueberschrift des Kernpaket-Blocks im Szenen-Prompt (05.09.2026 abends).
#: Er ersetzt das, was hier frueher gar nicht stand und im Gespraechs-Prompt
#: alle Verdichtungen waren: die **am Kernthema gefilterte** Auswahl -- die
#: passenden Verdichtungsthemen und die geprueften Kernzitate.
KERNPAKET_KOPF = (
    "Die Stellen, die zum Kernthema gehoeren (am Kernthema gefiltert, mit "
    "Interview-Nummer). Sie sind die Grundlage - alles andere Material siehst "
    "du hier bewusst nicht:"
)


def _kernpaket_text(conn, chat_id: int, ziel=None) -> str:
    """Block 2b: die gefilterten Verdichtungen und die Kernzitate.

    Das ersetzt die Zitatquelle des Szenen-Prompts: bis hierher kamen
    woertliche Saetze allein aus den Sprachprofilen der Figuren, die
    thematische Grundlage fehlte ganz. Jetzt steht die Auswahl da, die am
    Kernthema getroffen wurde -- nicht alle Verdichtungen, nicht ein
    Transkript. Die Sprachprofile bleiben unveraendert daneben stehen
    (``_figuren_text``): das eine sagt, WORUM es geht, das andere, WIE
    jemand spricht.

    **Seit dem Umbau vom 05.09.2026 nachts sind es die Schaerfungen dieser
    EINEN Szene** (``repo.schaerfungen``, Phase 6) und ihrer Figuren -- nicht
    mehr die globale Kernzitat-Auswahl. Der Unterschied ist der Punkt: eine
    Szene bekommt die Stellen, die zu ihr gehoeren, und keine fremden. Ohne
    Schaerfungen faellt der Code auf die alte Auswahl zurueck (eine Gruppe,
    die den Umbau nicht mitgemacht hat, verliert nichts)."""
    zeilen = []
    from interview_theater import kontext

    if ziel is not None:
        for eintrag in repo.schaerfungen(conn, chat_id, szene_id=ziel["id"]):
            name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
            zeile = f'- {name}: {eintrag["thema"]} -- "{eintrag["zitat"]}"'
            if eintrag["begruendung"]:
                zeile += f" ({eintrag['begruendung']})"
            zeilen.append(zeile)
        for figur in repo.szene_figuren(conn, ziel["id"]):
            for eintrag in repo.schaerfungen(conn, chat_id, figur_id=figur["id"]):
                name = kontext.interviewbezeichnung(
                    conn, chat_id, eintrag["aufnahme_id"]
                )
                zeilen.append(
                    f'- {figur["name"]} ({name}): {eintrag["thema"]} -- '
                    f'"{eintrag["zitat"]}"'
                )
        if zeilen:
            return T.KERNPAKET_KOPF + "\n" + "\n".join(zeilen)
    # Die Zusammenfassung gehoert der Verdichtung, nicht dem Thema: elf
    # markierte Themen eines Interviews schrieben sie elfmal (Audit-Befund
    # S2, 06.09.2026 -- 7.700 Zeichen Dublette). Einmal je Interview.
    gesehen: set[str] = set()
    for thema in repo.kernthemen_themen(conn, chat_id):
        name = kontext.interviewbezeichnung(conn, chat_id, thema["aufnahme_id"])
        zeile = f"- {name}: {thema['thema']}"
        zusammenfassung = (thema["zusammenfassung"] or "").strip()
        if zusammenfassung and zusammenfassung not in gesehen:
            gesehen.add(zusammenfassung)
            zeile += f"\n    {zusammenfassung}"
        zeilen.append(zeile)
    for eintrag in repo.kernzitate(conn, chat_id):
        name = kontext.interviewbezeichnung(conn, chat_id, eintrag["aufnahme_id"])
        zeile = f'- {name}: "{eintrag["zitat"]}"'
        if eintrag["begruendung"]:
            zeile += f" ({eintrag['begruendung']})"
        zeilen.append(zeile)
    if not zeilen:
        return ""
    return T.KERNPAKET_KOPF + "\n" + "\n".join(zeilen)


#: Ueberschrift von Block 3 -- die wichtigste Zeile des ganzen Prompts (Birk,
#: 05.09.2026: "Zitate als Few-Shots fuer die Sprechweise je Figur, das ist
#: das Wichtigste"). Sie sagt ausdruecklich, was mit den Zitaten zu tun ist:
#: nicht sie einbauen, sondern die Sprechweise daraus kopieren.
FIGUREN_KOPF = (
    "So spricht jede Figur (aus ihrem Interview, woertlich -- kopiere diese "
    "Sprechweise):"
)
#: Kopf, wenn KEINE Figur ein Sprachprofil/Zitate hat -- dann verspricht der
#: Block nichts, was er nicht haelt (06.09.2026: der Prompt sagte "woertlich",
#: darunter standen nur Name und ein Satz).
FIGUREN_KOPF_OHNE_STIMME = (
    "Die Figuren (wer sie sind, was sie wollen). Sprechweise ist noch nicht "
    "aus Interviews belegt -- gib jeder Figur eine eigene, unterscheidbare "
    "Art zu reden (Satzlaenge, Tempo, Lieblingswoerter), und halte sie durch:"
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
    # **Nur echte Zitate rechtfertigen den woertlich-Kopf** (Audit-Befund S4,
    # 06.09.2026). Vorher genuegte ein Sprachprofil, um FIGUREN_KOPF zu
    # setzen -- der sagt aber "aus ihrem Interview, woertlich", und darunter
    # standen dann Name, Beschreibung und eine Duktus-Zeile, kein einziges
    # Zitat. Ein Prompt, der etwas ankuendigt und nicht liefert, laesst das
    # Modell das Fehlende ergaenzen: es erfindet Zitate.
    mit_zitat = False
    for figur in repo.figuren(conn, chat_id):
        zeilen = [f"{figur['name']}"]
        if figur["beschreibung"]:
            zeilen[0] += f" -- {figur['beschreibung']}"
        if figur["sprachprofil"]:
            zeilen.append(figur["sprachprofil"].strip())
        for satz in (figur["zitate"] or "").split(repo.ZITAT_TRENNER):
            if satz.strip():
                zeilen.append(f'  "{satz.strip()}"')
                mit_zitat = True
        bloecke.append("\n".join(zeilen))
    if not bloecke:
        return ""
    kopf = T.FIGUREN_KOPF if mit_zitat else T.FIGUREN_KOPF_OHNE_STIMME
    return kopf + "\n\n" + "\n\n".join(bloecke)


#: Ueberschrift von Block 4. Continuity kommt **mechanisch aus der Datenbank**
#: (T5) -- kein Modellaufruf, keine Zusammenfassung: Nummer, Titel, Ort, Wer,
#: Was passiert, Was anders, je frueherer Szene eine Zeile.
CONTINUITY_KOPF = "Was bisher geschah:"


def _szenenfelder_zeilen(conn, zeile, felder) -> list[str]:
    """Die genannten Felder einer Szene als "Name: Wert"-Zeilen, leere weg.
    Die eine Stelle, an der Szenenfelder formatiert werden -- Continuity und
    "Diese Szene" sollen nie auseinanderlaufen."""
    zeilen = []
    feldnamen = T.FELDNAMEN
    for feld in felder:
        if feld == "figuren":
            namen = [f["name"] for f in repo.szene_figuren(conn, zeile["id"])]
            if namen:
                zeilen.append(f"{feldnamen['figuren']}: {', '.join(namen)}")
            continue
        if zeile[feld]:
            zeilen.append(f"{feldnamen[feld]}: {zeile[feld]}")
    return zeilen


#: Was aus einer frueheren Szene als Stichzeile mitgeht. Der Volltext kommt
#: seit dem 05.09.2026 zusaetzlich dazu (``_continuity_text``): die Stichzeilen
#: sagen die Lage, der Volltext die Sprache.
_CONTINUITY_FELDER = ("ort", "figuren", "was_passiert", "was_anders")

#: Was in "Diese Szene" steht: alles, was die Gruppe entschieden hat.
_DIESE_SZENE_FELDER = (
    "form", "ort", "zeit", "anlass", "figuren", "was_passiert", "was_anders",
    "kernsaetze", "ton", "titel",
)

#: Der Satz ueber den frueheren Szenen. Er sagt, was mit ihnen zu tun ist --
#: anschliessen, nicht wiederholen (Birk, 05.09.2026: "Szene 2 kennt Szene 1
#: nicht wirklich").
CONTINUITY_ANSCHLUSS = (
    "Das ist bereits geschrieben und gilt. Schliesse daran an: Figuren, "
    "Motive, Bewegungsmuster, Kernsaetze und Ton fuehren weiter; wiederhole "
    "nichts woertlich, ausser als bewusstes Echo."
)

#: Wie ein Volltext im Continuity-Block ueberschrieben wird.
CONTINUITY_VOLLTEXT_KOPF = "Szene {nummer} - vollstaendiger Text:"

#: Wie eine auf ihre Zusammenfassung reduzierte Szene ueberschrieben wird
#: (06.09.2026). Sie steht ausdruecklich als Zusammenfassung da und nicht als
#: gekuerzter Text: eine stille Auslassung saehe fuer das Modell aus wie eine
#: Szene, die so kurz war.
CONTINUITY_FASSUNG_KOPF = "Szene {nummer} - Zusammenfassung (nicht der Wortlaut):"

#: Der Schluessel der dritten Pflichtzeile der Modellantwort.
ZUSAMMENFASSUNG_SCHLUESSEL = "ZUSAMMENFASSUNG"

#: Der Schluessel der vierten Pflichtzeile (06.09.2026): was das Modell wegen
#: des Chats oder einer Regie-Notiz von den gespeicherten Angaben abweichend
#: gemacht hat. Sie ist der Weg, auf dem eine Freitext-Korrektur der Gruppe
#: nach dem Lauf im **Journal** landet und nicht nur im Szenentext -- der
#: Journal-Extraktor greift erst, wenn 2.000 Zeichen aus dem Gespraechsfenster
#: verdraengt wurden, und lief an Tag 1 nie.
ANDERS_SCHLUESSEL = "ANDERS GEMACHT"

#: Was in dieser Zeile "nichts" heisst. Eine Journalzeile "Szene 3: nichts"
#: waere Rauschen im Arbeitsstand.
_ANDERS_NICHTS = ("nichts", "keine abweichung", "keine", "-", "nichts anders")

#: Dasselbe auf Englisch (Karte A1): der englische Szenenprompt verlangt
#: ``ANDERS GEMACHT: nothing``. Gelesen wird die Vereinigung.
_ANDERS_NICHTS_EN = ("nothing", "none", "no deviation", "nothing different", "-")

#: Die englischen Alternativen der Kopfzeilen-Schluessel (Karte A1, K5). Der
#: Prompt verlangt die deutschen Protokoll-Token; ein englisches Modell
#: labelt trotzdem manchmal englisch. Deutsch wird zuerst probiert.
_TITEL_SCHLUESSEL = ("TITEL", "TITLE")
_KURZ_SCHLUESSEL = ("KURZ", "SHORT")
_ZUSAMMENFASSUNG_SCHLUESSEL_BEIDE = (ZUSAMMENFASSUNG_SCHLUESSEL, "SUMMARY")
_ANDERS_SCHLUESSEL_BEIDE = (ANDERS_SCHLUESSEL, "DONE DIFFERENTLY")

#: Der Kopf der Journalzeile, die aus "ANDERS GEMACHT" entsteht.
_JOURNAL_ANDERS = "Szene {nummer}: {text}"

#: Die Journalzeile nach einem Szenenlauf.
_JOURNAL_GESCHRIEBEN = "Szene {nummer} geschrieben: {titel}"

#: Zeilenkopf der Zusammenfassung in ``/stand`` und in der Phase-8-Uebersicht.
STAND_ZUSAMMENFASSUNG = "Szene {nummer}: {text}"

#: Wie viele Zeilen einer Szene ohne eigene Zusammenfassung stehen bleiben:
#: ihr Schluss. Genau er ist der Anschluss -- wie eine Szene ausgeht,
#: entscheidet, wie die naechste anfaengt.
CONTINUITY_KUERZUNG_ZEILEN = 15

_TEXT_CONTINUITY_GEKUERZT = "(Anfang gekuerzt, hier der Schluss der Szene:)"
_TEXT_KEINE_ANGABEN = "(keine Angaben zu dieser Szene)"

#: **Das Token-Budget des Szenen-Prompts -- hergeleitet, nicht gesetzt**
#: (Birk, 06.09.2026 04:30: *"Ob 50k fuer Reasoning reicht, nicht behaupten,
#: sondern pruefen; lieber konservativ; nichts darf abgeschnitten werden."*).
#:
#: **Zeichen je Token: 1,9, nicht 3.** ``kontext._ZEICHEN_JE_TOKEN`` = 3 ist
#: fuer ein Qualitaetsbudget gut genug; als harte Fenstergrenze waere es
#: gefaehrlich. Gemessen am 06.09.2026 gegen den Proxy
#: (``POST /v1/messages/count_tokens``, claude-opus-5, echter Szenen-Prompt
#: der Testgruppe): **38.610 Zeichen = 20.222 Token = 1,909 Zeichen je
#: Token** -- die Drei-Zeichen-Regel haette 12.870 geschaetzt und damit um
#: 36 % zu niedrig gelegen. Deutscher Prosatext mit Umlauten und
#: Eigennamen tokenisiert schlechter als englischer Fliesstext. Der Wert
#: deckt sich mit den gebuchten Laeufen (``aufruf``: 19.024 / 15.030 /
#: 14.920 / 13.689 / 12.575 Eingabe-Token, alle ``stop_reason=end_turn``).
SZENE_ZEICHEN_JE_TOKEN = 1.9

#: Kontextfenster von claude-opus-5: **200.000 Token fuer Eingabe UND
#: Ausgabe zusammen** -- Eingabe + ``max_tokens`` muessen darunter bleiben.
#: (Anthropic, Models overview, Stand 06.09.2026: das dort genannte 1M-Fenster
#: gilt fuer die aktuelle API-Generation; der hier benutzte Proxy faehrt das
#: konservative 200k-Fenster, und konservativ ist genau das, was hier
#: gebraucht wird -- ein zu grosszuegiges Budget quittiert die API mit
#: HTTP 400 statt mit einer Kuerzung.)
CLAUDE_FENSTER_TOKEN = 200_000

#: Das Fenster des Infomaniak-Pfads: Eingabe und Ausgabe zaehlen dort gegen
#: ein **gemeinsames** ``max_total_tokens = 249.984``
#: (SPEC-kontext-architektur.md, Nachtrag zu ``szene.MAX_TOKENS``). Weil
#: ``llm.prosa`` mit ``max_tokens = MAX_TOKENS`` = 200.000 gerufen wird, bleibt
#: dort rechnerisch nur der Rest fuer die Eingabe -- deutlich weniger als beim
#: Claude-Pfad. Das ist ein Befund, keine Annahme: wer dem Szenenlauf ueber
#: Infomaniak mehr Eingabe geben will, muss ``MAX_TOKENS`` senken.
INFOMANIAK_GESAMT_TOKEN = 249_984

#: Sicherheitsabschlag auf das rechnerische Budget: 25 %. Er faengt ab, was
#: die Zeichenschaetzung nicht sieht -- Formatierung des Anbieters,
#: Sonderzeichen in einem Interviewzitat, und die Schwankung der
#: Tokenisierung zwischen 1,9 und (im schlechtesten gemessenen Fall) knapp
#: darunter.
#:
#: **Die Systemanweisung faengt er NICHT ab** (Kalibrierung 30.09.2026,
#: ``docs/kontext-3-5-kalibrierung.md`` § 6). Bis dahin war das der Plan,
#: und er ging nicht auf: die groesste Szenen-Systemanweisung
#: (``dialog`` + Stil ``schlagabtausch``) misst 37.043 Zeichen ≈ 19.496
#: Token, der Abschlag auf den Infomaniak-Raum sind nur 12.496. Ein
#: Nutzertext am Budget haette mit ihr 56.984 Token gegen 49.984 Raum
#: ergeben -- HTTP 400, bevor die Kuerzungsleiter anspringt. Seither ist das
#: Budget eines, das System **und** Nutzertext zusammen fassen muss:
#: ``baue_nutzertext`` zieht die Systemanweisung des Laufs (Form + Stil) ab,
#: bevor es den Nutzertext misst (``nutzer_budget``).
BUDGET_RESERVE = 0.75

#: Eingabe-Budget des Claude-Pfads: (200.000 - 32.000 Ausgabedeckel) x 0,75,
#: fuer System + Nutzertext zusammen.
#: Gemessene Laeufe brauchen davon rund 15 % -- der Deckel ist die Bremse fuer
#: den Ausreisser (sechs lange Vorszenen im Volltext), nicht der Normalfall.
SZENE_TOKEN_MAX_CLAUDE = int(
    (CLAUDE_FENSTER_TOKEN - szene_claude.MAX_TOKENS) * BUDGET_RESERVE
)

#: Eingabe-Budget des Infomaniak-Pfads: (249.984 - 200.000) x 0,75, fuer
#: System + Nutzertext zusammen. Klein, aber ehrlich -- siehe
#: ``INFOMANIAK_GESAMT_TOKEN``. Mit der groessten Systemanweisung (19.496
#: Token) bleiben dem Nutzertext davon 17.992.
SZENE_TOKEN_MAX_INFOMANIAK = int(
    (INFOMANIAK_GESAMT_TOKEN - MAX_TOKENS) * BUDGET_RESERVE
)

#: Ab diesem Anteil des Budgets warnt der Lauf nach dem Aufruf ins Log --
#: mit den TATSAECHLICHEN Token des Anbieters, nicht mit der Schaetzung. So
#: bleibt die Herleitung oben im Betrieb messbar und faellt auf, bevor sie
#: reisst.
BUDGET_WARNSCHWELLE = 0.9


def token_budget(claude: bool) -> int:
    """Das geltende Eingabe-Budget in Token, je nach Anbieter -- fuer die
    **ganze** Eingabe, Systemanweisung und Nutzertext zusammen (seit
    30.09.2026; vorher wurde nur der Nutzertext dagegen gemessen). Wie viel
    davon dem Nutzertext bleibt, rechnet ``nutzer_budget`` aus.

    ``IT_SZENE_TOKEN_MAX`` ueberschreibt beides und meint dasselbe: die
    ganze Eingabe inklusive Systemanweisung -- bei jedem Aufruf gelesen
    (wie ``kontext.zeichengrenze``): am Workshoptag soll eine Korrektur ohne
    Neustart wirken. Ein unlesbarer oder unsinniger Wert faellt still auf die
    Herleitung zurueck."""
    vorgabe = SZENE_TOKEN_MAX_CLAUDE if claude else SZENE_TOKEN_MAX_INFOMANIAK
    roh = os.environ.get("IT_SZENE_TOKEN_MAX")
    if not roh:
        return vorgabe
    try:
        wert = int(roh)
    except ValueError:
        log.warning("IT_SZENE_TOKEN_MAX unlesbar (%r), nehme %d", roh, vorgabe)
        return vorgabe
    if wert < 1_000:
        log.warning("IT_SZENE_TOKEN_MAX zu klein (%d), nehme %d", wert, vorgabe)
        return vorgabe
    return wert


def nutzer_budget(claude: bool, system: str | None = None) -> int:
    """Was vom Eingabe-Budget fuer den Nutzertext bleibt: ``token_budget``
    minus die geschaetzten Token der Systemanweisung dieses Laufs.

    Gerechnet wird mit der TATSAECHLICHEN Anweisung (Form + Stil), nicht mit
    einer Konstante fuer den groessten Fall: ein Stilblatt, das waechst,
    schiebt die Grenze mit, statt eine feste Zahl veralten zu lassen. Nie
    negativ -- ist die Anweisung allein schon ueber dem Budget, bleibt 0,
    die Leiter kuerzt bis zum Ende und meldet, dass es nicht reicht."""
    return max(0, token_budget(claude) - schaetze_token(system or ""))


def schaetze_token(text: str) -> int:
    """Tokenschaetzung fuer den Szenen-Prompt: Zeichen ÷ 1,9 (gemessen, siehe
    ``SZENE_ZEICHEN_JE_TOKEN``). Bewusst NICHT ``kontext.schaetze``: dessen
    Divisor 3 ist fuer ein Qualitaetsbudget gedacht, hier zaehlt eine harte
    Fenstergrenze."""
    return int(len(text) / SZENE_ZEICHEN_JE_TOKEN)


#: Auf so viele Zitate je Figur faellt das Sprachprofil zurueck, wenn selbst
#: nach allen anderen Kuerzungen nichts passt (letzte Stufe).
SPRACHPROFIL_ZITATE_MAX = 3


def _gekuerzter_volltext(volltext: str) -> str:
    """Die letzten ``CONTINUITY_KUERZUNG_ZEILEN`` Zeilen, mit einer Zeile
    davor, die sagt, dass gekuerzt wurde. Ein stillschweigend abgeschnittener
    Text saehe fuer das Modell aus wie eine Szene, die mittendrin anfaengt."""
    zeilen = [z for z in volltext.strip().splitlines()]
    if len(zeilen) <= CONTINUITY_KUERZUNG_ZEILEN:
        return volltext.strip()
    schluss = "\n".join(zeilen[-CONTINUITY_KUERZUNG_ZEILEN:])
    return f"{T._TEXT_CONTINUITY_GEKUERZT}\n{schluss}"


def _zusammenfassung_fuer(conn, szene) -> str:
    """Die Zusammenfassung einer Szene fuer den Continuity-Block -- oder der
    Rueckfall, wenn sie keine hat.

    **Der Rueckfall ist nie leer** (06.09.2026). Bestehende Szenen stammen aus
    der Zeit vor der Pflichtzeile, und ein Modell, das sich nicht daran haelt,
    darf keine Luecke im Prompt hinterlassen: dann stehen die Stichzeilen
    (Ort, Wer, Was passiert, Was anders) und die letzten
    ``CONTINUITY_KUERZUNG_ZEILEN`` Zeilen des Textes da. Bewusst wird dafuer
    **kein Modell** gerufen -- ein automatischer Opus-Aufruf ohne Auftrag der
    Gruppe waere Geld, das niemand bewilligt hat."""
    eigene = ""
    try:
        eigene = (szene["zusammenfassung"] or "").strip()
    except (IndexError, KeyError):
        eigene = ""
    if eigene:
        return eigene
    zeilen = _szenenfelder_zeilen(conn, szene, _CONTINUITY_FELDER)
    text = (szene["volltext"] or "").strip()
    if text:
        zeilen.append(_gekuerzter_volltext(text))
    if not zeilen:
        return T._TEXT_KEINE_ANGABEN
    return "\n".join(zeilen)


def _continuity_bloecke(conn, chat_id: int, nummer: int | None) -> list[dict]:
    """Die frueheren Szenen als Bausteine: je Szene Kopf, Stichzeilen,
    Volltext und Zusammenfassung -- unentschieden, was davon in den Prompt
    geht. Die Entscheidung faellt in ``baue_nutzertext``, wenn feststeht, wie
    viel Platz uebrig ist.

    **Nur Szenen mit kleinerer Nummer** -- was danach kommt, ist fuer diese
    Szene keine Vorgeschichte, und eine Szene 5 als "bisher" zu lesen waere
    schlicht falsch. Ohne genannte Nummer (ein Auftrag ohne Szenenzahl) zaehlt
    alles Vorhandene als bisher."""
    frueher = [
        s for s in repo.hole_szenen(conn, chat_id)
        if s["nummer"] is not None
        and (nummer is None or s["nummer"] < nummer)
    ]
    bausteine = []
    for szene in frueher:
        kopf = T._SZENE_MIT_NUMMER.format(nummer=szene["nummer"])
        if szene["titel"]:
            kopf += f": {szene['titel']}"
        angaben = _szenenfelder_zeilen(conn, szene, _CONTINUITY_FELDER)
        bausteine.append({
            "nummer": szene["nummer"],
            "kopf": kopf + ("\n  " + "\n  ".join(angaben) if angaben else ""),
            # **Volltext, sonst Prosa** (06.09.2026, 10:30): in Phase 6 gibt
            # es noch keinen Theatertext, aber sehr wohl die Geschichte der
            # Vorszene -- und ohne sie schriebe jede Szene an der vorigen
            # vorbei. In Phase 7 gewinnt der schon uebersetzte Volltext.
            "volltext": (szene["volltext"] or "").strip()
            or _prosa_von(szene),
            "zusammenfassung": _zusammenfassung_fuer(conn, szene),
        })
    return bausteine


def prosa_von(szene) -> str:
    """Die Prosafassung einer Szene -- oder "", wenn die Spalte in einer
    alten Datenbank noch fehlt.

    Die Migration ist additiv und laeuft beim Start; ein Leser darf daran
    trotzdem nicht scheitern (dieselbe Haltung wie ``phasen.feld``).
    Oeffentlich seit 30.09.2026: ``kuerzung`` und ``kurzgeschichte`` lesen
    die Prosa ueber dieselbe Stelle."""
    try:
        return (szene["prosa"] or "").strip()
    except (IndexError, KeyError):
        return ""


#: Der alte, modulinterne Name -- die Aufrufer in diesem Modul bleiben.
_prosa_von = prosa_von


def _continuity_kennzeichnung(bausteine: list[dict], voll: set[int]) -> str:
    """Der ehrliche Satz darueber, welche Szene vollstaendig dasteht und
    welche nur als Zusammenfassung (Birk, 06.09.2026: keine stillen
    Auslassungen).

    Er nennt Nummern, keine Mengen: "Szene 1-2 als Zusammenfassung, Szene 3 im
    vollen Wortlaut -- schliesse an Szene 3 an". Ein Modell, das nicht weiss,
    dass es eine Kurzfassung liest, behandelt sie wie den Wortlaut und
    wiederholt Saetze, die so nie gefallen sind."""
    mit_text = [b for b in bausteine if b["volltext"]]
    if not mit_text:
        return ""
    kurz = [b["nummer"] for b in mit_text if b["nummer"] not in voll]
    ganz = [b["nummer"] for b in mit_text if b["nummer"] in voll]
    if not kurz:
        return ""
    teile = [T._KENNZEICHNUNG_KURZ.format(nummern=_nummernfolge(kurz))]
    if ganz:
        teile.append(T._KENNZEICHNUNG_GANZ.format(nummern=_nummernfolge(ganz)))
    satz = ", ".join(teile) + "."
    if ganz:
        satz += T._KENNZEICHNUNG_ANSCHLUSS.format(nummer=max(ganz))
    return satz


#: Der Kennzeichnungssatz des Continuity-Blocks, in seinen drei Teilen.
_KENNZEICHNUNG_KURZ = "Szene {nummern} als Zusammenfassung"
_KENNZEICHNUNG_GANZ = "Szene {nummern} im vollen Wortlaut"
_KENNZEICHNUNG_ANSCHLUSS = " Schliesse an Szene {nummer} an."


def _nummernfolge(nummern: list[int]) -> str:
    """``[1, 2, 3]`` -> ``"1-3"``, ``[1, 3]`` -> ``"1 und 3"`` -- eine Zeile
    Kosmetik, damit der Kennzeichnungssatz lesbar bleibt."""
    if not nummern:
        return ""
    if len(nummern) == 1:
        return str(nummern[0])
    if nummern == list(range(min(nummern), max(nummern) + 1)):
        return f"{min(nummern)}-{max(nummern)}"
    return ", ".join(str(n) for n in nummern[:-1]) + T._UND + str(nummern[-1])


def _continuity_text(conn, chat_id: int, nummer: int | None,
                     voll: set[int] | None = None) -> str:
    """Block 4: die frueheren Szenen, mechanisch aus der Datenbank.

    ``voll`` sagt, welche Szenennummern im vollen Wortlaut dastehen duerfen;
    alle uebrigen erscheinen als Zusammenfassung. ``None`` heisst "alle voll"
    -- so wird der Block zuerst gebaut, und erst wenn der GESAMTE Nutzertext
    ueber ``SZENE_TOKEN_MAX`` liegt, wird er mit einem kleineren ``voll`` neu
    gebaut (``baue_nutzertext``).

    **Der Volltext geht mit** (05.09.2026, Birk nach der Testgruppe): bis
    dahin standen hier nur Ort, Wer, Was passiert und Was anders -- Szene 2
    kannte Szene 1 damit nicht wirklich, weder ihre Saetze noch ihren Ton.

    **Gekuerzt wird von der AELTESTEN Szene an** (06.09.2026, Birk: *"Erste
    Szenen zuerst per Zusammenfassung."*). Die juengste Vorszene bleibt so
    lange wie irgend moeglich vollstaendig: an sie wird unmittelbar
    angeschlossen, und ihr Wortlaut ist der Ton, den die neue Szene
    weiterfuehrt."""
    bausteine = _continuity_bloecke(conn, chat_id, nummer)
    if not bausteine:
        return ""
    if voll is None:
        voll = {b["nummer"] for b in bausteine}

    bloecke = []
    for b in bausteine:
        teile = [b["kopf"]]
        if b["volltext"] and b["nummer"] in voll:
            teile.append(
                T.CONTINUITY_VOLLTEXT_KOPF.format(nummer=b["nummer"])
                + "\n" + b["volltext"]
            )
        elif b["volltext"]:
            # Nur wo es einen Text GIBT, steht eine Zusammenfassung: eine
            # bloss geplante Szene hat nichts zusammenzufassen, und ihr
            # Rueckfall waeren exakt die Stichzeilen, die schon im Kopf
            # stehen (Dublette -- Prompt-Audit-Regel 1).
            teile.append(
                T.CONTINUITY_FASSUNG_KOPF.format(nummer=b["nummer"])
                + "\n" + b["zusammenfassung"]
            )
        bloecke.append("\n\n".join(teile))

    kopf = [T.CONTINUITY_KOPF, T.CONTINUITY_ANSCHLUSS]
    kennzeichnung = _continuity_kennzeichnung(bausteine, voll)
    if kennzeichnung:
        kopf.append(kennzeichnung)
    return "\n".join(kopf) + "\n\n" + "\n\n".join(bloecke)


#: Ueberschrift von Block 6. Der Satz dahinter ist der Kern der Umstellung:
#: die Felder sind bindend, das Modell erfindet sie nicht neu.
DIESE_SZENE_KOPF = (
    "Diese Szene sollst du schreiben. Die Angaben sind bindend -- nichts "
    "ersetzen, nichts hinzuerfinden, was ihnen widerspricht:"
)

#: Was eine Szene an ihrer Stelle im Stueck LEISTEN muss (Birk, 06.09.2026
#: 00:00, nach einer Szene 1, die \"gar nicht mit dem zusammenhing, was wir
#: reingegeben haben\"). Die Angaben sagen, was passiert -- diese Zeilen
#: sagen, welche Fragen der Text fuer das Publikum beantwortet haben muss.
#: Deterministisch aus der Position: erste, mittlere, letzte Szene.
_AUFGABE_ERSTE = (
    "Aufgabe dieser Szene (sie ist die ERSTE -- Exposition): Wenn sie vorbei "
    "ist, weiss das Publikum ohne Erklaerung (1) wer die Figuren sind, "
    "(2) wie sie zueinander stehen, (3) warum sie hier an diesem Ort sind, "
    "(4) worum es geht -- der Konflikt ist eroeffnet, nicht geloest. Alle vier "
    "muessen im Text vorkommen, gezeigt durch Handlung und Rede, nicht durch "
    "Erklaersaetze. Eine Szene 1, die nur eine Stimmung zeigt, ist keine "
    "Szene 1."
)
_AUFGABE_MITTE = (
    "Aufgabe dieser Szene (Szene {nummer} von {gesamt}): Sie fuehrt weiter, "
    "was in den frueheren Szenen eroeffnet wurde -- der Konflikt verschaerft "
    "sich oder wendet sich; am Ende ist die Lage eine andere als am Anfang "
    "(\"Was anders ist\"). Sie darf nichts noch einmal erklaeren, was das "
    "Publikum schon weiss, und muss dem Publikum einen Grund geben, auf die "
    "naechste Szene zu warten."
)
_AUFGABE_LETZTE = (
    "Aufgabe dieser Szene (sie ist die LETZTE): Sie loest ein, was die "
    "Geschichte versprochen hat -- das Ende, wie die Gruppe es festgelegt hat "
    "(offen, traurig, versoehnt: steht im Rahmen/in der Geschichte). Jede "
    "Figur, die im Stueck etwas wollte, hat hier ein letztes Bild. Nichts "
    "Neues wird eroeffnet."
)


def _aufgabe_text(conn, chat_id: int, ziel) -> str:
    """Block: die dramaturgische Aufgabe der Szene an ihrer Position."""
    if ziel is None or ziel["nummer"] is None:
        return ""
    szenen = [
        s for s in repo.hole_szenen(conn, chat_id)
        if s["nummer"] is not None and not s["entfernt_am"]
    ]
    gesamt = max([s["nummer"] for s in szenen] + [ziel["nummer"]])
    nummer = ziel["nummer"]
    if nummer <= 1:
        return T._AUFGABE_ERSTE
    if nummer >= gesamt and gesamt > 1:
        return T._AUFGABE_LETZTE
    return T._AUFGABE_MITTE.format(nummer=nummer, gesamt=gesamt)


def budget_fuer_szene(conn, chat_id: int, ziel) -> int:
    """Das Wortbudget dieser Szene, oder 0, wenn dieses Profil keine waehlt.

    Die Form kommt aus ``laengen.form_der_szene``: bestaetigt vor
    vorgeschlagen vor Profilvorgabe. Der Seed ist die ``chat_id``, das Muster
    wird zyklisch ueber die Szenennummer gelesen -- eine spaeter eingefuegte
    Szene verschiebt deshalb kein Budget einer frueheren.

    Reine Leseabfrage, kein Modellaufruf."""
    from interview_theater import laengen

    if ziel is None or not laengen.aktiv():
        return 0
    stand = repo.hole_arbeitsstand(conn, chat_id)
    budget = laengen.budget_fuer(
        ziel["nummer"], laengen.form_der_szene(ziel), seed=chat_id,
        faktor=laengen.faktor_aus_stand(stand),
    )
    # Erst der Faktor (im Wuerfel), dann der Deckel: eine ausdrueckliche
    # Ansage der Gruppe ist eine Obergrenze und keine Zielzahl.
    return laengen.budget_mit_ansage(
        budget, laengen.woerter_aus_festlegungen(repo.festlegungen(conn, chat_id)),
    )


def _laenge_text(conn, chat_id: int, ziel) -> str:
    """Block: die Laenge dieser Szene. Leer, solange kein Profil sie waehlt --
    dann faellt er in ``_zusammen`` ersatzlos weg und der Nutzertext bleibt
    zeichengleich."""
    from interview_theater import laengen

    return laengen.block_szene(budget_fuer_szene(conn, chat_id, ziel))


#: Steht dieser Marker im Auftrag, ist es ein Neuschreiben: die alte Fassung
#: geht NICHT als Vorlage mit (06.09.2026, "Neu schreiben" lieferte zweimal
#: denselben Text). Der Marker selbst wird aus dem Auftrag entfernt.
NEU_MARKER = "[NEU]"
NEU_HINWEIS = (
    "Es gab schon eine Fassung dieser Szene; die Gruppe hat sie verworfen. "
    "Schreib eine ANDERE Szene zu denselben Angaben: anderer Einstieg, andere "
    "Struktur, andere Bilder, anderer Titel. Nichts aus der alten Fassung "
    "wiederverwenden -- du kennst sie nicht."
)


#: Steht dieser Marker im Auftrag, geht im **Prosalauf** (Phase 6) die
#: bestehende Prosa der Szene als bisheriger Text mit (30.09.2026, Kuerzen).
#: Dort ist ``volltext`` leer, und ohne den Marker saehe das Modell den Text
#: nicht, den es kuerzen soll -- ein Neuschrieb statt einer Kuerzung. Ein
#: Marker und kein Automatismus: jeder andere Lauf behaelt seinen Nutzertext
#: zeichengleich (Schnappschuss ``tests/test_profil_bitgleich.py``). Wie
#: ``NEU_MARKER`` wird er aus dem Auftrag entfernt.
BISHER_MARKER = "[BISHER]"
BISHER_KOPF = "Bisheriger Text dieser Szene, er soll ueberarbeitet werden:"

#: Die internen Auftragszeilen an ``starte`` (Karte A1, Aufgabe 23). Sie
#: landen unter dem Auftragskopf im Szenen-Prompt und gehen deshalb ueber
#: ``T``; lesbar bleiben sie in beiden Sprachen, weil
#: ``nummer_aus_auftrag`` "Szene N" und "scene N" versteht. Die Marker
#: (``NEU_MARKER``, ``BISHER_MARKER``) sind Protokoll und bleiben, wie sie
#: sind -- sie haengen hinten an ``notiz``. Aufrufer: ``starte`` selbst,
#: ``ablauf`` (Regie-Notiz), ``kuerzung``, ``knoepfe.szenen``/``wirkung``.
TEXT_AUFTRAG_SCHREIBEN = "Schreib Szene {nummer}."
TEXT_AUFTRAG_NEU = "Schreib Szene {nummer} neu. {notiz}"


#: Der Kopf ueber der Prosafassung im Feinschliff-Prompt (Phase 7,
#: 06.09.2026, 10:30). Die Geschichte ist dort **bindende Vorlage**: was
#: entsteht, ist eine Uebersetzung in eine Form, keine neue Szene.
VORLAGE_KOPF = (
    "Diese Szene steht bereits als Geschichte fest. Uebersetze sie in die "
    "Form \"{form}\": dieselben Ereignisse, dieselbe Reihenfolge, dieselben "
    "Figuren, dasselbe Ende. Erfinde nichts hinzu, was der Geschichte "
    "widerspricht, und lass nichts weg, was in ihr passiert. Was die "
    "Geschichte erzaehlt, wird jetzt gespielt.\n\n"
    "Die Geschichte dieser Szene:"
)

#: Die Form, die im Vorlagenkopf steht, wenn die Szene noch keine hat.
_FORM_RUECKFALL = "Dialog"


def _diese_szene_text(conn, ziel, neu: bool = False, vorlage: bool = False,
                      bisher_prosa: bool = False) -> str:
    """Block 6: alle Felder der zu schreibenden Szene, und bei einer
    Ueberarbeitung ihr bisheriger Text.

    Der Volltext geht nur bei einer Ueberarbeitung mit -- also dann, wenn es
    schon einen gibt. Bei einer neuen Szene waere ein fremder Volltext vor
    allem eine Vorlage zum Abschreiben.

    ``vorlage`` ist der Feinschliff (Phase 7): dann traegt der Block die
    **Prosafassung** als bindende Vorlage. Das ist der eine Fall, in dem ein
    fremder Text ausdruecklich abgeschrieben werden soll -- er ist das, was
    die Gruppe abgenommen hat.

    ``bisher_prosa`` (``BISHER_MARKER``) ist die Ueberarbeitung im
    Prosalauf: dann steht die bestehende Prosa als bisheriger Text da, weil
    ``volltext`` dort leer ist."""
    if ziel is None:
        return ""
    zeilen = [T.DIESE_SZENE_KOPF, _szenenkopf(ziel["nummer"])]
    zeilen += _szenenfelder_zeilen(conn, ziel, _DIESE_SZENE_FELDER)
    if vorlage and _prosa_von(ziel):
        zeilen.append("")
        zeilen.append(T.VORLAGE_KOPF.format(form=(ziel["form"] or T._FORM_RUECKFALL)))
        zeilen.append(_prosa_von(ziel))
    if ziel["volltext"] and not neu:
        zeilen.append("")
        zeilen.append(T.BISHER_KOPF)
        zeilen.append(ziel["volltext"])
    elif bisher_prosa and not vorlage and not neu and _prosa_von(ziel):
        zeilen.append("")
        zeilen.append(T.BISHER_KOPF)
        zeilen.append(_prosa_von(ziel))
    elif ziel["volltext"] and neu:
        zeilen.append("")
        zeilen.append(T.NEU_HINWEIS)
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
    return T._VERWORFEN_KOPF + "\n".join(zeilen)


_VERWORFEN_KOPF = "Das hat die Gruppe verworfen, es kommt nicht wieder vor:\n"


#: Ueberschrift des Chat-Blocks (06.09.2026, Birk: *"Der Szenenlauf sollte
#: auch den Chat mitbekommen, sonst kann nie von der vorgegebenen Struktur
#: abgewichen werden und es kommt immer zu Situationen, wo das Modell
#: scheinbar nicht richtig reagiert oder sich wiederholt."*).
CHAT_KOPF = "Was die Gruppe zuletzt dazu gesagt hat:"

#: Der Satz, der sagt, was mit dem Chat zu tun ist. Er raeumt den Vorrang
#: ausdruecklich ein: die gespeicherten Angaben sind der Stand von gestern,
#: der Chat ist die frische Absicht -- und ohne diesen Satz gewinnt im Zweifel
#: das, was oefter und strukturierter im Prompt steht (die Felder).
CHAT_ANSCHLUSS = (
    "Der Chat unten ist die frische Absicht der Gruppe. Widerspricht er den "
    "gespeicherten Angaben, gilt der Chat -- und du sagst in der "
    "Zusammenfassungszeile, was du deshalb anders gemacht hast. Wiederhole "
    "nicht, was die Gruppe an einer frueheren Fassung bemaengelt hat."
)

#: Kopf ueber den Journalzeilen zu genau dieser Szene.
CHAT_REGIE_KOPF = "Notizen der Gruppe zu dieser Szene:"

#: Wer im Chat-Block spricht -- ohne Klarnamen (siehe ``_chat_text``).
_SPRECHER_DU = "Du"
_SPRECHER_GRUPPE = "Gruppe"

#: Der Kopf ueber dem Auftrag, ganz am Ende des Nutzertexts.
_AUFTRAG_KOPF = "Euer Auftrag:\n"

#: Wie viele Chatnachrichten hoechstens mitgehen -- dieselbe Zahl wie im
#: Gespraechsfenster (``kontext.FENSTER_NACHRICHTEN``), aber eigenstaendig:
#: hier ist es ein Untergrenze-Fenster, dort eine Obergrenze.
CHAT_NACHRICHTEN = 20

#: Auf so viele Nachrichten faellt der Block zurueck, wenn das Budget nicht
#: reicht. **Nie auf null**: der Chat ist der einzige Weg, auf dem eine
#: Freitext-Korrektur ueberhaupt in den Lauf kommt.
CHAT_NACHRICHTEN_KURZ = 10

#: So viele Zeichen einer Bot-Nachricht gehen mit. Der Bot schickt ganze
#: Szenentexte in den Chat -- die stehen als Continuity schon im Prompt, und
#: ein zweites Mal waeren sie die groesste Dublette ueberhaupt
#: (Prompt-Audit-Regel 1).
CHAT_BOT_ZEICHEN = 300


def _chat_nachrichten(conn, chat_id: int, ziel, anzahl: int) -> list:
    """Die Nachrichten, die in den Chat-Block gehoeren -- **seit der letzten
    Fassung dieser Szene**, mindestens aber die letzten ``anzahl`` bzw. die
    letzten ``kontext.FENSTER_MINUTEN`` (06.09.2026, Birk).

    Der Grund fuer das Fassungs-Fenster: eine Gruppe schreibt um 14 Uhr "die
    Szene ist zu lang", geht essen und drueckt um 16 Uhr "neu schreiben". Ein
    reines Zeitfenster haette die Korrektur da laengst vergessen -- ein
    Fenster, das an ``szene.geaendert_am`` haengt, nie.

    Systemzeilen, Interview-Echos und die Bin-wieder-da-Meldungen fallen
    heraus (``kontext._ist_systemzeile``, ``repo.letzte_nachrichten``): sie
    sind Ereignisse, keine Gespraechsbeitraege."""
    from datetime import datetime, timedelta

    from interview_theater import kontext

    roh = [
        n for n in repo.letzte_nachrichten(conn, chat_id, anzahl=kontext._FENSTER_POOL)
        if not kontext._ist_systemzeile(n)
    ]
    roh.sort(key=lambda n: n["gesendet_am"])
    if not roh:
        return []

    juengste = datetime.fromisoformat(roh[-1]["gesendet_am"])
    zeitfenster = [
        n for n in roh[-anzahl:]
        if datetime.fromisoformat(n["gesendet_am"])
        >= juengste - timedelta(minutes=kontext.FENSTER_MINUTEN)
    ]

    seit = None
    if ziel is not None:
        try:
            seit = ziel["geaendert_am"]
        except (IndexError, KeyError):
            seit = None
    seit_fassung = [n for n in roh if seit and n["gesendet_am"] >= seit]

    # Die groessere der beiden Mengen, gedeckelt auf ``anzahl``: was seit der
    # letzten Fassung kam, ist der Kern -- das Zeitfenster ist die Untergrenze
    # fuer eine Szene, die gerade erst geschrieben wurde.
    gewaehlt = seit_fassung if len(seit_fassung) > len(zeitfenster) else zeitfenster
    return gewaehlt[-anzahl:]


def _regienotizen(conn, chat_id: int, nummer: int | None) -> list[str]:
    """Die Journalzeilen, die diese Szene beim Namen nennen -- Festlegungen
    und Verworfenes (``entschieden``/``verworfen``).

    Sie stehen im Chat-Block und nicht im Verworfen-Block, weil sie zu genau
    dieser Szene gehoeren und nicht zum Stueck. Hintergrund (06.09.2026): der
    Journal-Extraktor laeuft erst, wenn 2.000 Zeichen aus dem Fenster
    verdraengt wurden, und lief an Tag 1 nie -- Freitext-Korrekturen zu Szenen
    standen ausschliesslich im Chat."""
    if nummer is None:
        return []
    # Rundreise-Marker (Karte A1): ein Journal kann Eintraege aus beiden
    # Sprachen tragen -- "Szene 3" und "Scene 3" meinen dieselbe Szene.
    marken = {
        _SZENE_MIT_NUMMER.format(nummer=nummer),
        T._SZENE_MIT_NUMMER.format(nummer=nummer),
    }
    return [
        f"- {e['text']}" for e in repo.journal(conn, chat_id)
        if e["art"] in ("entschieden", "verworfen")
        and any(marke in (e["text"] or "") for marke in marken)
    ]


def _chat_text(conn, chat_id: int, ziel, nummer: int | None,
               anzahl: int = CHAT_NACHRICHTEN) -> str:
    """Block: der frische Chat plus die Regie-Notizen zu dieser Szene.

    **Ohne Klarnamen** (AGENTS.md, Anti-Klarnamen-Regel): jede Nachricht der
    Gruppe steht als ``Gruppe:``, jede des Bots als ``Du:``. Der
    Telegram-Vorname wandert bewusst NICHT mit -- ein Modell, dem er
    vorliegt, baut ihn in den Szenentext ein ("spricht wie Birk"), und in
    einem Prompt, der ausserdem in die USA geht, hat er nichts zu suchen.
    Genau deshalb wird hier auch nicht ``kontext.sprecherzeile``
    wiederverwendet: die setzt den Vornamen."""
    zeilen = []
    du, gruppe = T._SPRECHER_DU, T._SPRECHER_GRUPPE
    for n in _chat_nachrichten(conn, chat_id, ziel, anzahl):
        text = (n["text"] or "").strip()
        if n["ist_bot"]:
            if len(text) > CHAT_BOT_ZEICHEN:
                text = text[:CHAT_BOT_ZEICHEN].rstrip() + " [...]"
            zeilen.append(f"{du}: {text}" if text else f"{du}: ({n['typ']})")
        else:
            zeilen.append(f"{gruppe}: {text}" if text else f"{gruppe}: ({n['typ']})")

    notizen = _regienotizen(conn, chat_id, nummer)
    if not zeilen and not notizen:
        return ""
    teile = [T.CHAT_KOPF + "\n" + T.CHAT_ANSCHLUSS]
    if zeilen:
        teile.append("\n".join(zeilen))
    if notizen:
        teile.append(T.CHAT_REGIE_KOPF + "\n" + "\n".join(notizen))
    return "\n\n".join(teile)


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
#: Blockreihenfolge, praezisiert im Prompt-Audit 06.09.2026 (Befund S3): die
#: **Aufgabe dieser Szene** stand hinter Figuren, Continuity und Verworfenem,
#: also nach rund 8.000 Zeichen Material -- und damit hinter dem, was sie
#: eigentlich rahmen soll. Jetzt: erst der Bogen des Stuecks (worin spielt es,
#: wie endet es), dann die Aufgabe genau dieser Szene, dann das Material
#: (Thema, Kernpaket, Figuren), dann die Continuity, dann die Angaben dieser
#: Szene und zuletzt der Auftrag. Das Ende des Prompts wiegt am schwersten
#: (SPEC § 6.1) -- dort stehen die Angaben, die bindend sind, und der Auftrag.
_REIHENFOLGE = (
    # "laenge" steht direkt hinter "aufgabe" und damit im nie gekuerzten
    # Teil (30.09.2026, Karte R): eine Laengenvorgabe, die die
    # Kuerzungsleiter wegwerfen darf, ist keine.
    "format_rahmen", "aufgabe", "laenge", "thema", "kernpaket", "figuren",
    "continuity", "verworfen", "chat", "diese_szene", "auftrag",
)


def _zusammen(bloecke: dict) -> str:
    return "\n\n".join(bloecke[k] for k in _REIHENFOLGE if bloecke.get(k))


def _kernpaket_ohne_begruendungen(text: str) -> str:
    """Streicht die Klammer-Begruendungen aus den Kernpaket-Zeilen -- die
    Zitate bleiben, weil sie die Sprechweise tragen; die Begruendung war die
    Auswahlentscheidung der Gruppe und steht auch im Journal."""
    return re.sub(r'"\)?\s+\([^()]*\)\s*$', '"', text, flags=re.MULTILINE)


def _figuren_mit_wenig_zitaten(text: str) -> str:
    """Laesst je Figur hoechstens ``SPRACHPROFIL_ZITATE_MAX`` Zitatzeilen
    stehen. Letzte Kuerzungsstufe -- drei Zitate reichen als Few-Shot fuer
    eine Sprechweise, null reichten nicht (Audit-Befund S4: ein Prompt, der
    Zitate ankuendigt und keine liefert, laesst das Modell welche
    erfinden)."""
    zeilen, gezaehlt = [], 0
    for zeile in text.splitlines():
        ist_zitat = zeile.startswith('  "')
        if not ist_zitat:
            gezaehlt = 0
            zeilen.append(zeile)
            continue
        gezaehlt += 1
        if gezaehlt <= SPRACHPROFIL_ZITATE_MAX:
            zeilen.append(zeile)
    return "\n".join(zeilen)


def baue_nutzertext(conn, chat_id: int, auftrag: str, ziel=None, e=None,
                    system: str | None = None) -> str:
    """Baut den Nutzertext des Szenen-Aufrufs -- **Struktur statt Transkript**
    (Birk, 05.09.2026) und **unter einem harten Token-Deckel** (06.09.2026).

    Bloecke in dieser Reihenfolge: Format & Rahmen; die Aufgabe dieser Szene;
    die Laenge dieser Szene (nur mit aktivem Laengenprofil, Karte R);
    Kernthema; das Kernpaket; die Figuren mit Sprachprofil und woertlichen
    Zitaten; die frueheren Szenen (Continuity); was die Gruppe verworfen hat;
    der frische Chat; die Felder DIESER Szene; der Auftrag.

    **Die Kuerzungsleiter** (Birk, 06.09.2026: *"Der komplette Kontext soll
    ausgeschoepft werden koennen, aber gleichzeitig ein Deckel auf den
    Gesamt-Prompt"*). Zuerst steht alles im Volltext da. Passt das nicht unter
    ``nutzer_budget()`` -- ``token_budget()`` minus die Systemanweisung
    ``system`` dieses Laufs, die der Aufrufer mitgibt (30.09.2026; ohne
    ``system`` wird nichts abgezogen) --, wird in dieser Reihenfolge
    gekuerzt:

    1. **Vorszenen, aelteste zuerst**, jeweils auf ihre Zusammenfassung --
       eine nach der anderen, bis es passt. Die juengste Vorszene bleibt
       vollstaendig, solange irgend moeglich: an sie wird angeschlossen.
    2. **Der Chat** auf ``CHAT_NACHRICHTEN_KURZ`` Nachrichten -- nie ganz weg.
    3. **Kernpaket-Begruendungen** (die Zitate bleiben).
    4. **Sprachprofil-Zitate** auf drei je Figur.

    Nie gekuerzt werden Rahmen/Geschichte, die Aufgabe, die Laenge, die
    Angaben dieser Szene und der Auftrag: das ist genau das, was die Gruppe entschieden hat,
    und ein Modell, dem es fehlt, erfindet es (gemessen 05.09.2026 -- Szene in
    einer Kueche statt im Polizeikessel).

    Jede Kuerzung ist ein Vorfall mit Zahlen (``szene_prompt_gekuerzt``), kein
    Chattext: die Gruppe hat davon nichts, das Dashboard alles."""
    nummer = ziel["nummer"] if ziel is not None else nummer_aus_auftrag(auftrag)
    bausteine = _continuity_bloecke(conn, chat_id, nummer)

    def _bloecke(voll: set[int], chat_anzahl: int, kernpaket_kurz: bool,
                 zitate_kurz: bool) -> dict:
        kernpaket = _kernpaket_text(conn, chat_id, ziel)
        if kernpaket_kurz:
            kernpaket = _kernpaket_ohne_begruendungen(kernpaket)
        figuren = _figuren_text(conn, chat_id)
        if zitate_kurz:
            figuren = _figuren_mit_wenig_zitaten(figuren)
        return {
            "format_rahmen": _format_rahmen_text(conn, chat_id),
            "thema": _thema_text(conn, chat_id),
            # Je Szene, nicht global (Umbau 05.09.2026 nachts): die
            # Schaerfungen DIESER Szene und ihrer Figuren.
            "kernpaket": kernpaket,
            "figuren": figuren,
            "continuity": _continuity_text(conn, chat_id, nummer, voll),
            "verworfen": _verworfen_text(conn, chat_id),
            "chat": _chat_text(conn, chat_id, ziel, nummer, chat_anzahl),
            "aufgabe": _aufgabe_text(conn, chat_id, ziel),
            "laenge": _laenge_text(conn, chat_id, ziel),
            "diese_szene": _diese_szene_text(
                conn, ziel, neu=NEU_MARKER in (auftrag or ""),
                vorlage=not schreibt_prosa(conn, chat_id),
                bisher_prosa=BISHER_MARKER in (auftrag or ""),
            ),
            "auftrag": T._AUFTRAG_KOPF + (
                auftrag.replace(NEU_MARKER, "").replace(BISHER_MARKER, "").strip()
            ),
        }

    budget = nutzer_budget(
        szene_claude.ist_aktiv(e, conn, chat_id) if e else False, system
    )
    voll = {b["nummer"] for b in bausteine}
    text = _zusammen(_bloecke(voll, CHAT_NACHRICHTEN, False, False))
    if schaetze_token(text) <= budget:
        return text
    return _kuerze_szenenprompt(
        conn, chat_id, e, _bloecke, bausteine, voll, text, budget, nummer,
        schaetze_token(system or ""),
    )


def _kuerze_szenenprompt(conn, chat_id: int, e, bloecke, bausteine,
                         voll: set, text: str, budget: int, nummer,
                         system_token: int = 0) -> str:
    """Die vier Kuerzungsstufen aus dem Docstring von ``baue_nutzertext``, in
    ihrer Reihenfolge -- jede nur, wenn die vorige nicht gereicht hat.

    Jede Kuerzung ist ein Vorfall mit Zahlen (``szene_prompt_gekuerzt``), kein
    Chattext: die Gruppe hat davon nichts, das Dashboard alles."""
    vorher = len(text)

    # Stufe 1: aelteste Vorszene zuerst auf ihre Zusammenfassung.
    zusammengefasst: list[int] = []
    for b in bausteine:
        if schaetze_token(text) <= budget:
            break
        if b["nummer"] not in voll or not b["volltext"]:
            continue
        voll.discard(b["nummer"])
        zusammengefasst.append(b["nummer"])
        text = _zusammen(bloecke(voll, CHAT_NACHRICHTEN, False, False))

    stufen = []
    if zusammengefasst:
        stufen.append(
            "Vorszenen als Zusammenfassung: "
            + ", ".join(str(n) for n in zusammengefasst)
        )
    # Stufen 2-4, jede nur wenn die vorige nicht reichte.
    chat_anzahl, kernpaket_kurz, zitate_kurz = CHAT_NACHRICHTEN, False, False
    for name, setzen in (
        (f"Chat auf {CHAT_NACHRICHTEN_KURZ} Nachrichten", "chat"),
        ("Kernpaket ohne Begruendungen", "kernpaket"),
        (f"Sprachprofil auf {SPRACHPROFIL_ZITATE_MAX} Zitate je Figur", "zitate"),
    ):
        if schaetze_token(text) <= budget:
            break
        if setzen == "chat":
            chat_anzahl = CHAT_NACHRICHTEN_KURZ
        elif setzen == "kernpaket":
            kernpaket_kurz = True
        else:
            zitate_kurz = True
        text = _zusammen(bloecke(voll, chat_anzahl, kernpaket_kurz, zitate_kurz))
        stufen.append(name)

    _melde_kuerzung(conn, chat_id, e, nummer, vorher, text, budget, stufen,
                    system_token)
    return text


def _melde_kuerzung(conn, chat_id: int, e, nummer, vorher: int, text: str,
                    budget: int, stufen: list, system_token: int = 0) -> None:
    """Der Vorfall zur Kuerzung -- mit Zahlen und den durchlaufenen Stufen."""
    abzug = (
        f", Systemanweisung {system_token} Token schon abgezogen"
        if system_token else ""
    )
    detail = (
        f"Szene {nummer if nummer is not None else '?'}: Prompt gekuerzt "
        f"{vorher} -> {len(text)} Zeichen "
        f"({schaetze_token(text)} von {budget} Token{abzug}). "
        + "; ".join(stufen)
    )
    if schaetze_token(text) > budget:
        detail += " -- REICHT IMMER NOCH NICHT"
    log.warning("Szenen-Prompt gekuerzt: %s", detail)
    try:
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None),
            "szene_prompt_gekuerzt", detail,
        )
    except Exception:
        log.exception("Vorfall szene_prompt_gekuerzt nicht geschrieben")


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


def _kopfwert_einer(zeile: str, schluessel: tuple[str, ...]) -> str | None:
    """``_kopfwert`` fuer den ersten passenden Schluessel -- deutsch zuerst
    (Karte A1, K5)."""
    for s in schluessel:
        wert = _kopfwert(zeile, s)
        if wert is not None:
            return wert
    return None


def zerlege(text: str) -> tuple[str | None, str | None, str | None, str | None, str]:
    """Trennt die Kopfzeilen der Modellantwort vom Szenentext.

    Liefert ``(titel, kurzbeschreibung, zusammenfassung, anders_gemacht,
    volltext)``; alles ausser dem Volltext kann None sein. Fehlt der Kopf ganz,
    ist der gesamte Text die Szene -- ein fehlender Titel ist kein Grund, einen
    fertigen Szenentext wegzuwerfen. Der Aufrufer setzt dann 'Szene N' ein.

    ``ZUSAMMENFASSUNG`` und ``ANDERS GEMACHT`` sind seit dem 06.09.2026
    Pflichtzeilen (``prompts/szene.md``, Abschnitt "Deine Ausgabe"). Sie kommen
    vom Szenen-Modell selbst mit und kosten deshalb keinen zweiten Aufruf --
    genau der Punkt: das Modell hat den Text gerade geschrieben und weiss am
    besten, was in ihm passiert und was es wegen des Chats anders gemacht hat.
    Haelt es sich nicht daran, ist das kein Fehler des Laufs: der Aufrufer
    meldet einen Vorfall, und der Prompt faellt spaeter auf Stichzeilen plus
    Schluss zurueck (``_zusammenfassung_fuer``).

    ``ANDERS GEMACHT: nichts`` wird zu ``None`` -- eine Journalzeile "Szene 3:
    nichts" waere Rauschen."""
    zeilen = text.splitlines()
    titel = kurz = fassung = anders = None
    ab = 0
    for i, zeile in enumerate(zeilen[:_KOPFZEILEN]):
        if not zeile.strip():
            ab = i + 1
            continue
        wert = _kopfwert_einer(zeile, _TITEL_SCHLUESSEL)
        if wert is not None and titel is None:
            titel, ab = wert, i + 1
            continue
        wert = _kopfwert_einer(zeile, _KURZ_SCHLUESSEL)
        if wert is not None and kurz is None:
            kurz, ab = wert, i + 1
            continue
        wert = _kopfwert_einer(zeile, _ZUSAMMENFASSUNG_SCHLUESSEL_BEIDE)
        if wert is not None and fassung is None:
            fassung, ab = wert, i + 1
            continue
        wert = _kopfwert_einer(zeile, _ANDERS_SCHLUESSEL_BEIDE)
        if wert is not None and anders is None:
            anders, ab = wert, i + 1
            continue
        break

    volltext = "\n".join(zeilen[ab:]).strip()
    if anders and anders.strip().lower().strip(".") in (
            _ANDERS_NICHTS + _ANDERS_NICHTS_EN):
        anders = None
    return (titel or None), (kurz or None), (fassung or None), (anders or None), volltext


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
        repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
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

    _sende_und_merke(conn, tg, e, chat_id, T._TEXT_ANGEBOT_USA)
    try:
        knoepfe.biete_szene_usa(conn, tg, chat_id)
    except Exception:
        log.exception("USA-Knoepfe fehlgeschlagen, chat_id=%s", chat_id)


def _pruefe_budget(conn, chat_id: int, ueber_claude: bool) -> None:
    """Vergleicht die TATSAECHLICHEN Eingabe-Token des gerade gebuchten Laufs
    mit dem Budget und warnt ab ``BUDGET_WARNSCHWELLE``.

    Der Sinn ist, dass die Herleitung oben (Zeichen ÷ 1,9, Fenster minus
    Ausgabedeckel, 25 % Reserve) im Betrieb **messbar** bleibt statt geglaubt
    zu werden: der Anbieter sagt nach jedem Aufruf, wie viele Token die
    Eingabe wirklich hatte -- System UND Nutzertext, also genau das, was
    ``token_budget`` seit dem 30.09.2026 bemisst. Laeuft die Schaetzung auseinander, faellt es hier
    auf, bevor die API mit HTTP 400 antwortet.

    Reine Beobachtung: ein Fehlschlag beim Lesen darf einen fertigen
    Szenentext nicht mitreissen."""
    budget = token_budget(ueber_claude)
    try:
        zeile = conn.execute(
            "SELECT tatsaechliche_token, geschaetzte_token FROM aufruf "
            "WHERE art = ? AND chat_id = ? ORDER BY id DESC LIMIT 1",
            (ART, chat_id),
        ).fetchone()
    except Exception:
        log.exception("Budgetpruefung: aufruf nicht lesbar")
        return
    if zeile is None:
        return
    echt = zeile["tatsaechliche_token"] or 0
    if not echt:
        return
    anteil = echt / budget
    if anteil >= BUDGET_WARNSCHWELLE:
        log.warning(
            "Szenen-Prompt bei %.0f %% des Budgets: %d von %d Token "
            "(geschaetzt %s) -- Herleitung pruefen",
            anteil * 100, echt, budget, zeile["geschaetzte_token"],
        )
        try:
            repo.merke_vorfall(
                conn, chat_id, None, "szene_budget_knapp",
                f"Eingabe {echt} von {budget} Token ({anteil:.0%})",
            )
        except Exception:
            log.exception("Vorfall szene_budget_knapp nicht geschrieben")
    else:
        log.info("Szenen-Prompt: %d von %d Token (%.0f %%)", echt, budget, anteil * 100)


def schreibe(conn, tg, klm, e, chat_id: int, auftrag: str,
             art: str = ART, bei_teil=None) -> int:
    """Der eigentliche Szenen-Aufruf: Prompt bauen, Modell fragen, Szene
    speichern, Journal schreiben, Vorschau in die Gruppe schicken. Liefert
    die Nummer der geschriebenen Szene.

    Laeuft im Thread aus ``starte()``; wer sie direkt aufruft (Tests, ein
    kuenftiger Stapellauf), bekommt sie synchron und muss sich selbst um die
    Sperre kuemmern. Fehler fliegen heraus -- ``_lauf()`` faengt sie.

    ``art`` (30.09.2026, Karte R) landet in der Tabelle ``aufruf``. Der
    Nachpass setzt ``szene_nachpass``, damit sich seine Laeufe getrennt zaehlen
    lassen -- wie ``dramaturgie_b1`` es vormacht. Ohne Angabe bleibt es
    ``ART``.

    ``bei_teil`` (Karte W, Fix-Runde 1): die Senke des laufenden Texts. Sie
    legt **nur** ``_lauf`` an -- der Lauf, den die Gruppe bestellt hat. Der
    Nachpass, die Dramaturgie-Schleife und die Simulation rufen ``schreibe``
    ohne sie und streamen deshalb nicht (AGENTS.md: vom Nachpass erfaehrt
    die Gruppe nichts). Abgeschlossen wird sie hier, sobald feststeht, ob
    ein Szenentext da ist; ein Fehler davor faellt an ``_lauf``, das sie
    verwirft."""
    ziel = ziel_fuer(conn, chat_id, auftrag)
    nummer = ziel["nummer"]

    # **Phase 6 schreibt eine Geschichte, Phase 7 den Theatertext**
    # (06.09.2026, 10:30, Birk). In Phase 6 geht IMMER prosa.md in die
    # Systemanweisung -- die Form der Szene ist dort noch gar nicht
    # entschieden (``form`` bleibt NULL, ``form_vorschlag`` ist eine Notiz
    # fuer den Feinschliff).
    prosa_lauf = schreibt_prosa(conn, chat_id)
    form = PROSA if prosa_lauf else ziel["form"]
    # Der Stil der Szene (06.09.2026, 12:50) -- gewaehlt im Feinschliff, im
    # Prosalauf ohne Wirkung (``systemanweisung`` laesst ihn dort weg).
    stil = ziel["stil"] if "stil" in ziel.keys() else None
    # Die Anweisung zuerst: ihr Umfang geht vom Budget des Nutzertexts ab
    # (Kalibrierung 30.09.2026 -- Form + Stil bis 19.496 Token).
    system = systemanweisung(form, stil)
    nutzer = baue_nutzertext(conn, chat_id, auftrag, ziel, e, system=system)
    ueber_claude = szene_claude.ist_aktiv(e, conn, chat_id)
    senke = bei_teil
    if ueber_claude:
        antwort = szene_claude.prosa(
            conn, e, getattr(klm, "_klient", None) or httpx.Client(timeout=TIMEOUT_S),
            chat_id, system,
            nutzer, art, timeout=TIMEOUT_S, bei_teil=senke,
        )
    else:
        antwort = klm.prosa(
            chat_id, system,
            nutzer, art, max_tokens=MAX_TOKENS, timeout=TIMEOUT_S, bei_teil=senke,
        )
    _pruefe_budget(conn, chat_id, ueber_claude)

    titel, kurz, fassung, anders, volltext = zerlege(antwort)
    if not volltext:
        # Kein Szenentext ist kein 'fertig' (Fix-Runde 1, Befund 4): die
        # vorlaeufige Blase verschwindet ersatzlos.
        if senke is not None:
            strom.verwirf(tg, chat_id, senke=senke)
        raise SzeneFehler("Antwort des Sprachmodells enthielt keinen Szenentext")
    # Kein ``post_id``: der Szenentext geht nicht als eine Nachricht raus,
    # sondern als Vorschau mit Knopfleiste. 'fertig' ohne post_id heisst fuer
    # die Ansicht schlicht: die vorlaeufige Blase darf weg.
    if senke is not None:
        strom.schliesse(tg, chat_id, senke=senke)

    # Die Zusammenfassung ist Pflichtzeile des Prompts (prompts/szene.md).
    # Fehlt sie, ist der Szenentext trotzdem gut -- gemeldet wird es
    # trotzdem, denn ohne sie faellt jeder spaetere Szenenlauf fuer diese
    # Szene auf Stichzeilen plus Schluss zurueck (_zusammenfassung_fuer).
    if not (fassung or "").strip():
        repo.merke_vorfall(
            conn, chat_id, getattr(e, "bot_name", None),
            "szene_ohne_zusammenfassung",
            f"Szene {nummer}: Modellantwort ohne Pflichtzeile "
            f"'{ZUSAMMENFASSUNG_SCHLUESSEL}:' -- im Prompt greift der Rueckfall",
        )

    # Immer ein UPDATE: die Szene existiert an dieser Stelle bereits, weil
    # ``ziel_fuer`` sie notfalls angelegt hat. Die Planungsfelder bleiben
    # dabei stehen -- ``aktualisiere_szene`` fasst nur Titel, Kurzform,
    # Zusammenfassung und Volltext an.
    #
    # In Phase 6 geht der Text in ``prosa`` und NICHT in ``volltext``: die
    # Geschichte ist kein Theatertext, und ``volltext`` ist die Bedingung
    # dafuer, dass Phase 7 abgeschlossen ist. Die Zusammenfassung kommt in
    # beiden Faellen aus dem gerade geschriebenen Text.
    repo.aktualisiere_szene(
        conn, ziel["id"], titel or ziel["titel"], kurz,
        None if prosa_lauf else volltext, fassung,
        prosa=volltext if prosa_lauf else None,
    )
    # Und zusaetzlich als Fassung ans Ende von ``szenenfassung`` (06.09.2026):
    # "Neu schreiben" ersetzte bis dahin den Volltext, und die Gruppe konnte
    # nicht zurueck. Reines Anhaengen, nie Aendern -- ``szene.volltext``
    # bleibt genau wie bisher die aktuelle Fassung, kein Aufrufer ausserhalb
    # muss etwas anderes lesen. Scheitert es, ist die Szene trotzdem
    # geschrieben: eine verlorene Historienzeile darf keinen bezahlten Lauf
    # kosten.
    try:
        repo.haenge_szenenfassung_an(
            conn, chat_id, ziel["id"], volltext, fassung, anders,
            anbieter="claude" if ueber_claude else "infomaniak",
            modell=(
                (getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE)
                if ueber_claude
                else getattr(e, "llm_modell", None)
            ),
        )
    except Exception:
        log.exception("Szenenfassung nicht angehaengt, chat_id=%s", chat_id)

    titel = titel or T._SZENE_MIT_NUMMER.format(nummer=nummer)
    # Das Journal haelt fest, was gilt (SPEC § 2) -- eine geschriebene Szene
    # ist eine Festlegung der Gruppe, kein Vorschlag. Der Eintrag steht
    # danach im Gespraechs-Prompt und im Szenen-Prompt jedes weiteren Laufs.
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        T._JOURNAL_GESCHRIEBEN.format(nummer=nummer, titel=titel),
        quelle="szene",
    )
    # Was das Modell wegen des Chats anders gemacht hat, wird eine eigene
    # Journalzeile (06.09.2026). Sonst stuende die Freitext-Korrektur der
    # Gruppe ("kuerzer, ohne den Bruder") nur im Chat, waere nach dreissig
    # Minuten aus dem Fenster gerollt und beim naechsten Lauf vergessen.
    if (anders or "").strip():
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            T._JOURNAL_ANDERS.format(nummer=nummer, text=anders.strip()),
            quelle="szene",
        )
    # Der Text geht VOLLSTAENDIG in den Chat (05.09.2026, Birk): lange Texte
    # teilt der Telegram-Wrapper selbst (``telegram.teile_text``), und eine
    # Vorschau von sechs Zeilen war fuer eine Gruppe, die im Raum steht und
    # den Text lesen will, keine Hilfe. Darunter haengen die vier Knoepfe,
    # mit denen die Szene angenommen, geaendert, neu geschrieben oder
    # verlassen wird (``knoepfe.biete_nach_szenentext``) -- vorher stand der
    # Text einfach da und niemand wusste, was jetzt dran ist.
    _sende_szenentext(conn, tg, e, chat_id, nummer, titel, volltext)
    return nummer


def _sende_szenentext(conn, tg, e, chat_id: int, nummer: int, titel: str,
                      volltext: str) -> None:
    """Der Szenentext samt der Vier-Knopf-Leiste darunter.

    Faellt die Tastatur aus (alte Telegram-Attrappe, Telegram-Fehler), geht
    der Text trotzdem raus -- dieselbe Fehlerhaltung wie bei der
    Speicher-Leiste in ``ablauf.antworte``: die Szene ist wichtiger als ihre
    Knoepfe."""
    from interview_theater import knoepfe

    text = T._TEXT_SZENENTEXT.format(nummer=nummer, titel=titel, volltext=volltext)
    try:
        message_id = knoepfe.biete_nach_szenentext(conn, tg, chat_id, nummer, text)
        repo.merke_bot_zeile(conn, chat_id, message_id, e, text)
    except Exception:
        log.exception("Szenentext-Leiste fehlgeschlagen, chat_id=%s", chat_id)
        _sende_und_merke(conn, tg, e, chat_id, text)



#: Waehrend der Szenenlauf laeuft (1-3 Minuten Opus), zeigt der Bot, dass er
#: arbeitet (Birk, 06.09.2026: "so ein witziges Emoji, dass er arbeitet"):
#: alle ~4 s die Tippanzeige (sie verfaellt nach 5 s), und alle 40 s eine
#: kleine Zeile mit wechselndem Emoji, die am Ende wieder geloescht wird.
#: **Zusammengefasst am 06.09.2026** (Birk, 11:15): die wechselnde Zeile
#: waehrend eines Szenenlaufs ist dieselbe Umsetzung wie ueberall sonst
#: (``arbeitszeilen.Lauf``). Hier steht nur noch, WELCHE Liste gilt: die
#: Prosa-Zeilen, weil ein Szenenlauf Prosa schreibt.
ARBEITSART = "prosa"


def _lauf(conn, tg, klm, e, chat_id: int, auftrag: str,
          sperre: threading.Lock, art: str = ART) -> None:
    """Der Thread-Rumpf: ``schreibe()`` mit Fehlerbehandlung und garantierter
    Freigabe der Sperre. Bliebe sie bei einem Fehlschlag liegen, koennte die
    Gruppe fuer den Rest des Workshops keine Szene mehr schreiben lassen.

    **Und, seit dem 30.09.2026 (Karte R), der Nachpass**: nachzaehlen und
    Sprachmuster pruefen, und wenn etwas dran ist, GENAU EINEN
    Ueberarbeitungslauf anhaengen. Er steht hier und nicht in ``schreibe``,
    weil er ``schreibe`` selbst ruft -- in ``schreibe`` waere es eine
    Rekursion. Er steht im ``try`` und nicht im ``finally``, weil es nach
    einem gescheiterten Lauf keinen Text gibt, ueber den nachzuzaehlen waere.
    Und er steht **vor** der Freigabe der Sperre, damit ihm kein zweiter
    Szenenlauf derselben Gruppe dazwischenkommt.

    Ein Nachpass auf einem Nachpass gibt es nicht: der ruft ``schreibe``
    direkt und kommt hier nie vorbei."""
    from interview_theater import arbeitszeilen

    zeilen = arbeitszeilen.sichtbar(tg, chat_id, ARBEITSART)
    # Der laufende Text (Karte W). Der Szenenlauf haengt in einem eigenen
    # Thread, und niemand wartet vor dem Bildschirm -- aber im Browser ist
    # "es passiert etwas" der Unterschied zwischen zwei Minuten Stille und
    # zwei Minuten Lesen. Hier und nicht in ``schreibe`` (Fix-Runde 1,
    # Befund 2): der Nachpass ruft ``schreibe`` direkt und soll unsichtbar
    # bleiben.
    senke = strom.senke(tg, chat_id, "szene")
    try:
        nummer = schreibe(conn, tg, klm, e, chat_id, auftrag, art=art,
                          bei_teil=senke)
        # ``art == ART``: der Nachpass nur nach einem GEWOEHNLICHEN Lauf. Er
        # selbst ruft ``schreibe`` direkt und kommt hier nie vorbei -- die
        # Bedingung ist die zweite Wache gegen eine Schleife, kein Ersatz
        # fuer die erste. Ohne aktives Profil ist ``nach_szene`` ein No-Op.
        if art == ART:
            from interview_theater import nachpass

            # Eigenes ``try`` (Schlussreview I1): die Szene ist hier schon
            # gespeichert und verschickt. Reisst der Nachpass, ist das ein
            # Vorfall und keine "fehlgeschlagen"-Zeile an die Gruppe -- er ist
            # eine Zugabe, auf die niemand wartet (SPEC § 11.1).
            try:
                nachpass.nach_szene(conn, tg, klm, e, chat_id, nummer)
            except Exception:
                log.exception("Nachpass gescheitert, chat_id=%s, Szene %s",
                              chat_id, nummer)
                nachpass._vorfall(conn, chat_id, e, nachpass.VORFALL_FEHLER,
                                  f"Szene {nummer}: Nachpass gescheitert")
    except Exception:
        log.exception("Szenen-Aufruf fehlgeschlagen, chat_id=%s", chat_id)
        # Ueber die Senke selbst, nicht ueber die Gruppe: ein Gespraechszug,
        # der gerade daneben streamt, bleibt unberuehrt (Befund 1). Ist sie
        # schon abgeschlossen, passiert nichts.
        if senke is not None:
            strom.verwirf(tg, chat_id, senke=senke)
        try:
            repo.merke_vorfall(
                conn, chat_id, getattr(e, "bot_name", None), "szene_fehlgeschlagen",
                "Szenen-Aufruf fehlgeschlagen",
            )
        except Exception:
            log.exception("Vorfall zum Szenen-Fehler nicht schreibbar, chat_id=%s", chat_id)
        # Anders als beim Absichtserkenner erfaehrt die Gruppe davon: sie hat
        # gerade die Ankuendigung bekommen und wartet (SPEC § 11.1).
        _sende_und_merke(conn, tg, e, chat_id, T._TEXT_FEHLER)
    finally:
        zeilen.stoppe()
        sperre.release()


def starte(conn, tg, klm, e, chat_id: int, auftrag: str,
           art: str = ART) -> threading.Thread | None:
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

    # Chronologie-Sperre (05.09.2026): geschrieben wird immer nur die
    # kleinste Szene ohne Volltext. Nennt der Auftrag eine spaetere, sagt der
    # Bot EINEN Satz und schreibt die frueheste offene -- keine Rueckfrage,
    # keine Abfuhr. Der Auftragstext wird dabei auf die tatsaechlich
    # geschriebene Szene umgeschrieben, sonst stuende im Prompt "Schreib
    # Szene 3" ueber einer Szene 1.
    gemeint = ziel_fuer(conn, chat_id, auftrag, chronologisch=False)
    ziel = ziel_fuer(conn, chat_id, auftrag)
    if (
        gemeint is not None
        and ziel is not None
        and gemeint["nummer"] is not None
        and ziel["nummer"] != gemeint["nummer"]
    ):
        _sende_und_merke(
            conn, tg, e, chat_id,
            T._TEXT_ERST_FRUEHERE.format(
                nummer=gemeint["nummer"], vorher=ziel["nummer"],
            ),
        )
        auftrag = T.TEXT_AUFTRAG_SCHREIBEN.format(nummer=ziel["nummer"])

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
            _sende_und_merke(conn, tg, e, chat_id, T._TEXT_USA_ERINNERUNG)
            return None
        repo.setze_szene_usa(conn, chat_id, False)
        _usa_erinnerungen.pop(chat_id, None)
        _sende_und_merke(conn, tg, e, chat_id, T._TEXT_USA_KEINE_ANTWORT)

    sperre = _sperre_fuer(chat_id)
    if not sperre.acquire(blocking=False):
        _sende_und_merke(conn, tg, e, chat_id, T._TEXT_BESETZT)
        return None

    if szene_claude.ist_aktiv(e, conn, chat_id):
        _sende_und_merke(conn, tg, e, chat_id, T._TEXT_WARNUNG_USA)
    _sende_und_merke(conn, tg, e, chat_id, T._TEXT_ANGEKUENDIGT)
    # Hinweis, keine Sperre: die Szene wird trotzdem geschrieben.
    hinweis = neue_figuren_hinweis(conn, chat_id, ziel)
    if hinweis:
        _sende_und_merke(conn, tg, e, chat_id, hinweis)
    thread = threading.Thread(
        target=_lauf, args=(conn, tg, klm, e, chat_id, auftrag, sperre, art),
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        # Kommt der Thread nicht hoch, gibt ihn auch niemand mehr frei --
        # dann bliebe die Sperre bis zum Prozessende liegen.
        sperre.release()
        raise
    return thread


from interview_theater import sprache  # noqa: E402  (bewusst unten: kein Zyklus)
T = sprache.Texte(__name__)

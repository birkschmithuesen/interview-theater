"""Inline-Knoepfe fuer die drei Auswahl-Momente (05.09.2026).

**Warum es das gibt.** Die Sprachnavigation ist an Auswahl-Momenten
unzuverlaessig -- gemessen am 05.09.2026: der Absichtserkenner
(``erkenner.py``) erkennt eine Kernthema-Festlegung zuverlaessig, wenn er das
ganze Gespraech sieht (3/3), aber live sieht er nur ein Fenster von ein bis
drei Nachrichten. Im Fenster mit der Zustimmung schrieb er ``entschieden``
(eine Journalnotiz) statt ``kernthema_setzen`` (ein Arbeitsstand-Feld). Die
Festlegung landete deshalb nicht in der Datenbank und erschien nicht auf der
Weboberflaeche.

Ein Knopf traegt die Auswahl selbst -- es ist nichts zu erraten. Genau
dafuer, und nur dafuer, sind Knoepfe hier gedacht: **drei Stellen**, an denen
die Gruppe aus wenigen benannten Moeglichkeiten waehlt (Kernthema,
Aufnahme an/aus, naechste Phase). Alles andere -- Begriffe, Fragen,
Figurenbeschreibungen -- bleibt bewusst Sprache: dort gibt es keine Liste,
aus der sich waehlen liesse.

**Drei Zusagen, an denen sich dieser Code messen laesst:**

1. ``callback_data`` bleibt unter 64 Bytes (Telegram-Grenze). Ein Knopf
   traegt nur ``k:<id>`` -- der eigentliche Wert (ein Kernthema kann laenger
   sein als die ganze Grenze) steht in der Tabelle ``knopf``. Geprueft wird
   die Grenze in ``telegram.Telegram.sende_mit_knoepfen``, nicht hier.
2. **Kein Modellaufruf.** Wie bei den Slash-Befehlen (``befehle.py``) greift
   ein Knopf frueh und deterministisch: ``bot.schleife`` gibt ihn ab, bevor
   irgendein Kontext gebaut wird. Was ein Modell braucht, geht wie ueberall
   an einen eigenen Thread (``aufnahme.starte_abschluss``).
3. **Idempotent.** Jeder Druck wird ueber ``repo.beanspruche_knopf``
   beansprucht -- ein bedingtes UPDATE, das nur einmal gewinnt. Der zweite
   Druck bekommt eine freundliche Rueckmeldung und loest nichts aus.
"""

import logging
import re

from interview_theater import phasen, repo

log = logging.getLogger(__name__)

#: Praefix in ``callback_data``. Ein Buchstabe, weil daneben nur noch die id
#: Platz hat -- und sie soll auch bei einer sechsstelligen id nicht an die
#: 64-Byte-Grenze stossen (``k:999999`` sind neun Bytes).
PRAEFIX = "k:"

ART_KERNTHEMA = "kernthema"
ART_AUFNAHME = "aufnahme"
ART_PHASE = "phase"
#: Form je Szene (Phase 6) -- dasselbe Ziel wie ``/szene <n> form <wert>``.
#: Der Wert der Knopfzeile traegt beides, durch ':' getrennt: "3:dialog".
ART_SZENENFORM = "szenenform"
#: Einwilligung ins US-Modell -- dasselbe Ziel wie ``/szene usa ja|nein``.
ART_SZENE_USA = "szene_usa"
#: Ein Interview jetzt auswerten -- dasselbe Ziel wie ``/auswerten <N>``. Der
#: ``wert`` traegt die ``aufnahme_id`` des Interview-Kopfes, damit der Druck
#: auch dann noch das gemeinte Interview trifft, wenn inzwischen ein weiteres
#: aufgenommen wurde (05.09.2026).
ART_AUSWERTEN = "auswerten"
#: Arbeitsstand zeigen -- dasselbe Ziel wie ``/stand``.
ART_STAND = "stand"
#: Bedienung zeigen -- dasselbe Ziel wie ``/hilfe``.
ART_HILFE = "hilfe"
#: Die Speicher-Leiste unter einem Vorschlag (05.09.2026): "So speichern"
#: schreibt den Wert aus dem Vorschlagsblock (``vorschlag.py``) in den
#: Arbeitsstand -- ueber dieselben Schreibwege wie ``erkenner.wende_an``.
#: Der ``wert`` traegt beides, durch '|' getrennt: "begriffe|Heimat, Arbeit".
#: '|' und nicht ':', weil ein Kernthema regelmaessig einen Doppelpunkt
#: enthaelt ("Ankommen: zwischen zwei Sprachen").
ART_SPEICHERN = "speichern"
#: "Passt, aber anders" (05.09.2026 abends, Birk): speichert die aktuelle
#: Fassung TROTZDEM -- damit ueberhaupt etwas in der Datenbank steht -- und
#: fragt danach gezielt nach, was anders werden soll. Der ``wert`` traegt
#: wie beim Speichern ``"<art>|<wert>"``.
ART_ANDERS = "anders"
#: "Eigene Idee": speichert NICHT, Tastatur weg, ein Satz. Der ``wert``
#: traegt nur die Art, damit die Leiste als Ganzes verfaellt.
ART_EIGENE = "eigene"
#: Stufe 1 der zweistufigen Kernthema-Wahl: eine grobe Richtung. Speichert
#: ``arbeitsstand.kernthema_richtung`` (NICHT ``kernthema``) und loest einen
#: Gespraechszug im Thread aus, der zu dieser Richtung Formulierungen
#: vorschlaegt.
ART_RICHTUNG = "richtung"
#: Figuren, Ebene 1: "Anzahl aendern" / "Namen aendern" und ihre Auswahl.
ART_FIGUREN_ANZAHL_MENU = "figuren_anzahl_menu"
ART_FIGUREN_ANZAHL = "figuren_anzahl"
#: "Andere Zahl" in der Figurenanzahl-Frage: kein Wert, sondern ein
#: Merkposten -- die naechste Nachricht der Gruppe wird als Zahl gelesen.
ART_FIGUREN_ANZAHL_FREI = "figuren_anzahl_frei"
ART_FIGUREN_NAMEN_MENU = "figuren_namen_menu"
#: Eine bestimmte Entwurfszeile umbenennen (``wert`` ist ihr Index).
ART_FIGUR_NAME_MENU = "figur_name_menu"
#: Ein konkreter Namensvorschlag (``wert`` ist der Name; welche Zeile
#: gemeint ist, steht in ``arbeitsstand.figur_aktuell``).
ART_FIGUR_NAME = "figur_name"
#: Figuren, Ebene 2 -- Figur fuer Figur. Der ``wert`` ist jeweils der Name
#: der Figur, um die es geht.
ART_FIGUR_PASST = "figur_passt"
ART_FIGUR_INTERVIEW_MENU = "figur_interview_menu"
#: Die Auswahl eines Interviews: ``"<Figurname>|<aufnahme_id>"``.
ART_FIGUR_INTERVIEW = "figur_interview"
ART_FIGUR_DUKTUS_MENU = "figur_duktus_menu"
#: Ein konkreter Duktus-Vorschlag (``wert`` ist der Text; die Figur steht in
#: ``arbeitsstand.figur_aktuell``).
ART_FIGUR_DUKTUS = "figur_duktus"
ART_FIGUR_ENTFERNEN = "figur_entfernen"
#: Ein Rahmen-Vorschlag (Phase 5): Ort, Zeit, Anlass in einer Zeile.
ART_RAHMEN = "rahmen"
#: Die proaktive Frage beim Eintritt in eine Phase.
ART_WIR_ZUERST = "wir_zuerst"
ART_SCHLAG_VOR = "schlag_vor"
#: Alle beendeten, aber noch nicht ausgewerteten Interviews nacheinander
#: verdichten -- der Weg aus der Phase-4-Sperre (``phasen.voraussetzungen``).
ART_AUSWERTEN_ALLE = "auswerten_alle"
#: Die Leiste unter JEDEM Teil-Transkript (05.09.2026, Birk nach dem
#: Live-Lauf Gruppe 1): "Interview geht weiter" -- Tastatur weg, eine Zeile,
#: KEIN Modellaufruf. Vorher stand das Transkript einfach da und die Gruppe
#: wusste nicht, ob der Bot noch zuhoert.
ART_TEIL_WEITER = "teil_weiter"
#: Das Gegenstueck: "Interview ist fertig" -- wortgleich dieselbe Wirkung wie
#: "Aufnahme beenden" (``befehle._befehl_aufnahme``), kein zweiter Weg.
ART_TEIL_FERTIG = "teil_fertig"

# --- Phase 6 · Szenen (05.09.2026) ----------------------------------------
#
# Die Knopf-Navigation durch Phase 6 und 7 (``szenenfolge.py``). Sie folgt
# derselben Grundregel wie alles hier: ein Vorschlag steht als Text im Chat,
# darunter haengen Knoepfe, und der Knopf traegt die Entscheidung selbst.
# Freie Nachrichten wirken daneben unveraendert weiter -- die Knoepfe sind
# ein Weg, kein Kaefig (AGENTS.md).

#: Die Szenenfolge speichern -- ``wert`` ist "<weiter|anders>|<Vorschlagstext>".
ART_SZENENFOLGE_SPEICHERN = "szenenfolge_speichern"
#: "Anzahl aendern" oeffnet die vier Zahlknoepfe (kein Modellaufruf).
ART_SZENENFOLGE_ANZAHL = "szenenfolge_anzahl"
#: Eine gewaehlte Anzahl -- stoesst einen neuen Vorschlag an (im Thread).
ART_SZENENFOLGE_ANZAHL_WERT = "szenenfolge_anzahl_wert"
#: "Reihenfolge aendern" -- der Bot fragt, die naechste Nachricht wird
#: eingebaut (``nimm_wunsch_auf``).
ART_SZENENFOLGE_REIHENFOLGE = "szenenfolge_reihenfolge"
#: Eine Szene vorstellen (deterministisch aus der Datenbank) samt Menue.
ART_SZENE_ZEIGEN = "szene_zeigen"
#: "Passt, schreiben" -- die Szene schreiben lassen, oder erst die fehlenden
#: Felder vorschlagen, oder erst die USA-Frage stellen.
ART_SZENE_SCHREIBEN = "szene_schreiben"
#: "Anders planen" -- der Bot fragt, was; die naechste Nachricht wirkt.
ART_SZENE_PLANEN = "szene_planen"
#: "Form aendern" -- oeffnet ``biete_szenenform`` fuer diese Szene.
ART_SZENE_FORM = "szene_form"
#: "Ueberspringen" -- weiches Entfernen der Szene (N3).
ART_SZENE_UEBERSPRINGEN = "szene_ueberspringen"
#: Die vorgeschlagenen Felder EINER Szene speichern -- ``wert`` ist
#: "<nummer>|<Vorschlagstext>".
ART_SZENENFELDER_SPEICHERN = "szenenfelder_speichern"
#: Die vier Knoepfe unter einem fertigen Szenentext.
ART_SZENE_PASST = "szene_passt"
ART_SZENE_ANDERS = "szene_anders"
ART_SZENE_NEU = "szene_neu"
ART_SZENE_NAECHSTE = "szene_naechste"
#: "So lassen" -- die Antwort auf einen Pruef-Vermerk (eine fruehere Szene
#: wurde geaendert). Nimmt den Vermerk zurueck und laesst den Text stehen.
ART_SZENE_SO_LASSEN = "szene_so_lassen"
#: Phase 7 · Durchlauf: eine Szene im Volltext zeigen, das Textbuch als Datei.
ART_DURCHLAUF_SZENE = "durchlauf_szene"
ART_TEXTBUCH = "textbuch"
#: Phase 5 · Geschichte: den Vorschlag (Bogen, Ende, Szenenfolge) speichern.
#: ``wert`` ist "<weiter|anders>|<Vorschlagstext>" wie bei der Szenenfolge.
ART_GESCHICHTE_SPEICHERN = "geschichte_speichern"
#: Phase 6 · Schaerfung: eine Szenen- bzw. Figuren-Schaerfung uebernehmen
#: (``wert`` ist die Szenennummer bzw. der Figurenname), eine weitere Runde
#: anstossen, oder weiter zu den Szenentexten.
ART_SCHAERFUNG_SZENE = "schaerfung_szene"
ART_SCHAERFUNG_FIGUR = "schaerfung_figur"
ART_SCHAERFUNG_RUNDE = "schaerfung_runde"


#: Trennzeichen im ``wert`` der Speicher-Leiste.
TRENNER = "|"

#: Die drei Knoepfe der **Grundleiste** -- sie stehen unter JEDER
#: Vorschlagsnachricht des Bots, in dieser Reihenfolge (05.09.2026 abends,
#: Birk). Der Wortlaut ist Absicht: er sagt, was die Gruppe TUT, nicht was
#: der Bot tut. "So speichern" ist deshalb ueberall durch "Gefaellt uns,
#: weiter" ersetzt.
_TEXT_EIGENE_KNOPF = "Eigene Idee"
_TEXT_ANDERS_KNOPF = "Passt, aber anders"
_TEXT_SPEICHERN_KNOPF = "Gefaellt uns, weiter"
#: "Passt, aber anders" speichert und fragt dann gezielt -- deterministisch,
#: kein Modellaufruf (Zusage 2). Der erste Halbsatz ist die Quittung, der
#: zweite die Frage: eine offene Aufforderung ("sagt mir, was anders sein
#: soll") bekam im Probelauf ein Schulterzucken, die drei Beispiele nicht.
_TEXT_ANDERS = (
    "Gespeichert. Was genau soll anders sein - Wortwahl, Reihenfolge, "
    "etwas raus?"
)
#: "Eigene Idee": nichts gespeichert, der naechste Gruppenbeitrag ist der
#: Vorschlag.
_TEXT_EIGENE = "Erzaehlt - ich baue es ein."
#: Nach einem "Gefaellt uns, weiter": bestaetigen, dann die eine Frage, die
#: den Zwischenraum offenhaelt, bevor der Phasenknopf kommt.
_TEXT_NACH_SPEICHERN_FRAGE = "Wollt ihr noch etwas hinzufuegen, bevor es weitergeht?"
_TEXT_AUSWERTEN_ALLE_KNOPF = "Alle auswerten"
_TEXT_AUSWERTEN_ALLE_LAEUFT = "Ich werte die offenen Interviews aus."
_TEXT_AUSWERTEN_ALLE_NICHTS = "Es ist nichts mehr offen."
#: Die Frage unter dem Weiter-Knopf nach einem Speichern -- eine Frage, kein
#: Wechsel (``phasen.py``: die Phase setzt allein die Gruppe).
_TEXT_WEITER_FRAGE = "Gehen wir weiter?"

#: Was nach dem Speichern in den Chat geht -- die Notiert-Zeile, im selben
#: Wortlaut wie beim Erkenner (``erkenner.baue_meldung``): die Gruppe soll
#: nicht zwei Formen fuer dieselbe Sache lernen.
_NOTIERT = {
    "begriffe": "Begriffe",
    "fragen": "Fragen",
    "kernthema": "Kernthema",
    "kernfrage": "Kernfrage",
    "rahmen": "Setting",
    "geschichte": "Geschichte",
}

#: Hoechstens drei Vorschlaege je Kernthema-Angebot. Mehr ist keine Auswahl
#: mehr, sondern eine Liste, die gelesen werden will -- und die Gruppe steht
#: im Raum vor einem Telefon.
MAX_VORSCHLAEGE = 3

_TEXT_KERNTHEMA_FRAGE = "Welches Kernthema nehmen wir? Tippt eins an - oder sagt mir ein anderes."
_TEXT_KERNTHEMA_KEINE = (
    "Ich habe noch keine Vorschlaege - die entstehen aus den ausgewerteten "
    "Interviews. Ihr koennt mir das Kernthema auch einfach sagen."
)
_TEXT_SCHON_BENUTZT = "Das habe ich schon uebernommen."
_TEXT_UNBEKANNT = "Diesen Knopf kenne ich nicht mehr."
#: Die Knopfbeschriftungen heissen seit 05.09.2026 "Interview", nicht
#: "Aufnahme" (Birk, Live-Lauf Gruppe 3): "Aufnahme klingt, als liefe ein
#: Mikrofon -- es sind Sprachnachrichten." Der Modus, die Klassen und die
#: Tabellen heissen intern weiter aufnahme; geaendert hat sich, was die
#: Gruppe liest.
_TEXT_AUFNAHME_STARTEN = "Interview starten"
_TEXT_AUFNAHME_BEENDEN = "Interview beenden"
#: Die zwei Knoepfe unter einem Teil-Transkript (05.09.2026).
_TEXT_TEIL_WEITER_KNOPF = "Interview geht weiter"
_TEXT_TEIL_FERTIG_KNOPF = "Interview ist fertig"
#: Was "Interview geht weiter" tut: eine Zeile, sonst nichts.
_TEXT_TEIL_WEITER = "Gut, ich hoere weiter zu."
#: Der seltene Fall, dass die Aufnahme schon aus ist, wenn der Knopf kommt.
_TEXT_TEIL_SCHON_AUS = "Die Aufnahme laeuft nicht mehr."

#: Die Ablauf-Erklaerung vor dem Start (05.09.2026, Birk nach Gruppe 3,
#: 16:36). Der Anlass: die Gruppe sagte "wir wollen ein Interview machen",
#: der Gespraechs-Bot schrieb eine eigene Bedienungsanleitung, der Erkenner
#: startete gleichzeitig die Aufnahme -- Text und Knopf widersprachen sich.
#: Seitdem gilt: der Erkenner startet NICHT mehr selbst, er legt diese drei
#: Saetze und den Knopf "Interview starten" hin, und die Gruppe entscheidet.
#: Deterministischer Systemtext, kein Modellaufruf -- und der Gespraechs-Bot
#: erklaert die Bedienung nicht mehr selbst (``prompts/system.md``).
TEXT_ABLAUF = (
    "So geht ein Interview: Tippt \"Interview starten\" an. Schickt dann die "
    "Sprachnachricht oder die Sprachnachrichten eurer Interviewpartnerin - "
    "nach jeder bekommt ihr den abgetippten Text und sagt mir per Knopf, ob "
    "das Interview weitergeht oder fertig ist. Fuer die naechste Person "
    "tippt ihr wieder \"Interview starten\"."
)
#: Die drei Knoepfe der Leiste nach einem beendeten Interview (05.09.2026).
_TEXT_AUSWERTEN_KNOPF = "Auswerten"
_TEXT_NAECHSTE_AUFNAHME_KNOPF = "Naechstes Interview"
_TEXT_STAND_KNOPF = "Stand zeigen"
_TEXT_HILFE_KNOPF = "Hilfe"
#: Der Knopf zeigt auf ein Interview, das es nicht mehr gibt -- nur moeglich,
#: wenn zwischen Angebot und Druck geloescht wurde (scripts/loeschen.py).
_TEXT_AUSWERTEN_UNBEKANNT = "Dieses Interview kenne ich nicht mehr."
#: Nur erreichbar, wenn ein Aufrufer ``behandle()`` ohne ``klm`` benutzt --
#: ein Programmierfehler, aber einer, der die Gruppe nicht ratlos laesst.
_TEXT_AUSWERTEN_UNMOEGLICH = "Ich kann gerade nicht auswerten."

#: Die Phase, in der es ueberhaupt etwas aufzunehmen gibt (``phasen.PHASEN``:
#: "3 · Interviews"). Davor wird gearbeitet, nicht aufgenommen: in Phase 1
#: kommt die im Plenum gesammelte Begriffsliste zum Bot, in Phase 2 werden im
#: Gespraech die Fragen entwickelt -- fuer beides gibt es kein Mikrofon.
#:
#: Anlass (05.09.2026, Birk im laufenden Workshop): "aber direkt schon mit
#: aufnahme starten? nach der begruessung kommt erst die eingabe der begriffe
#: und damit die fragen zu erstellen. hast du die reihenfolge der phasen
#: beachtet?" -- die Einstiegsleiste bot "Aufnahme starten" phasenblind an,
#: als erste und damit naheliegendste Handlung, und schickte die Gruppe zwei
#: Arbeitsschritte zu weit.
PHASE_INTERVIEWS = 3

#: Setting & Figuren (frei erfunden). Der Rahmen wird seit dem Umbau vom
#: 05.09.2026 nachts HIER gesetzt, nicht mehr in einer eigenen Phase.
PHASE_SETTING = 4
#: Rueckwaertskompatibler Name: der Rahmen ist Teil von Phase 4 geworden.
PHASE_RAHMEN = PHASE_SETTING

#: Die Geschichte im Groben (Bogen, Ende, Szenenfolge mit Form).
PHASE_GESCHICHTE = 5
#: Die Schaerfung am Material -- hier kommen die Interviews wieder ins Spiel.
PHASE_SCHAERFUNG = 6
#: Die Phase, in der die Szenentexte entstehen, und die des Durchlaufs.
#: Als Konstanten und nicht als 7 und 8 im Code: eine neunte Phase soll
#: nichts brauchen ausser ``phasen.PHASEN``.
PHASE_SZENEN = 7
PHASE_DURCHLAUF = 8

_TEXT_SZENENFORM_FRAGE = "Welche Form soll Szene {nummer} haben?"
_TEXT_USA_FRAGE_KNOEPFE = "Tippt an, was gelten soll:"
_TEXT_USA_JA_KNOPF = "Ja, US-Modell"
_TEXT_USA_NEIN_KNOPF = "Nein, Schweiz"
_TEXT_USA_JA = (
    "Gut, Szenen kommen ab jetzt vom US-Modell. Ich sage es vor jeder "
    "Szene nochmal."
)
_TEXT_USA_NEIN = "Verstanden, alles bleibt in der Schweiz. Ich frage nicht wieder."

# --- Wortlaut der Phase-6/7-Knoepfe ---------------------------------------
#
# Alle Beschriftungen an einer Stelle: die Gruppe soll fuer dieselbe Sache nie
# zwei Formulierungen lesen, und ein Test soll den Wortlaut pruefen koennen,
# ohne ihn abzuschreiben. Keine Nummern in Phasenknoepfen -- "Weiter zu
# Durchlauf", nicht "Weiter zu Phase 7" (Birk 05.09.2026): die Nummer ist
# Buchhaltung, der Name ist die Sache.

#: Die Grundleiste ist dieselbe wie ueberall (``speicherleiste``) -- die
#: Beschriftungen werden hier NICHT zweitgepflegt, sondern von dort geholt:
#: die Gruppe soll fuer dieselbe Sache nie zwei Formulierungen lesen. Die
#: Aliase stehen trotzdem da, weil die Phase-6-Tests den Wortlaut pruefen,
#: ohne ihn abzuschreiben.
TEXT_WEITER_KNOPF = _TEXT_SPEICHERN_KNOPF
TEXT_ANDERS_KNOPF = _TEXT_ANDERS_KNOPF
TEXT_EIGENE_IDEE_KNOPF = _TEXT_EIGENE_KNOPF
_TEXT_EIGENE_IDEE = _TEXT_EIGENE

#: Szenenfolge.
TEXT_ANZAHL_KNOPF = "Anzahl aendern"
TEXT_REIHENFOLGE_KNOPF = "Reihenfolge aendern"
_TEXT_ANZAHL_FRAGE = "Wie viele Szenen sollen es sein?"
_TEXT_REIHENFOLGE_FRAGE = (
    "Sagt mir, wie die Reihenfolge sein soll - ich baue sie ein."
)
_TEXT_FOLGE_GESPEICHERT = "Notiert, {anzahl} Szenen:"
_TEXT_FOLGE_LEER = (
    "Aus dem Vorschlag konnte ich keine Szenen lesen. Sagt sie mir einfach."
)

#: Szene fuer Szene.
TEXT_SZENE_SCHREIBEN_KNOPF = "Ja, schreiben"
TEXT_SZENE_PLANEN_KNOPF = "Anders planen"
TEXT_SZENE_FORM_KNOPF = "Form aendern"
TEXT_SZENE_UEBERSPRINGEN_KNOPF = "Ueberspringen"
_TEXT_SZENE_PLANEN_FRAGE = "Was soll an dieser Szene anders sein?"
_TEXT_SZENE_UEBERSPRUNGEN = "Szene {nummer} ist raus."
_TEXT_SZENE_UNBEKANNT = "Diese Szene kenne ich nicht mehr."

#: Unter dem fertigen Szenentext.
TEXT_PASST_KNOPF = "Passt"
TEXT_NEU_KNOPF = "Neu schreiben"
TEXT_NAECHSTE_KNOPF = "Naechste Szene"
_TEXT_PASST = "Szene {nummer} steht."
_TEXT_SZENE_ANDERS_FRAGE = (
    "Was soll anders werden? Sagt es mir, dann schreibe ich sie neu."
)
_TEXT_KEINE_NAECHSTE = (
    "Das war die letzte Szene. Wollt ihr sie durchgehen?"
)
#: Der Pruef-Vermerk (Aenderung an einer frueheren Szene, 05.09.2026).
TEXT_SZENE_SO_LASSEN_KNOPF = "So lassen"
_TEXT_SZENE_SO_GELASSEN = "Gut, Szene {nummer} bleibt, wie sie ist."
_TEXT_SPAETERE_GEPRUEFT = (
    "Weil sich Szene {nummer} geaendert hat, sehe ich mir {spaetere} noch "
    "einmal mit euch an - geschrieben habe ich nichts neu."
)

#: Phase 7 · Durchlauf.
TEXT_DURCHLAUF_SZENE_KNOPF = "Szene {nummer} ansehen"
TEXT_TEXTBUCH_KNOPF = "Textbuch als Datei"
_TEXT_TEXTBUCH_BESCHREIBUNG = "Euer Textbuch - alle Szenen in einer Datei."
_TEXT_TEXTBUCH_FEHLER = (
    "Die Datei ist nicht durchgekommen. Ich kann euch die Szenen auch einzeln "
    "schicken."
)
_TEXT_SZENE_OHNE_TEXT = "Szene {nummer} ist noch nicht geschrieben."

#: Phase 5 · Geschichte.
_TEXT_GESCHICHTE_GESPEICHERT = "Notiert, eure Geschichte in {anzahl} Szenen:"
_TEXT_GESCHICHTE_LEER = (
    "Aus dem Vorschlag konnte ich keine Geschichte lesen. Erzaehlt sie mir "
    "einfach."
)

#: Phase 6 · Schaerfung.
TEXT_SCHAERFUNG_RUNDE_KNOPF = "Noch eine Runde"
_TEXT_SCHAERFUNG_LAEUFT = (
    "Ich lege eure Geschichte neben die Interviews und suche, was dazu passt."
)
_TEXT_SCHAERFUNG_UEBERNOMMEN = "Uebernommen: {anzahl} Stellen."
_TEXT_SCHAERFUNG_NICHTS = "Dazu ist gerade nichts offen."
_TEXT_SCHAERFUNG_DURCH = (
    "Das war alles, was ich zuordnen konnte. Wollt ihr noch eine Runde, oder "
    "gehen wir an die Szenentexte?"
)



def _daten(knopf_id: int) -> str:
    """Die ``callback_data`` zu einer Knopf-id."""
    return f"{PRAEFIX}{knopf_id}"


def _id_aus_daten(daten: str) -> int | None:
    """Liest die Knopf-id aus ``callback_data``; None bei allem anderen.

    Tolerant gegenueber Fremdem: in einer Gruppe kann ein anderer Bot
    Knoepfe stehen haben, und ein Knopfdruck aus einer alten Fassung dieses
    Bots (anderes Format) darf die Schleife nicht zum Absturz bringen."""
    if not daten.startswith(PRAEFIX):
        return None
    rest = daten[len(PRAEFIX):]
    return int(rest) if rest.isdigit() else None


def _entferne_tastatur(tg, chat_id, message_id) -> None:
    """Nimmt die Knoepfe unter der Angebotsnachricht weg -- nachdem die
    Wirkung eingetreten ist, nie davor.

    Fehlschlaege werden geschluckt: die Wirkung steht schon in der Datenbank,
    und die Gruppe soll wegen einer misslungenen Kosmetik keine Fehlermeldung
    sehen (global-constraints.md 'Fehlerhaltung')."""
    if message_id is None:
        return
    try:
        tg.entferne_knoepfe(chat_id, message_id)
    except Exception:
        log.warning("Knoepfe entfernen fehlgeschlagen, chat_id=%s", chat_id)


# --- Angebote -------------------------------------------------------------


def kernthema_vorschlaege(conn, chat_id: int) -> list[str]:
    """Bis zu ``MAX_VORSCHLAEGE`` Kernthema-Vorschlaege, rein aus der
    Datenbank -- die Kurzformen der Verdichtungsthemen
    (``verdichtung_thema.kurz``, hoechstens acht Woerter).

    Kein Modellaufruf: die Themen sind schon beim Verdichten eines Interviews
    entstanden und bezahlt, sie hier ein zweites Mal zu erfragen waere ein
    zweiter Aufruf fuer dasselbe Ergebnis. Doppelte fallen raus (zwei
    Interviews koennen dasselbe Thema tragen), die Reihenfolge bleibt die der
    Entstehung -- die aelteste Verdichtung zuerst."""
    gesehen: list[str] = []
    for verdichtung in repo.verdichtungen(conn, chat_id):
        for thema in repo.themen_zu(conn, verdichtung["id"]):
            text = (thema["kurz"] or thema["thema"] or "").strip()
            if text and text not in gesehen:
                gesehen.append(text)
    return gesehen[:MAX_VORSCHLAEGE]


def biete_kernthema(conn, tg, chat_id: int, vorschlaege: list[str] | None = None) -> bool:
    """Bietet die Kernthema-Vorschlaege als Knoepfe an. Liefert False, wenn
    es nichts anzubieten gab -- dann hat der Aufrufer bereits die Zeile
    bekommen, die das erklaert.

    Der Volltext steht in der Beschriftung UND in der Tabelle ``knopf``, nie
    in ``callback_data`` (Zusage 1 im Moduldocstring)."""
    if vorschlaege is None:
        vorschlaege = kernthema_vorschlaege(conn, chat_id)
    vorschlaege = [v for v in vorschlaege if v.strip()][:MAX_VORSCHLAEGE]
    if not vorschlaege:
        tg.sende(chat_id, _TEXT_KERNTHEMA_KEINE)
        return False
    knoepfe = [
        (wert, _daten(repo.lege_knopf_an(conn, chat_id, ART_KERNTHEMA, wert)))
        for wert in vorschlaege
    ]
    tg.sende_mit_knoepfen(chat_id, _TEXT_KERNTHEMA_FRAGE, knoepfe)
    return True


def biete_aufnahme(conn, tg, chat_id: int, text: str, knopf: bool = True) -> int:
    """Haengt den Aufnahme-Umschalter unter ``text``; liefert die
    ``message_id`` der Angebotsnachricht.

    Die message_id wird zurueckgegeben, weil der Erkenner-Pfad
    (``erkenner._melde_interviewmodus``) seine Bestaetigung wie jede andere
    Bot-Nachricht mitschreibt (``repo.merke_nachricht``) und dafuer die id
    braucht -- vorher stand dort ein ``tg.sende``, das sie ohnehin lieferte.

    Die Beschriftung richtet sich nach dem Zustand JETZT: laeuft eine
    Aufnahme, heisst der Knopf "Aufnahme beenden", sonst "Aufnahme starten".
    Die Wirkung ist beide Male dieselbe wie ``/aufnahme`` -- ein Umschalter,
    kein Ein- und ein Ausschalter (befehle._befehl_aufnahme): sonst gaebe es
    zwei Zustaende und drei Bedienelemente, und genau daran ist die
    gesprochene Variante am 05.09.2026 gescheitert.

    ``knopf=False`` schickt denselben Text OHNE Tastatur (05.09.2026,
    Live-Fall Gruppe 1, 14:21): unter der Startbestaetigung ("Aufnahme
    laeuft ...") hing bis dahin sofort "Aufnahme beenden" -- sieben Sekunden
    spaeter war er gedrueckt, und es entstand ein leeres Interview. Die
    Beenden-Moeglichkeit kommt seitdem erst mit dem ersten Teil-Transkript
    (``biete_nach_teil``), also dann, wenn es ueberhaupt etwas zu beenden
    gibt."""
    if not knopf:
        return tg.sende(chat_id, text)
    laeuft = repo.ist_interviewmodus_an(conn, chat_id)
    beschriftung = _TEXT_AUFNAHME_BEENDEN if laeuft else _TEXT_AUFNAHME_STARTEN
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)
    return tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def biete_nach_teil(conn, tg, chat_id: int, text: str) -> int:
    """Die Leiste unter einem Teil-Transkript: "Interview geht weiter" ·
    "Interview ist fertig" (05.09.2026, Birk nach dem Live-Lauf Gruppe 1).

    Der gemessene Fall: nach dem Echo "Interview 4, Teil 1: ..." stand das
    Transkript einfach da. Die Gruppe im Raum konnte nicht sehen, ob der Bot
    weiter aufnimmt oder ob das Interview zu Ende ist -- Birk: "das sollte
    aktiv als naechste Antwort angeboten werden nach dem Transkript, nicht
    mit Transkript einfach so stehen lassen."

    Zwei Knoepfe, beide ohne Modellaufruf: "geht weiter" nimmt nur die
    Tastatur ab und sagt einen Satz, "ist fertig" ist wortgleich derselbe
    Weg wie "Aufnahme beenden" (``befehle._befehl_aufnahme``).

    Ein neues Echo nimmt der vorherigen Leiste die Tastatur ab
    (``_nimm_alte_leiste_ab``): sonst staenden nach fuenf Sprachnachrichten
    fuenf Leisten im Chat, und ein Druck auf die von vor drei Nachrichten
    beendete das Interview, ohne dass jemand das gemeint haette.

    Liefert die ``message_id`` der Echo-Nachricht."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_WEITER)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_TEIL_FERTIG)
    leiste = [
        (
            _TEXT_TEIL_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_WEITER, None)),
        ),
        (
            _TEXT_TEIL_FERTIG_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEIL_FERTIG, None)),
        ),
    ]
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def biete_phase(conn, tg, chat_id: int, text: str, nummer: int) -> None:
    """Haengt "Weiter zu Phase N" unter ``text``.

    Bewusst genau EIN Ziel und nicht die ganze Phasenliste: das Angebot ist
    eine Frage ("gehen wir weiter?"), keine Navigation. Zurueckspringen bleibt
    ``/phase 4`` -- selten genug, und ein Knopf je Phase machte aus dem
    Angebot ein Menue."""
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    beschriftung = f"Weiter zu {phasen.knopfbezeichnung(nummer)}"
    tg.sende_mit_knoepfen(chat_id, text, [(beschriftung, _daten(knopf_id))])


def _phasenknopf(conn, chat_id: int) -> tuple[str, str] | None:
    """Der Knopf "Weiter zu Phase N", wenn die Materiallage eine hoehere
    Stufe hergibt -- sonst None (``phasen.naechste_moegliche``, reine
    Leseabfrage).

    Die Sperre fuer Phase 4 steckt in ``phasen.voraussetzungen``, nicht
    hier: solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    ``naechste_moegliche`` die 4 gar nicht erst her -- an allen drei Stellen
    zugleich (diese Funktion, ``biete_nach_aufnahme``,
    ``kontext._baue_phasenhinweis``)."""
    nummer = phasen.naechste_moegliche(conn, chat_id)
    if nummer is None:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_PHASE, str(nummer))
    return (f"Weiter zu {phasen.knopfbezeichnung(nummer)}", _daten(knopf_id))


def _auswerten_alle_knopf(conn, chat_id: int, ausser: int | None = None) -> tuple[str, str] | None:
    """"Alle auswerten", solange ein beendetes Interview ohne Verdichtung
    offen ist -- sonst None.

    Das Gegenstueck zur Phase-4-Sperre: wo "Weiter zu Phase 4" wegfaellt,
    soll nicht einfach nichts stehen, sondern der Weg dorthin.

    ``ausser`` nimmt das Interview aus, fuer das schon ein eigener
    "Auswerten"-Knopf danebensteht (``biete_nach_aufnahme``): zwei Knoepfe
    fuer dieselbe eine Auswertung waeren keine Auswahl, sondern eine
    Verdopplung -- die Gruppe steht im Raum und trifft den ersten."""
    from interview_theater import aufnahme

    offen = [
        kopf for kopf in aufnahme.unausgewertete_interviews(conn, chat_id)
        if kopf["id"] != ausser
    ]
    if not offen:
        return None
    knopf_id = repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN_ALLE, None)
    return (_TEXT_AUSWERTEN_ALLE_KNOPF, _daten(knopf_id))


def _nimm_alte_leiste_ab(conn, tg, chat_id: int, art: str) -> None:
    """Nimmt die Tastatur einer aelteren, ungedrueckten Speicher-Leiste
    derselben Art ab, bevor eine neue kommt.

    Warum: der Wert steckt im Knopf, nicht im Text. Nach drei Vorschlaegen
    staenden sonst drei Leisten im Chat, und ein Druck auf die von vor zwei
    Nachrichten speicherte den ueberholten Vorschlag -- genau die Sorte
    stiller Fehler, gegen die die Knoepfe angetreten sind. Die alten
    Knopfzeilen werden zusaetzlich als benutzt gestempelt
    (``repo.verfallen_lassen``), damit sie auch dann nicht mehr wirken, wenn
    die App die Tastatur noch einen Moment zeigt."""
    alte = repo.offene_knoepfe(conn, chat_id, art)
    if not alte:
        return
    repo.verfallen_lassen(conn, [k["id"] for k in alte])
    for message_id in dict.fromkeys(k["message_id"] for k in alte):
        _entferne_tastatur(tg, chat_id, message_id)


def speicherleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die **Grundleiste** unter einem Vorschlag: "Eigene Idee" · "Passt,
    aber anders" · "Gefaellt uns, weiter" (05.09.2026 abends, Birk).

    ``wert`` ist der Text aus dem Vorschlagsblock (``vorschlag.lies``) --
    exakt der, der beim Druck gespeichert wird. Nichts wird hier
    umformuliert, gekuerzt oder ergaenzt: was die Gruppe im Chat liest, ist
    was in der Datenbank landet.

    **Beide rechten Knoepfe speichern.** "Passt, aber anders" schreibt
    denselben Wert wie "Gefaellt uns, weiter" und fragt danach nach der
    Aenderung -- der Unterschied ist, was DANACH passiert, nicht ob etwas in
    der Datenbank steht. Der Anlass ist gemessen: ein "nochmal anders" ohne
    Speichern liess die Gruppe drei Runden lang mit einem leeren
    Arbeitsstand weiterarbeiten, und beim Abbruch war nichts da.

    Der Volltext steht in der Tabelle ``knopf``, nie in ``callback_data``
    (Zusage 1 im Moduldocstring) -- eine Begriffsliste sprengt die 64 Bytes
    muehelos."""
    eigene = repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)
    anders = repo.lege_knopf_an(
        conn, chat_id, ART_ANDERS, f"{art}{TRENNER}{wert}"
    )
    speichern = repo.lege_knopf_an(
        conn, chat_id, ART_SPEICHERN, f"{art}{TRENNER}{wert}"
    )
    return [
        (_TEXT_EIGENE_KNOPF, _daten(eigene)),
        (_TEXT_ANDERS_KNOPF, _daten(anders)),
        (_TEXT_SPEICHERN_KNOPF, _daten(speichern)),
    ]


#: Die Auswahl-Marker (``vorschlag.ARTEN``), die **oben** in der Leiste je
#: Zeile einen eigenen Knopf ergeben, und die Knopf-Art dazu. Die Grundleiste
#: kommt in jedem Fall darunter.
_AUSWAHLMARKER = {
    "richtungen": ART_RICHTUNG,
    "kernthema": ART_KERNTHEMA,
    "namen": ART_FIGUR_NAME,
    "duktus": ART_FIGUR_DUKTUS,
    "rahmen": ART_RAHMEN,
}

#: Wie viele Auswahlknoepfe hoechstens ueber der Grundleiste stehen. Vier
#: plus drei ist auf dem Telefon noch eine Leiste; mehr ist eine Liste.
MAX_AUSWAHL = 4

#: Fuer welche Auswahl-Marker die Grundleiste den ERSTEN Vorschlag als
#: speicherbaren Wert traegt -- ``"Passt, aber anders"`` braucht einen Wert,
#: und bei einer Liste ist der erste Vorschlag die ehrlichste Wahl (er steht
#: oben und ist der, den das Modell fuer den besten haelt).
_ERSTER_ALS_WERT = {
    "kernthema": "kernthema",
    "rahmen": "rahmen",
}


def _auswahlleiste(conn, chat_id: int, marker: str, wert: str) -> list[tuple[str, str]]:
    """Ein Knopf je Zeile eines Auswahl-Blocks (``VORSCHLAG RICHTUNGEN:`` und
    Verwandte) -- die Zeile ist zugleich Beschriftung und gespeicherter Wert.

    Der Volltext steht wie ueberall in der Tabelle ``knopf``; in
    ``callback_data`` steht nur die id (Zusage 1)."""
    from interview_theater import vorschlag

    art = _AUSWAHLMARKER[marker]
    return [
        (zeile, _daten(repo.lege_knopf_an(conn, chat_id, art, zeile)))
        for zeile in vorschlag.zeilen(wert)[:MAX_AUSWAHL]
    ]


def sende_mit_speicherleiste(conn, tg, chat_id: int, text: str) -> tuple[int, bool]:
    """Schickt eine Bot-Antwort und haengt die Knoepfe darunter
    (05.09.2026). Liefert ``(message_id, leiste?)``.

    Zwei Sorten Knopf, in dieser Reihenfolge:

    1. **Optionsknoepfe oben** -- einer je Zeile eines Auswahl-Blocks
       (``VORSCHLAG RICHTUNGEN:``, ``KERNTHEMA:``, ``NAMEN:``, ``DUKTUS:``,
       ``RAHMEN:``). Sie tragen die Auswahl selbst.
    2. **Die Grundleiste unten** -- "Eigene Idee" · "Passt, aber anders" ·
       "Gefaellt uns, weiter", unter JEDER Vorschlagsnachricht.

    Die Grundleiste braucht einen speicherbaren Wert. Er kommt entweder aus
    dem Block der gerade offenen Art (``offene_art``: Begriffe in Phase 1,
    Fragen in 2, Kernthema/Figuren in 4) oder -- bei einer Auswahlliste --
    aus deren ERSTEM Vorschlag (``_ERSTER_ALS_WERT``). Gibt es weder das eine
    noch das andere, steht die Nachricht ohne Knoepfe da: **kein Raten**,
    lieber keine Knoepfe als welche, die den falschen Text speichern.

    Die Markerzeilen selbst gehen nie in den Chat (``vorschlag.ohne_marker``);
    sie sind Technik zwischen Prompt und Code, kein Inhalt fuer die Gruppe.

    Der Text ist auch ohne Leiste immer derselbe -- das ist wichtig: die
    Gruppe soll nicht daran, ob Knoepfe darunter stehen, ablesen muessen, ob
    das Modell die Form eingehalten hat."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(text) or text
    bloecke = vorschlag.alle(text)

    # Oben: die Auswahlknoepfe. Kommen mehrere Auswahl-Bloecke in einer
    # Nachricht (das Modell soll das nicht, tut es aber gelegentlich),
    # gewinnt der erste aus _AUSWAHLMARKER -- eine feste Ordnung statt einer
    # zufaelligen aus dem Text.
    marker = next((m for m in _AUSWAHLMARKER if m in bloecke), None)

    art = offene_art(conn, chat_id)
    wert = bloecke.get(art) if art else None
    if marker in _ERSTER_ALS_WERT and _ERSTER_ALS_WERT[marker] == art:
        # Eine Auswahlliste: die Grundleiste traegt den ERSTEN Vorschlag,
        # nie die ganze Liste -- "Passt, aber anders" soll einen Rahmen
        # speichern, nicht drei untereinander.
        #
        # **Nur, wenn die Liste zur offenen Art gehoert** (06.09.2026, Birk,
        # Testgruppe 21:50): der Bot hatte in Phase 6 drei Szenenbilder als
        # ``VORSCHLAG RAHMEN:`` angeboten, die Gruppe druckte "Gefaellt uns,
        # weiter" -- und die Leiste ueberschrieb den Rahmen von 21:37 ("Vier
        # Freundinnen im Nordkiez ...") still mit "Leyla checkt ihr Handy auf
        # dem Schulhof". Ohne diese Bedingung speichert jede Liste, die
        # zufaellig einen bekannten Marker traegt, in ein Feld, um das es
        # gerade gar nicht geht.
        erste = vorschlag.zeilen(bloecke[marker])
        if erste:
            wert = erste[0]

    if marker is None and (not art or not wert):
        return tg.sende(chat_id, sauber), False

    oben = _auswahlleiste(conn, chat_id, marker, bloecke[marker]) if marker else []
    if not art or not wert:
        # Auswahlknoepfe ohne speicherbaren Wert (Richtungen, Namen, Duktus):
        # die Grundleiste faellt weg, die Optionen bleiben. "Eigene Idee"
        # kommt trotzdem mit -- ohne sie gaebe es keinen Weg an der Liste
        # vorbei.
        if oben:
            oben.append(
                (
                    _TEXT_EIGENE_KNOPF,
                    _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, marker)),
                )
            )
            message_id = tg.sende_mit_knoepfen(chat_id, sauber, oben)
            repo.merke_knopf_nachricht(
                conn, [_id_aus_daten(d) for _, d in oben], message_id
            )
            return message_id, True
        return tg.sende(chat_id, sauber), False

    if art == "figuren" and not oben:
        # Figuren sind zweistufig (05.09.2026 abends): Ebene 1 ist die Liste
        # mit "Anzahl aendern" und "Namen aendern" -- ein eigener Weg, kein
        # Sonderfall der Grundleiste.
        return biete_figurenliste(conn, tg, chat_id, wert, sauber), True

    if art == "geschichte" and not oben:
        # Die Geschichte traegt Bogen, Ende UND die Szenenfolge; sie geht
        # deshalb ueber ihren eigenen Speicherweg (``_speichere_geschichte``)
        # und nicht ueber den Arbeitsstand-Setter -- sonst staende der
        # Vorschlagstext als ein Feld da und keine Szene in der Tabelle.
        return sende_geschichte(conn, tg, chat_id, text), True

    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_EIGENE)
    leiste = oben + speicherleiste(conn, chat_id, art, wert)
    message_id = tg.sende_mit_knoepfen(chat_id, sauber, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


def offene_art(conn, chat_id: int) -> str | None:
    """Welche Art gerade noch fehlt und deshalb eine Speicher-Leiste
    verdient -- oder None.

    Die Reihenfolge ist die der Arbeit, nicht die des Alphabets, und sie
    haengt an der **Phase**, damit in Phase 1 nicht ploetzlich nach Figuren
    gefragt wird:

    * Phase 1 -- ``begriffe``, solange das Feld leer ist.
    * Phase 2 -- ``fragen``, solange das Feld leer ist.
    * Phase 4 -- ``rahmen`` (das **Setting**: Ort, Zeit, Anlass), solange das
      Feld leer ist; danach ``figuren``, solange die Liste nicht fixiert ist
      (``figuren_fixiert_am`` -- dieselbe Bedingung wie
      ``phasen.voraussetzungen[5]``). Kernthema und Kernfrage stehen hier
      seit dem Umbau vom 05.09.2026 nachts **nicht** mehr: es wird erfunden,
      nicht aus dem Material geschaelt.
    * Phase 5 -- ``geschichte``, solange das Feld leer ist.

    Steht der Wert, gibt es keine Leiste mehr -- **das** ist der Mechanismus
    hinter "die Leiste kommt nach jeder Aenderung wieder": speichert weder
    Knopf noch Erkenner, bleibt das Feld leer, und die naechste Bot-Antwort
    mit einem Vorschlagsblock traegt sie erneut."""
    phase = phasen.aktuelle(conn, chat_id)
    stand = repo.hole_arbeitsstand(conn, chat_id)

    def leer(feld: str) -> bool:
        return not (stand and (stand[feld] or "").strip())

    # "Passt, aber anders" hat gespeichert UND um eine Aenderung gebeten --
    # dann gehoert die Leiste wieder unter die naechste Antwort, obwohl das
    # Feld gefuellt ist. Ohne diese Ausnahme gaebe es keinen Weg, den
    # ueberarbeiteten Vorschlag abzunehmen (05.09.2026 abends).
    offen = (stand["aenderung_offen"] if stand else "") or ""
    if offen:
        return offen

    if phase == 1:
        return "begriffe" if leer("begriffe") else None
    if phase == 2:
        return "fragen" if leer("fragen") else None
    if phase == 4:
        if leer("rahmen"):
            return "rahmen"
        if leer("figuren_fixiert_am"):
            return "figuren"
    if phase == 5 and leer("geschichte"):
        return "geschichte"
    return None


def sende_notiert_mit_leiste(conn, tg, chat_id: int, text: str, art: str,
                             wert: str) -> tuple[int, bool]:
    """Die \"Notiert:\"-Meldung des Erkenners MIT der Grundleiste darunter.

    Der Anlass (Birk, Live-Befund Testgruppe 05.09.2026, 23:37): der
    Erkenner-Nachlauf laeuft NACH der Gespraechsantwort. Speichert er in
    Phase 4 oder 5 eine Ping-Pong-Art, stand die Grundleiste unter der
    Antwort davor -- also unter einem Text, der den Wert noch gar nicht
    kannte, waehrend die Nachricht mit dem Wert nackt dastand. Jetzt haengt
    sie dort, wo der Wert steht: \"Passt, aber anders\" schaerft nach,
    \"Gefaellt uns, weiter\" fixiert, \"Eigene Idee\" macht den Weg frei.

    Die alte Leiste wird abgenommen (``_nimm_alte_leiste_ab``), damit nicht
    zwei im Chat stehen und die aeltere den ueberholten Wert speichert."""
    for alte in (ART_SPEICHERN, ART_ANDERS, ART_EIGENE):
        _nimm_alte_leiste_ab(conn, tg, chat_id, alte)
    leiste = speicherleiste(conn, chat_id, art, wert)
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id, True


def _aufnahme_anbieten(conn, chat_id: int, nur_phase_3: bool = False) -> bool:
    """Darf eine Knopfleiste von sich aus eine Aufnahme ANBIETEN?

    Ja ab ``PHASE_INTERVIEWS`` -- und ja, solange eine Aufnahme laeuft, egal
    in welcher Phase: dann heisst der Knopf "Aufnahme beenden", und ein
    laufendes Interview ohne Ausschalter waere die schlechtere Falle als ein
    Angebot zur falschen Zeit.

    Nein in Phase 1 (Begriffe) und 2 (Fragen). Mit ``nur_phase_3`` auch nein
    ab Phase 4: das ist die Leiste NACH einem Interview
    (``biete_nach_aufnahme``) -- hat die Gruppe inzwischen zum Kernthema
    weitergeschaltet, ist "Naechste Aufnahme" dort kein Angebot mehr, sondern
    ein Rueckschritt. In der Einstiegsleiste bleibt der Knopf dagegen auch
    spaeter stehen: nachtraeglich ein Interview zu ergaenzen ist ein normaler
    Vorgang, nur eben keiner, den der Bot vorschlaegt.

    Das ist ausdruecklich nur eine Regel fuer die ANGEBOTE: ``/aufnahme`` und
    der Erkenner-Pfad (``biete_aufnahme``) bleiben phasenunabhaengig, die
    Gruppe darf jederzeit ausdruecklich aufnehmen (AGENTS.md, "Fokus, kein
    Kaefig"). Nur das unaufgeforderte Angebot richtet sich nach der
    Reihenfolge der Phasen."""
    if repo.ist_interviewmodus_an(conn, chat_id):
        return True
    jetzige = phasen.aktuelle(conn, chat_id)
    if nur_phase_3:
        return jetzige == PHASE_INTERVIEWS
    return jetzige >= PHASE_INTERVIEWS


def biete_nach_aufnahme(conn, tg, chat_id: int, text: str, kopf_id: int | None) -> int:
    """Die Knopfleiste nach einem beendeten Interview (05.09.2026, Birk:
    "ersetze am besten alle slash befehl vorschlaege mit knoepfen. und gib
    auch immer sinnvolle alternativvorschlaege").

    Der gemessene Fall (Gruppe 2, 13:59): ein Interview unter
    ``aufnahme.MINDEST_WOERTER`` endete mit einem Text, der ``/auswerten``
    empfahl; die Gruppe fragte zweimal nach, und ausgewertet wurde nie. Der
    Grund ist derselbe wie ueberall hier: ein empfohlener Slash-Befehl ist
    eine Bedienungsanleitung, ein Knopf ist der Weg.

    Drei Knoepfe, in dieser Reihenfolge -- der wahrscheinlichste zuletzt ist
    hier falsch, weil die Gruppe im Raum steht und den ersten trifft:

    * **Auswerten** -- die Verdichtung dieses Interviews in den Chat. Liegt
      sie schon vor (der Normalfall: verdichtet wird sofort, ausgespielt
      erst auf Wunsch), wird sie aus der Datenbank ausgespielt; liegt keine
      vor (Interview unter der Mindestlaenge), laeuft wortgleich das, was
      ``/auswerten`` tut. Faellt nur weg, wenn es gar kein Interview gibt
      (``kopf_id`` ist None).
    * **Naechste Aufnahme** -- derselbe Umschalter wie ``/aufnahme``, aber
      nur in Phase 3 (``_aufnahme_anbieten(nur_phase_3=True)``): ist die
      Gruppe schon weiter, waere es ein Rueckschritt statt eines Angebots.
    * **Weiter zu Phase N** -- nur, wenn ``phasen.naechste_moegliche`` es
      hergibt. Das ist die Alternative, die im Live-Fall gefehlt hat: statt
      direkt das naechste Interview zu starten, haette die Gruppe auch in die
      Auswertung gehen koennen.

    Kein Modellaufruf, alles aus der Datenbank -- wie jedes Angebot hier.
    Liefert die ``message_id`` der Angebotsnachricht."""
    knoepfe: list[tuple[str, str]] = []
    if kopf_id is not None:
        # Auch wenn schon verdichtet wurde: seit 05.09.2026 geht die
        # Verdichtung NICHT mehr von selbst in den Chat -- der Knopf ist der
        # Weg, sie zu sehen (``aufnahme.zeige_verdichtung``), nicht nur der
        # Weg, sie nachtraeglich zu erzwingen.
        knoepfe.append(
            (
                _TEXT_AUSWERTEN_KNOPF,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUSWERTEN, str(kopf_id))),
            )
        )
    # "Naechste Aufnahme" statt "Aufnahme starten": nach einem beendeten
    # Interview ist genau das gemeint, und der Wortlaut sagt es. Laeuft wider
    # Erwarten schon wieder eine Aufnahme (ein Knopf aus einer alten
    # Nachricht), heisst er wie ueberall "Aufnahme beenden" -- die Wirkung ist
    # in beiden Faellen der Umschalter aus ``/aufnahme``.
    #
    # Seit 05.09.2026 nur noch, wenn die Phase es hergibt
    # (``_aufnahme_anbieten``): ist die Gruppe waehrend des Interviews schon
    # auf 4 (Kernthema & Figuren) weitergegangen, ist "Naechste Aufnahme"
    # kein Angebot mehr, sondern ein Rueckschritt. "Auswerten" und "Weiter zu
    # Phase N" bleiben davon unberuehrt.
    if _aufnahme_anbieten(conn, chat_id, nur_phase_3=True):
        knoepfe.append(
            (
                _TEXT_NAECHSTE_AUFNAHME_KNOPF
                if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    # Solange ein beendetes Interview ohne Verdichtung offen ist, gibt
    # ``phasen.naechste_moegliche`` die 4 nicht her (Phase-4-Sperre) -- an
    # ihre Stelle tritt der Weg dorthin: alle offenen auswerten.
    alle = _auswerten_alle_knopf(conn, chat_id, ausser=kopf_id)
    if alle is not None:
        knoepfe.append(alle)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        knoepfe.append(phasenknopf)
    return tg.sende_mit_knoepfen(chat_id, text, knoepfe)


def biete_einstieg(conn, tg, chat_id: int, text: str) -> int:
    """Die Knopfleiste unter einer Begruessung (Erstkontakt, Wiederkehr):
    "Stand zeigen", "Hilfe" -- und, wenn die Materiallage es hergibt,
    "Weiter zu Phase N".

    "Aufnahme starten" steht seit 05.09.2026 nur noch davor, wenn die Phase
    es hergibt (``_aufnahme_anbieten``): ab Phase 3 (Interviews) oder solange
    eine Aufnahme laeuft. In Phase 1 (Begriffe) und 2 (Fragen) gibt es nichts
    aufzunehmen -- die Begriffe kommen aus dem Plenum als Text oder
    Sprachnachricht, die Fragen entstehen im Gespraech mit dem Bot. Der erste
    Knopf ist der, den die Gruppe im Raum trifft; er darf nicht zwei
    Arbeitsschritte zu weit zeigen.

    Damit steht in der Begruessung selbst kein Slash-Befehl mehr: der Weg ist
    der Knopf, ``/hilfe`` listet die Befehle weiterhin auf, wenn jemand sie
    sucht."""
    knoepfe: list[tuple[str, str]] = []
    if _aufnahme_anbieten(conn, chat_id):
        knoepfe.append(
            (
                _TEXT_AUFNAHME_STARTEN if not repo.ist_interviewmodus_an(conn, chat_id)
                else _TEXT_AUFNAHME_BEENDEN,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_AUFNAHME, None)),
            )
        )
    knoepfe += [
        (
            _TEXT_STAND_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_STAND, None)),
        ),
        (
            _TEXT_HILFE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_HILFE, None)),
        ),
    ]
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        # Direkt hinter der Aufnahme, wenn es sie gibt -- sonst ganz vorn: der
        # Schritt in die naechste Phase ist dann die wahrscheinlichste Absicht.
        knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, phasenknopf)
    else:
        # Kein Phasenknopf, aber offene Auswertungen: dann ist DAS der
        # naechste Schritt (Phase-4-Sperre) -- an derselben Stelle.
        alle = _auswerten_alle_knopf(conn, chat_id)
        if alle is not None:
            knoepfe.insert(1 if _aufnahme_anbieten(conn, chat_id) else 0, alle)
    return tg.sende_mit_knoepfen(chat_id, text, knoepfe)


def biete_szenenform(conn, tg, chat_id: int, nummer: int, text: str | None = None) -> None:
    """Bietet die sechs Formen fuer EINE Szene als Knoepfe an (05.09.2026).

    Warum hier ein Knopf: 553e3aa stellt die Form je Szene in phasen/6.md als
    nummerierte Auswahl. Dieselbe Schwaeche wie beim Format -- "nimm das
    dritte" ist fuer den Erkenner nicht aufloesbar, und eine falsch geratene
    Form fuehrt zu einem Szenentext nach den falschen Dramaturgieregeln
    (``prompts/formen/<name>.md``).

    Die Szenennummer MUSS mitwandern, sonst wuesste der Knopfdruck nicht,
    welche Szene gemeint ist. Sie steht dafuer im ``wert`` der Knopfzeile
    ("3:dialog"), nicht in ``callback_data`` -- dort steht wie ueberall nur
    die Knopf-id. Damit bleibt die 64-Byte-Grenze unabhaengig von Nummer und
    Formnamen eingehalten.

    Die Liste kommt aus ``szene.FORMEN`` und wird hier NICHT zweitgepflegt:
    kommt dort eine Form dazu, gibt es den Knopf automatisch."""
    from interview_theater import szene

    knoepfe = [
        (
            form.capitalize(),
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFORM, f"{nummer}:{form}")),
        )
        for form in szene.FORMEN
    ]
    tg.sende_mit_knoepfen(
        chat_id, text or _TEXT_SZENENFORM_FRAGE.format(nummer=nummer), knoepfe
    )


def biete_szene_usa(conn, tg, chat_id: int, text: str | None = None) -> None:
    """Haengt die beiden Einwilligungsknoepfe unter das USA-Angebot
    (``szene._TEXT_ANGEBOT_USA``).

    Der Anlass ist der teuerste gemessene Fehler des 05.09.2026: der Bot
    fragte nach dem US-Modell, die Gruppe antwortete siebenmal sinngemaess
    "ja" -- der Erkenner las es jedes Mal als Zustimmung zu den FIGUREN, und
    der Bot wiederholte dieselbe Erinnerung, bis der Notausgang
    (``szene.USA_ERINNERUNGEN_MAX``) griff und in der Schweiz schrieb. Eine
    Einwilligung ist genau der Fall, der nicht erraten werden darf: hier
    entscheidet die Gruppe ueber eine Datenuebermittlung.

    Zwei Knoepfe und nicht einer: anders als beim Aufnahme-Umschalter sind
    Ja und Nein zwei verschiedene Entscheidungen mit verschiedenen Folgen,
    und ein Nein muss genauso ein Druck sein wie ein Ja -- sonst waere
    Schweigen die einzige Form der Ablehnung."""
    knoepfe = [
        (_TEXT_USA_JA_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "ja"))),
        (_TEXT_USA_NEIN_KNOPF, _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_USA, "nein"))),
    ]
    tg.sende_mit_knoepfen(chat_id, text or _TEXT_USA_FRAGE_KNOEPFE, knoepfe)


# --- Phase 6 · Szenen: Angebote -------------------------------------------


def grundleiste(conn, chat_id: int, art: str, wert: str) -> list[tuple[str, str]]:
    """Die drei Knoepfe, die unter JEDEM Vorschlag in Phase 6 stehen:
    "Eigene Idee" · "Passt, aber anders" · "Gefaellt uns, weiter".

    ``art`` ist die Knopf-Art, unter der gespeichert wird
    (``ART_SZENENFOLGE_SPEICHERN``, ``ART_SZENENFELDER_SPEICHERN``), ``wert``
    der Text, der beim Druck wirkt -- exakt der, der im Chat steht. Nichts
    wird hier umformuliert (dieselbe Zusage wie in ``speicherleiste``).

    "Gefaellt uns, weiter" und "Passt, aber anders" speichern BEIDE. Der
    Unterschied steht im Praefix des Wertes und wirkt danach: "anders" nimmt
    den Vorschlag an und fragt zugleich, was noch geaendert werden soll -- die
    Gruppe soll einen brauchbaren Vorschlag nicht wegwerfen muessen, nur weil
    ein Detail nicht stimmt (Birk, 05.09.2026)."""
    return [
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, art)),
        ),
        (
            TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"anders{TRENNER}{wert}")),
        ),
        (
            TEXT_WEITER_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, art, f"weiter{TRENNER}{wert}")),
        ),
    ]


def _mit_leiste(conn, tg, chat_id: int, text: str, leiste: list[tuple[str, str]]) -> int:
    """Schickt ``text`` mit ``leiste`` und merkt sich die Nachricht je Knopf --
    damit eine spaetere Leiste die alte abnehmen kann
    (``_nimm_alte_leiste_ab``)."""
    message_id = tg.sende_mit_knoepfen(chat_id, text, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(daten) for _, daten in leiste], message_id
    )
    return message_id


def sende_szenenfolge(conn, tg, chat_id: int, antwort: str) -> int:
    """Der Szenenfolge-Vorschlag im Chat: der Text ohne Markerzeilen, darunter
    "Anzahl aendern" · "Reihenfolge aendern" und die Grundleiste.

    Ohne Marker (``vorschlag.lies``) gibt es KEINE Leiste -- kein Raten:
    lieber ein Vorschlag ohne Knoepfe als Knoepfe, die den falschen Text
    speichern (dieselbe Regel wie in ``sende_mit_speicherleiste``). Die Gruppe
    kann dann immer noch frei antworten; das wirkt ohnehin immer."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "szenenfolge")
    if not wert:
        log.error("Szenenfolge-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENENFOLGE_SPEICHERN)
    leiste = [
        (
            TEXT_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_ANZAHL, None)),
        ),
        (
            TEXT_REIHENFOLGE_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_REIHENFOLGE, None)
            ),
        ),
    ] + grundleiste(conn, chat_id, ART_SZENENFOLGE_SPEICHERN, wert)
    return _mit_leiste(conn, tg, chat_id, sauber, leiste)


def sende_geschichte(conn, tg, chat_id: int, antwort: str) -> int:
    """Der Geschichte-Vorschlag im Chat (Phase 5): Bogen, Ende und
    Szenenfolge, darunter \"Anzahl aendern\" · \"Reihenfolge aendern\" und die
    Grundleiste.

    Derselbe Weg wie ``sende_szenenfolge`` -- ohne Marker keine Leiste, kein
    Raten. Der ``wert`` traegt den ganzen Block: die Geschichte und ihre
    Szenen sind EINE Entscheidung."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "geschichte")
    if not wert:
        log.error("Geschichte-Vorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_GESCHICHTE_SPEICHERN)
    leiste = [
        (
            TEXT_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENENFOLGE_ANZAHL, None)),
        ),
        (
            TEXT_REIHENFOLGE_KNOPF,
            _daten(
                repo.lege_knopf_an(
                    conn, chat_id, ART_SZENENFOLGE_REIHENFOLGE, None
                )
            ),
        ),
    ] + grundleiste(conn, chat_id, ART_GESCHICHTE_SPEICHERN, wert)
    return _mit_leiste(conn, tg, chat_id, sauber, leiste)


# --- Phase 6 · Schaerfung am Material -------------------------------------


def biete_schaerfung(conn, tg, chat_id: int) -> bool:
    """Stellt die naechste offene Schaerfung vor -- erst Szene fuer Szene,
    dann Figur fuer Figur. Liefert True, solange noch eine kam.

    Deterministisch aus der Datenbank (``schaerfung.szenenvorschlag`` /
    ``figurvorschlag``): das Mapping ist schon gelaufen, hier wird nur
    vorgestellt -- kein Modellaufruf im Handler (Zusage 2).

    Ist nichts mehr offen, steht die Frage nach einer weiteren Runde da und,
    wenn die Materiallage sie hergibt, der Weg zu den Szenentexten."""
    from interview_theater import schaerfung as schaerfung_modul

    for szene in repo.hole_szenen(conn, chat_id):
        text = schaerfung_modul.szenenvorschlag(conn, chat_id, szene)
        if text is None:
            continue
        leiste = grundleiste(
            conn, chat_id, ART_SCHAERFUNG_SZENE, str(szene["nummer"])
        )
        _mit_leiste(conn, tg, chat_id, text, leiste)
        return True
    for figur in repo.figuren(conn, chat_id):
        text = schaerfung_modul.figurvorschlag(conn, chat_id, figur)
        if text is None:
            continue
        leiste = grundleiste(conn, chat_id, ART_SCHAERFUNG_FIGUR, figur["name"])
        _mit_leiste(conn, tg, chat_id, text, leiste)
        return True
    leiste = [
        (
            TEXT_SCHAERFUNG_RUNDE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHAERFUNG_RUNDE, None)),
        )
    ]
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        leiste.append(phasenknopf)
    _mit_leiste(conn, tg, chat_id, _TEXT_SCHAERFUNG_DURCH, leiste)
    return False


def starte_schaerfung(conn, tg, klm, e, chat_id: int) -> None:
    """Stoesst das Mapping an (im Thread) und stellt danach die erste
    Schaerfung vor -- der automatische Eintritt in Phase 6.

    Kein Modellaufruf hier: ``schaerfung.starte`` gibt sofort ab (Zusage 2).
    Ohne Sprachmodell (Tests) bleibt der Weg trotzdem offen -- dann wird
    gezeigt, was schon zugeordnet ist."""
    from interview_theater import schaerfung as schaerfung_modul

    def _danach() -> None:
        biete_schaerfung(conn, tg, chat_id)

    tg.sende(chat_id, _TEXT_SCHAERFUNG_LAEUFT)
    if schaerfung_modul.starte(conn, tg, klm, e, chat_id, nachbereitung=_danach) is None:
        biete_schaerfung(conn, tg, chat_id)


def sende_szenenfelder(conn, tg, chat_id: int, nummer: int, antwort: str) -> int:
    """Der Feldvorschlag fuer EINE Szene, mit der Grundleiste darunter.

    Der ``wert`` traegt die Szenennummer mit (\"3|form: Lied\\nort: ...\"):
    zwischen Vorschlag und Druck kann die Gruppe laengst ueber eine andere
    Szene reden, und ein Feldvorschlag, der in der falschen Szene landet, ist
    schlimmer als keiner."""
    from interview_theater import vorschlag

    sauber = vorschlag.ohne_marker(antwort) or antwort
    wert = vorschlag.lies(antwort, "szene")
    if not wert:
        log.error("Feldvorschlag ohne Marker, chat_id=%s", chat_id)
        return tg.sende(chat_id, sauber)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENENFELDER_SPEICHERN)
    leiste = grundleiste(
        conn, chat_id, ART_SZENENFELDER_SPEICHERN, f"{nummer}{TRENNER}{wert}"
    )
    return _mit_leiste(conn, tg, chat_id, sauber, leiste)


def biete_szene(conn, tg, chat_id: int, zeile) -> int:
    """Stellt EINE Szene vor und haengt ihr Menue darunter: "Passt,
    schreiben" · "Anders planen" · "Form aendern" · "Ueberspringen" ·
    "Eigene Idee".

    Deterministisch aus der Datenbank (``szenenfolge.vorstellung``) -- kein
    Modellaufruf. Das Menue kommt nach jeder Aenderung neu: jeder der Knoepfe,
    der etwas an der Szene aendert, ruft am Ende wieder hierher zurueck.

    Steht ein Pruef-Vermerk an dieser Szene (an einer frueheren Szene wurde
    etwas geaendert, ``szenenfolge.zu_pruefen``), sind es zwei andere
    Knoepfe: "Neu schreiben" und "So lassen". Das ist die Frage, die dann
    ansteht -- "Ueberspringen" und "Form aendern" waeren daneben Rauschen."""
    from interview_theater import szenenfolge

    nummer = zeile["nummer"]
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENE_SCHREIBEN)
    if szenenfolge.zu_pruefen(conn, chat_id, nummer):
        leiste = [
            (
                TEXT_NEU_KNOPF,
                _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NEU, str(nummer))),
            ),
            (
                TEXT_SZENE_SO_LASSEN_KNOPF,
                _daten(
                    repo.lege_knopf_an(conn, chat_id, ART_SZENE_SO_LASSEN, str(nummer))
                ),
            ),
        ]
        return _mit_leiste(
            conn, tg, chat_id, szenenfolge.vorstellung(conn, zeile, chat_id), leiste
        )
    leiste = [
        (
            TEXT_SZENE_SCHREIBEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_SCHREIBEN, str(nummer))),
        ),
        (
            TEXT_SZENE_PLANEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_PLANEN, str(nummer))),
        ),
        (
            TEXT_SZENE_FORM_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_FORM, str(nummer))),
        ),
        (
            TEXT_SZENE_UEBERSPRINGEN_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_SZENE_UEBERSPRINGEN, str(nummer))
            ),
        ),
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(
                repo.lege_knopf_an(conn, chat_id, ART_EIGENE, ART_SZENE_SCHREIBEN)
            ),
        ),
    ]
    return _mit_leiste(conn, tg, chat_id, szenenfolge.vorstellung(conn, zeile), leiste)


def biete_nach_szenentext(conn, tg, chat_id: int, nummer: int, text: str) -> int:
    """Die vier Knoepfe unter einem frisch geschriebenen Szenentext: "Passt" ·
    "Passt, aber anders" · "Neu schreiben" · "Naechste Szene".

    Der Anlass (Birk, 05.09.2026): der Szenentext stand im Chat, und danach
    passierte nichts -- die Gruppe wusste nicht, ob sie zustimmen, aendern
    oder weitergehen soll, und der Bot wusste nicht, ob die Szene gilt.
    Deshalb traegt "Passt" seit heute einen eigenen Stempel in der Datenbank
    (``repo.setze_szene_fertig``) und nicht bloss das Vorhandensein eines
    Textes.

    Ist es die letzte Szene und sind alle fertig, steht statt "Naechste
    Szene" der Weg weiter: "Weiter zu Durchlauf" -- ohne Nummer, wie jeder
    Phasenknopf hier."""
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SZENE_PASST)
    leiste = [
        (
            TEXT_PASST_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_PASST, str(nummer))),
        ),
        (
            TEXT_ANDERS_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_ANDERS, str(nummer))),
        ),
        (
            TEXT_NEU_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NEU, str(nummer))),
        ),
        (
            TEXT_NAECHSTE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_SZENE_NAECHSTE, str(nummer))),
        ),
    ]
    return _mit_leiste(conn, tg, chat_id, text, leiste)


def biete_durchlauf(conn, tg, chat_id: int) -> int:
    """Der Eintritt in Phase 7: die Szenenfolge mit Status als Text, darunter
    ein Knopf je Szene, "Textbuch als Datei" und "Eigene Idee".

    Alles deterministisch aus der Datenbank. Der Durchlauf ist eine Ansicht
    auf das, was die Gruppe gebaut hat -- kein Anlass, ein Modell zu fragen."""
    from interview_theater import szenenfolge

    leiste = []
    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is None:
            continue
        leiste.append(
            (
                TEXT_DURCHLAUF_SZENE_KNOPF.format(nummer=s["nummer"]),
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_DURCHLAUF_SZENE, str(s["nummer"])
                    )
                ),
            )
        )
    leiste.append(
        (
            TEXT_TEXTBUCH_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_TEXTBUCH, None)),
        )
    )
    leiste.append(
        (
            TEXT_EIGENE_IDEE_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, ART_TEXTBUCH)),
        )
    )
    return _mit_leiste(conn, tg, chat_id, szenenfolge.uebersicht(conn, chat_id), leiste)


# --- Phase 6 · Szenen: Wirkungen ------------------------------------------


def _szene_mit_nummer(conn, chat_id: int, nummer: int):
    """Die (nicht entfernte) Szene mit dieser Nummer, oder None."""
    return next(
        (s for s in repo.hole_szenen(conn, chat_id) if s["nummer"] == nummer), None
    )


def _naechste_offene(conn, chat_id: int, nach: int):
    """Die naechste Szene nach ``nach``, die noch nicht abgenommen ist -- oder
    None, wenn keine mehr kommt.

    Nicht einfach "die naechste": eine Gruppe, die Szene 2 ueberspringt und
    spaeter zurueckkommt, soll nicht an ihr vorbeigeschickt werden."""
    from interview_theater import szenenfolge

    for s in repo.hole_szenen(conn, chat_id):
        if s["nummer"] is not None and s["nummer"] > nach and not szenenfolge.ist_fertig(s):
            return s
    return None


def _speichere_szenenfolge(conn, tg, klm, e, chat_id: int, roh: str) -> str:
    """Legt aus dem Vorschlag die Szenen an und stellt die erste vor.

    ``roh`` ist ``"<weiter|anders>|<Vorschlagstext>"``. Beide Wege speichern;
    "anders" haengt danach die Frage an, was noch geaendert werden soll -- die
    naechste freie Nachricht wirkt dann ganz normal ueber den Erkenner."""
    from interview_theater import szenenfolge

    modus, _, wert = roh.partition(TRENNER)
    zeilen = szenenfolge.zerlege(wert)
    if not zeilen:
        log.error("Szenenfolge-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_FOLGE_LEER)
        return _TEXT_FOLGE_LEER
    nummern = szenenfolge.lege_an(conn, chat_id, zeilen)
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        "Szenenfolge: " + "; ".join(f"{n}. {z[0]}" for n, z in zip(nummern, zeilen)),
        quelle="knopf",
    )
    tg.sende(chat_id, _TEXT_FOLGE_GESPEICHERT.format(anzahl=len(nummern)))
    if modus.strip() == "anders":
        tg.sende(chat_id, _TEXT_EIGENE_IDEE)
    erste = _szene_mit_nummer(conn, chat_id, nummern[0])
    if erste is not None:
        biete_szene(conn, tg, chat_id, erste)
    return f"{len(nummern)} Szenen uebernommen"


def _speichere_geschichte(conn, tg, chat_id: int, roh: str) -> str:
    """Speichert Bogen und Ende (``arbeitsstand.geschichte``) UND legt die
    Szenenfolge an -- Phase 5, ein Vorschlag, eine Entscheidung.

    Die Szenen entstehen ueber denselben ``szenenfolge.lege_an`` wie bisher:
    es gibt einen Weg, eine Szenenfolge anzulegen, nicht zwei. Danach kommt
    **keine** Szenenvorstellung -- die naechste Station ist die Schaerfung,
    und die Gruppe bekommt dafuer den Phasenknopf."""
    from interview_theater import szenenfolge

    modus, _, wert = roh.partition(TRENNER)
    geschichte, zeilen = szenenfolge.zerlege_geschichte(wert)
    if not geschichte or not zeilen:
        log.error("Geschichte-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_GESCHICHTE_LEER)
        return _TEXT_GESCHICHTE_LEER
    repo.setze_arbeitsstand(conn, chat_id, "geschichte", geschichte)
    nummern = szenenfolge.lege_an(conn, chat_id, zeilen)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Geschichte: {geschichte}", quelle="knopf",
    )
    repo.schreibe_journal(
        conn, chat_id, "entschieden",
        "Szenenfolge: " + "; ".join(f"{n}. {z[0]}" for n, z in zip(nummern, zeilen)),
        quelle="knopf",
    )
    tg.sende(
        chat_id,
        _TEXT_GESCHICHTE_GESPEICHERT.format(anzahl=len(nummern))
        + "\n" + geschichte,
    )
    if modus.strip() == "anders":
        repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", "geschichte")
        tg.sende(chat_id, _TEXT_ANDERS)
        return "Gespeichert, was soll anders sein?"
    repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        _mit_leiste(conn, tg, chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
    else:
        tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
    return f"Geschichte mit {len(nummern)} Szenen uebernommen"


def _speichere_szenenfelder(conn, tg, chat_id: int, roh: str) -> str:
    """Schreibt die vorgeschlagenen Felder in die Szene und stellt sie neu vor.

    ``roh`` ist ``"<nummer>|<Vorschlagstext>"``; der Vorschlagstext ist
    ``feld: Wert`` je Zeile. Gelesen wird ueber ``szene.feldname`` --
    dieselben Aliase wie beim Befehl und beim Erkenner, kein zweites
    Vokabular. Was der Code nicht kennt, wird uebergangen und geloggt: ein
    unbekanntes Feld ist kein Grund, die uebrigen wegzuwerfen."""
    from interview_theater import szene as szene_modul

    roh_nummer, _, wert = roh.partition(TRENNER)
    try:
        nummer = int(roh_nummer)
    except ValueError:
        log.error("Feldvorschlag ohne Nummer, chat_id=%s, roh=%r", chat_id, roh)
        return _TEXT_UNBEKANNT
    szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
    gesetzt = []
    for zeile in wert.splitlines():
        kopf, trenner, rest = zeile.partition(":")
        feld = szene_modul.feldname(kopf)
        if not trenner or not feld or not rest.strip():
            continue
        if feld == "figuren":
            nach_name = {
                f["name"].strip().lower(): f["id"] for f in repo.figuren(conn, chat_id)
            }
            ids = [
                nach_name[n.strip().lower()]
                for n in rest.split(",")
                if n.strip().lower() in nach_name
            ]
            if ids:
                repo.setze_szene_figuren(conn, chat_id, szene_id, ids)
                gesetzt.append(feld)
            continue
        repo.setze_szenenfeld(conn, szene_id, feld, rest.strip())
        gesetzt.append(feld)
    if not gesetzt:
        log.error("Feldvorschlag ohne verwertbares Feld, chat_id=%s", chat_id)
        return _TEXT_UNBEKANNT
    biete_szene(conn, tg, chat_id, repo.hole_szene(conn, szene_id))
    return f"Szene {nummer}: {', '.join(gesetzt)}"


def _schreibe_szene(conn, tg, klm, e, chat_id: int, nummer: int,
                    notiz: str | None = None) -> str:
    """"Passt, schreiben" -- mit den drei Ausgaengen, die es hier gibt:

    1. Es fehlen Pflichtfelder der Szene -> **kein** Sperrtext, sondern ein
       Vorschlag der fehlenden Felder aus dem Material
       (``szenenfolge.starte_feldvorschlag``), mit Grundleiste darunter. Der
       Sperrtext bleibt der richtige Weg beim direkten Schreibauftrag
       (``/szene``), aber wer eine Szene vor Augen hat und "schreiben" tippt,
       soll nicht eine Liste von Luecken bekommen.
    2. Die USA-Einwilligung steht noch aus -> ``szene.starte`` stellt die
       Frage samt Knoepfen und merkt sich den Auftrag; nach der Antwort
       laeuft er automatisch weiter (``erkenner._starte_szene``). Genau das
       Verhalten von heute, nur eingebettet.
    3. Sonst laeuft der Szenenlauf im eigenen Thread -- kein Modellaufruf in
       diesem Handler (Zusage 2)."""
    from interview_theater import szene as szene_modul, szenenfolge

    ziel = _szene_mit_nummer(conn, chat_id, nummer)
    if ziel is None:
        tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
        return _TEXT_SZENE_UNBEKANNT
    fehlende, _ = szene_modul.fehlendes(conn, ziel)
    eigene = [
        f for f in fehlende if f not in szene_modul.ARBEITSSTAND_PFLICHTFELDER
    ]
    if eigene:
        if szenenfolge.starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel) is not None:
            return "Ich schlage die fehlenden Angaben vor"
    auftrag = f"Schreib Szene {nummer}."
    if notiz and notiz.strip():
        auftrag += f" {notiz.strip()}"
    szene_modul.starte(conn, tg, klm, e, chat_id, auftrag)
    return f"Szene {nummer} laeuft"


def _wirke_phase6(conn, tg, klm, e, knopf, chat_id: int) -> str | None:
    """Die Wirkungen der Phase-6- und Phase-7-Knoepfe. Liefert None, wenn die
    Art nicht hierher gehoert -- ``_wirke`` macht dann weiter.

    Ausgelagert, weil ``_wirke`` sonst auf ueber vierhundert Zeilen anwuechse
    und die eine Regel, um die es geht ("kein Modellaufruf im Handler"), im
    Rauschen unterginge."""
    from interview_theater import szenenfolge

    art = knopf["art"]
    wert = str(knopf["wert"] or "")

    if art == ART_SZENENFOLGE_SPEICHERN:
        return _speichere_szenenfolge(conn, tg, klm, e, chat_id, wert)

    if art == ART_GESCHICHTE_SPEICHERN:
        return _speichere_geschichte(conn, tg, chat_id, wert)

    if art == ART_SCHAERFUNG_SZENE:
        # Die Uebernahme ist deterministisch (Felder ergaenzen), der naechste
        # Vorschlag kommt aus der Datenbank -- kein Modellaufruf (Zusage 2).
        from interview_theater import schaerfung as schaerfung_modul

        modus, _, nummer_roh = wert.partition(TRENNER)
        ziel = _szene_mit_nummer(conn, chat_id, int(nummer_roh or wert))
        if ziel is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        anzahl = schaerfung_modul.uebernimm_szene(conn, chat_id, ziel)
        if not anzahl:
            tg.sende(chat_id, _TEXT_SCHAERFUNG_NICHTS)
        else:
            tg.sende(chat_id, _TEXT_SCHAERFUNG_UEBERNOMMEN.format(anzahl=anzahl))
        if modus.strip() == "anders":
            tg.sende(chat_id, _TEXT_EIGENE_IDEE)
        biete_schaerfung(conn, tg, chat_id)
        return f"Szene {ziel['nummer']} geschaerft"

    if art == ART_SCHAERFUNG_FIGUR:
        from interview_theater import schaerfung as schaerfung_modul

        modus, _, name = wert.partition(TRENNER)
        figur = repo.hole_figur(conn, chat_id, name or wert)
        if figur is None:
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        anzahl = schaerfung_modul.uebernimm_figur(conn, chat_id, figur)
        if not anzahl:
            tg.sende(chat_id, _TEXT_SCHAERFUNG_NICHTS)
        else:
            tg.sende(chat_id, _TEXT_SCHAERFUNG_UEBERNOMMEN.format(anzahl=anzahl))
        if modus.strip() == "anders":
            tg.sende(chat_id, _TEXT_EIGENE_IDEE)
        biete_schaerfung(conn, tg, chat_id)
        return f"{figur['name']} geschaerft"

    if art == ART_SCHAERFUNG_RUNDE:
        # Eine weitere Runde mit dem inzwischen geschaerften Stand -- der
        # Lauf haengt im Thread, hier wird nur angestossen.
        starte_schaerfung(conn, tg, klm, e, chat_id)
        return "Noch eine Runde"

    if art == ART_SZENENFOLGE_ANZAHL:
        # Nur die Zahlenknoepfe oeffnen -- der Vorschlag entsteht erst beim
        # Druck auf eine Zahl, und der laeuft im Thread.
        leiste = [
            (
                str(zahl),
                _daten(
                    repo.lege_knopf_an(
                        conn, chat_id, ART_SZENENFOLGE_ANZAHL_WERT, str(zahl)
                    )
                ),
            )
            for zahl in szenenfolge.ANZAHL_MOEGLICH
        ]
        _mit_leiste(conn, tg, chat_id, _TEXT_ANZAHL_FRAGE, leiste)
        return "Wie viele?"

    if art == ART_SZENENFOLGE_ANZAHL_WERT:
        # In Phase 5 ist die Anzahl eine Angabe zur GESCHICHTE, nicht zu
        # einer blanken Szenenfolge -- derselbe Knopf, der Weg richtet sich
        # nach der Station.
        if phasen.aktuelle(conn, chat_id) <= PHASE_GESCHICHTE:
            szenenfolge.starte_geschichte(conn, tg, klm, e, chat_id, anzahl=int(wert))
        else:
            szenenfolge.starte(conn, tg, klm, e, chat_id, anzahl=int(wert))
        return f"{wert} Szenen"

    if art == ART_SZENENFOLGE_REIHENFOLGE:
        # Der Bot fragt; die naechste Nachricht wirkt ueber den normalen
        # Gespraechszug, der den Vorschlag neu baut. Kein Modellaufruf hier.
        tg.sende(chat_id, _TEXT_REIHENFOLGE_FRAGE)
        return "Sagt mir die Reihenfolge"

    if art == ART_SZENE_ZEIGEN:
        ziel = _szene_mit_nummer(conn, chat_id, int(wert))
        if ziel is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        biete_szene(conn, tg, chat_id, ziel)
        return f"Szene {wert}"

    if art == ART_SZENE_SCHREIBEN:
        return _schreibe_szene(conn, tg, klm, e, chat_id, int(wert))

    if art == ART_SZENE_PLANEN:
        # Wie "Nochmal anders": ein Satz, kein Modellaufruf. Was die Gruppe
        # danach sagt, laeuft ueber den Erkenner (art szene_planen) oder den
        # Gespraechszug -- beide Wege setzen die Felder und stellen die Szene
        # neu vor.
        tg.sende(chat_id, _TEXT_SZENE_PLANEN_FRAGE)
        return "Was soll anders sein?"

    if art == ART_SZENE_FORM:
        biete_szenenform(conn, tg, chat_id, int(wert))
        return "Welche Form?"

    if art == ART_SZENE_UEBERSPRINGEN:
        nummer = int(wert)
        # Weich (N3): die Szene ist raus, aber nichts ist weg -- eine Gruppe,
        # die es sich anders ueberlegt, hat sie noch.
        entfernt = repo.entferne_szene(conn, chat_id, nummer)
        if entfernt is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        tg.sende(chat_id, _TEXT_SZENE_UEBERSPRUNGEN.format(nummer=nummer))
        naechste = _naechste_offene(conn, chat_id, nummer)
        if naechste is not None:
            biete_szene(conn, tg, chat_id, naechste)
        return f"Szene {nummer} raus"

    if art == ART_SZENENFELDER_SPEICHERN:
        modus, _, rest = wert.partition(TRENNER)
        meldung = _speichere_szenenfelder(conn, tg, chat_id, rest)
        if modus.strip() == "anders":
            tg.sende(chat_id, _TEXT_EIGENE_IDEE)
        return meldung

    if art == ART_SZENE_PASST:
        nummer = int(wert)
        ziel = _szene_mit_nummer(conn, chat_id, nummer)
        if ziel is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        repo.setze_szene_fertig(conn, ziel["id"], True)
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            f"Szene {nummer} abgenommen: {ziel['titel'] or ''}".strip(),
            quelle="knopf",
        )
        tg.sende(chat_id, _TEXT_PASST.format(nummer=nummer))
        _biete_weiter_nach_szene(conn, tg, chat_id, nummer)
        return f"Szene {nummer} steht"

    if art == ART_SZENE_ANDERS:
        # Der Regie-Vermerk kommt als naechste Nachricht; ``ablauf.antworte``
        # greift ihn auf (``szenenfolge.nimm_regienotiz``) und schreibt die
        # Szene damit neu. Kein Modellaufruf hier.
        nummer = int(wert)
        szenenfolge.erwarte_regienotiz(chat_id, nummer)
        tg.sende(chat_id, _TEXT_SZENE_ANDERS_FRAGE)
        _melde_spaetere(conn, tg, chat_id, nummer)
        return "Was soll anders werden?"

    if art == ART_SZENE_NEU:
        nummer = int(wert)
        ziel = _szene_mit_nummer(conn, chat_id, nummer)
        if ziel is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        # Die alte Fassung bleibt in der Datenbank (N3-Haltung: nichts wird
        # weggeworfen), der Fertig-Stempel faellt: ein neuer Text ist wieder
        # ein Entwurf.
        repo.hebe_fassung_auf(conn, ziel["id"])
        repo.setze_szene_fertig(conn, ziel["id"], False)
        # Diese Szene wird gerade neu geschrieben -- ihr eigener Pruef-Vermerk
        # ist damit erledigt, und die spaeteren bekommen einen.
        szenenfolge.nimm_pruefvermerk(conn, chat_id, nummer)
        _melde_spaetere(conn, tg, chat_id, nummer)
        return _schreibe_szene(conn, tg, klm, e, chat_id, nummer)

    if art == ART_SZENE_SO_LASSEN:
        # "So lassen": der Vermerk faellt weg, der Text bleibt. Kein Lauf,
        # kein Modellaufruf -- die Gruppe hat entschieden, dass die Aenderung
        # an der frueheren Szene diese hier nicht beruehrt.
        nummer = int(wert)
        szenenfolge.nimm_pruefvermerk(conn, chat_id, nummer)
        tg.sende(chat_id, _TEXT_SZENE_SO_GELASSEN.format(nummer=nummer))
        _biete_weiter_nach_szene(conn, tg, chat_id, nummer)
        return f"Szene {nummer} bleibt"

    if art == ART_SZENE_NAECHSTE:
        naechste = _naechste_offene(conn, chat_id, int(wert))
        if naechste is None:
            _biete_weiter_nach_szene(conn, tg, chat_id, int(wert))
            return "Das war die letzte"
        biete_szene(conn, tg, chat_id, naechste)
        return f"Szene {naechste['nummer']}"

    if art == ART_DURCHLAUF_SZENE:
        nummer = int(wert)
        ziel = _szene_mit_nummer(conn, chat_id, nummer)
        if ziel is None:
            tg.sende(chat_id, _TEXT_SZENE_UNBEKANNT)
            return _TEXT_SZENE_UNBEKANNT
        volltext = (ziel["volltext"] or "").strip()
        if not volltext:
            tg.sende(chat_id, _TEXT_SZENE_OHNE_TEXT.format(nummer=nummer))
            return _TEXT_SZENE_OHNE_TEXT.format(nummer=nummer)
        # Der Volltext geht ungekuerzt raus -- lange Texte teilt der
        # Telegram-Wrapper selbst (``telegram.teile_text``).
        kopf = f"Szene {nummer}"
        if ziel["titel"]:
            kopf += f": {ziel['titel']}"
        tg.sende(chat_id, f"{kopf}\n\n{volltext}")
        return f"Szene {nummer}"

    if art == ART_TEXTBUCH:
        text = szenenfolge.textbuch(conn, chat_id)
        try:
            tg.sende_datei(
                chat_id, szenenfolge.dateiname(chat_id), text,
                _TEXT_TEXTBUCH_BESCHREIBUNG,
            )
        except Exception:
            # Scheitert sendDocument (alte Telegram-Attrappe, Rechte in der
            # Gruppe), soll die Gruppe nicht ratlos dastehen: eine Zeile, und
            # die Szenen sind ueber "Szene N ansehen" weiter erreichbar.
            log.exception("Textbuch-Datei fehlgeschlagen, chat_id=%s", chat_id)
            tg.sende(chat_id, _TEXT_TEXTBUCH_FEHLER)
            return _TEXT_TEXTBUCH_FEHLER
        return "Textbuch"

    return None


def _melde_spaetere(conn, tg, chat_id: int, nummer: int) -> list[int]:
    """Markiert nach einer Aenderung an Szene ``nummer`` alle spaeteren
    geschriebenen Szenen zur Pruefung und sagt der Gruppe in EINER Zeile,
    welche das sind (``szenenfolge.markiere_spaetere``).

    Kein automatisches Neuschreiben und keine Rueckfrage: die Szenen tragen
    danach ihren Vermerk, und wenn sie das naechste Mal vorgestellt werden,
    stehen "Neu schreiben" und "So lassen" darunter. Ein Fehlschlag beim
    Senden darf den laufenden Knopf nicht mitreissen."""
    from interview_theater import szenenfolge

    betroffen = szenenfolge.markiere_spaetere(conn, chat_id, nummer)
    if not betroffen:
        return []
    namen = ", ".join(f"Szene {n}" for n in betroffen)
    try:
        tg.sende(
            chat_id,
            _TEXT_SPAETERE_GEPRUEFT.format(nummer=nummer, spaetere=namen),
        )
    except Exception:
        log.exception("Hinweis auf spaetere Szenen fehlgeschlagen, chat_id=%s", chat_id)
    return betroffen


def _biete_weiter_nach_szene(conn, tg, chat_id: int, nummer: int) -> None:
    """Nach einer abgenommenen Szene: entweder die naechste offene, oder --
    wenn keine mehr kommt -- "Weiter zu Durchlauf".

    Der Phasenknopf entsteht ueber ``_phasenknopf``, also nur, wenn die
    Materiallage Phase 7 ueberhaupt hergibt (``phasen.voraussetzungen``:
    mindestens eine geschriebene Szene). Er heisst "Weiter zu 7 · Durchlauf"
    wie jeder Phasenknopf -- eine zweite Schreibweise waere eine zweite Sache
    zu lernen."""
    naechste = _naechste_offene(conn, chat_id, nummer)
    if naechste is not None:
        biete_szene(conn, tg, chat_id, naechste)
        return
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        _mit_leiste(conn, tg, chat_id, _TEXT_KEINE_NAECHSTE, [phasenknopf])
    else:
        tg.sende(chat_id, _TEXT_KEINE_NAECHSTE)


# --- Verarbeitung ---------------------------------------------------------


#: Bestaetigung statt Ueberschreiben (06.09.2026, Birk, Testgruppe 21:50):
#: steht das Feld schon und hat niemand um eine Aenderung gebeten, ist
#: "Gefaellt uns, weiter" ein Ja zum Bestehenden, kein neuer Wert.
_TEXT_SCHON_GESETZT = "Steht schon so."


def _ist_bestaetigung(conn, chat_id: int, art: str, wert: str) -> bool:
    """Ist dieser Speicherdruck nur ein Ja zu dem, was schon dasteht?

    Die Bedingung (06.09.2026, Birk): das Feld ist gesetzt, der Druck traegt
    einen ANDEREN Wert, und es ist keine Aenderung offen
    (``arbeitsstand.aenderung_offen``). Dann hat niemand um eine Aenderung
    gebeten -- und ein stilles Ueberschreiben ist genau der Fall vom
    Testabend: "Gefaellt uns, weiter" unter einem Szenenbild-Vorschlag
    ersetzte den Rahmen von 21:37 durch "Leyla checkt ihr Handy auf dem
    Schulhof", ohne dass irgendwo stand, dass etwas verloren geht.

    Ueberschrieben wird weiterhin nach "Passt, aber anders" (setzt
    ``aenderung_offen``) und durch den Erkenner, wenn die Gruppe den neuen
    Wert wirklich sagt -- beides sind ausgesprochene Absichten, kein
    Nebeneffekt eines Knopfdrucks."""
    if art not in _NOTIERT:
        return False
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if stand is None:
        return False
    alt = (stand[art] or "").strip() if art in stand.keys() else ""
    if not alt or alt == wert.strip():
        return False
    return not (stand["aenderung_offen"] or "").strip()


def _speichere(conn, tg, chat_id: int, roh: str, weiterfrage: bool = True,
               nur_bestaetigen: bool = False) -> str:
    """Schreibt den Wert einer Speicher-Leiste in den Arbeitsstand -- ueber
    **dieselben** ``repo``-Funktionen wie ``erkenner.wende_an``.

    Das ist die ganze Uebung: kein zweiter Schreibweg, kein zweites Feld,
    keine zweite Notiert-Zeile. Der Erkenner-Pfad bleibt daneben bestehen;
    schreibt er zuerst, ist das Feld gesetzt und die Leiste erscheint gar
    nicht mehr (``offene_art``).

    ``roh`` ist ``"<art>|<wert>"`` (siehe ``ART_SPEICHERN``). Getrennt wird
    am ERSTEN '|', damit ein Wert mit '|' darin (eine Frageliste zum
    Beispiel) die Art nicht zerlegt."""
    art, _, wert = roh.partition(TRENNER)
    art = art.strip()
    wert = wert.strip()
    if not art or not wert:
        log.error("Speicher-Knopf ohne Wert, chat_id=%s, roh=%r", chat_id, roh)
        return _TEXT_UNBEKANNT

    if art == "figuren":
        return _uebernimm_figurenliste(conn, tg, chat_id, wert)

    if art not in _NOTIERT:
        log.error("Speicher-Knopf mit unbekannter art %r, chat_id=%s", art, chat_id)
        return _TEXT_UNBEKANNT

    if nur_bestaetigen and _ist_bestaetigung(conn, chat_id, art, wert):
        # Das Feld steht, niemand hat um eine Aenderung gebeten: der Druck
        # ist ein Ja zum Bestehenden. Keine Schreiboperation, keine
        # Notiert-Zeile, kein Journal-Eintrag -- und vor allem kein stiller
        # Verlust (06.09.2026, Testgruppe 21:50).
        log.info(
            "Speicher-Knopf bestaetigt nur, art=%s, chat_id=%s", art, chat_id,
        )
        repo.merke_vorfall(
            conn, chat_id, None, "ueberschreiben_verhindert",
            f"'{art}' steht bereits und wurde durch einen Speicher-Knopf nicht ersetzt",
        )
        tg.sende(chat_id, _TEXT_SCHON_GESETZT)
        return _TEXT_SCHON_GESETZT

    repo.setze_arbeitsstand(conn, chat_id, art, wert)
    if weiterfrage:
        # Abgenommen: die offene Aenderungsbitte ist erledigt, die Leiste
        # verschwindet wieder (``offene_art``).
        repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"{_NOTIERT[art]}: {wert}", quelle="knopf",
    )
    tg.sende(
        chat_id,
        f"Notiert:\n{_NOTIERT[art]}: {wert}\nFalls das nicht stimmt, sagt es mir.",
    )
    # Danach die eine Frage, die den Zwischenraum offenhaelt -- und darunter,
    # wenn die Materiallage es hergibt, der Weg weiter
    # (``phasen.voraussetzungen``): der Knopf sagt, was jetzt dran ist,
    # statt dass jemand raten muss.
    if weiterfrage:
        phasenknopf = _phasenknopf(conn, chat_id)
        if phasenknopf is not None:
            tg.sende_mit_knoepfen(chat_id, _TEXT_NACH_SPEICHERN_FRAGE, [phasenknopf])
        else:
            tg.sende(chat_id, _TEXT_NACH_SPEICHERN_FRAGE)
    return f"{_NOTIERT[art]} uebernommen"


def _ersetze_namen(conn, tg, chat_id: int, neuer_name: str) -> str:
    """Ersetzt den Namen EINER Zeile im Figuren-Entwurf und stellt Ebene 1
    neu hin (05.09.2026 abends).

    Welche Zeile gemeint ist, steht im Merkposten
    ``arbeitsstand.figur_aktuell`` (ihr Index) -- der Knopf traegt nur den
    Namen, damit auch ein langer Name die 64 Bytes nie beruehrt."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    roh_index = (stand["figur_aktuell"] if stand else "") or ""
    zeilen = _entwurfszeilen(conn, chat_id)
    if not roh_index.isdigit() or int(roh_index) >= len(zeilen) or not neuer_name:
        log.error("Namensknopf ohne Zeile, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_UNBEKANNT)
        return _TEXT_UNBEKANNT
    index = int(roh_index)
    alt_zeile = zeilen[index]
    # Nur der Namensteil wird getauscht -- Satz und Interview bleiben, sie
    # sind die Arbeit der Gruppe, der Name war nur ihre Beschriftung.
    rest = alt_zeile.split("—", 1)
    if len(rest) == 1:
        rest = alt_zeile.split(" - ", 1)
        zeilen[index] = (
            f"{neuer_name} - {rest[1].lstrip()}" if len(rest) > 1 else neuer_name
        )
    else:
        zeilen[index] = f"{neuer_name} — {rest[1].lstrip()}"
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", None)
    biete_figurenliste(conn, tg, chat_id, "\n".join(zeilen))
    return "Name geaendert"


def _figurenzeile(namen: list[str]) -> str:
    """Dieselbe Zeile, die der Erkenner baut (``erkenner._figuren_zeile``) --
    von dort geholt statt hier zweitgepflegt: die Gruppe soll nicht zwei
    Formulierungen fuer dasselbe Ereignis sehen."""
    from interview_theater import erkenner

    return erkenner._figuren_zeile(namen)


# --- Figuren, Ebene 1: die Liste ------------------------------------------

_TEXT_FIGUREN_ANZAHL_KNOPF = "Anzahl aendern"
_TEXT_FIGUREN_NAMEN_KNOPF = "Namen aendern"
_TEXT_FIGUREN_ANZAHL_FRAGE = "Wie viele Figuren sollen es sein?"
_TEXT_FIGUREN_NAMEN_FRAGE = "Welchen Namen wollt ihr aendern?"
#: Die eigene Frage VOR der Figurenliste (05.09.2026 abends, Birk): wie viele
#: Figuren das Stueck haben soll, entscheidet die Gruppe -- nicht der Prompt.
#: Vorher stand "zwei bis vier" in ``prompts/phasen/4.md`` und die Zahl war
#: eine Nebenwirkung eines Vorschlags.
_TEXT_FIGUREN_ANZAHL_ERSTFRAGE = "Wie viele Figuren soll das Stueck haben?"
#: Wie viele Figuren zur Auswahl stehen. Eins, weil ein Monolog ein Stueck
#: ist; sechs, weil darueber eine Laiengruppe an einem Wochenende die Proben
#: nicht mehr besetzt bekommt. Alles andere geht ueber "Andere Zahl" --
#: begrenzt wird nichts, nur die Knopfleiste.
FIGURENZAHLEN = ("1", "2", "3", "4", "5", "6")
_TEXT_FIGUREN_ANZAHL_FREI_KNOPF = "Andere Zahl"
_TEXT_FIGUREN_ANZAHL_FREI_FRAGE = (
    "Sagt mir die Zahl - ich schlage euch dann genau so viele Figuren vor."
)
#: Die Grenzen der frei gesagten Zahl. Nicht null (ein Stueck ohne Figuren
#: gibt es nicht) und nicht zwoelf plus: darueber ist es keine Besetzung mehr,
#: sondern eine Liste, und der naechste Schritt (Figur fuer Figur) wuerde zum
#: Nachmittag.
FIGURENZAHL_MIN = 1
FIGURENZAHL_MAX = 12
_TEXT_FIGURENZAHL_UNKLAR = (
    "Das habe ich nicht als Zahl gelesen. Sagt mir eine Zahl zwischen "
    f"{FIGURENZAHL_MIN} und {FIGURENZAHL_MAX}."
)

#: Merkposten je Gruppe: die naechste freie Nachricht ist die Figurenanzahl
#: (nach "Andere Zahl"). Wie ``szenenfolge._regienotiz_erwartet`` bewusst im
#: Prozess und nicht in der Datenbank: er gilt fuer genau die naechste
#: Nachricht, ein Neustart dazwischen macht daraus wieder einen normalen
#: Gespraechsbeitrag -- und das ist die richtige Fehlerrichtung.
_anzahl_erwartet: set[int] = set()


def erwarte_figurenanzahl(chat_id: int) -> None:
    """Merkt: die naechste Nachricht dieser Gruppe ist die Figurenanzahl."""
    _anzahl_erwartet.add(chat_id)


def nimm_figurenanzahl_erwartung(chat_id: int) -> bool:
    """Liefert True, wenn eine Zahl erwartet wird -- und vergisst es dabei.

    Einmalig wie ``szenenfolge.nimm_regienotiz``: sonst wuerde jede weitere
    Nachricht der Gruppe als Figurenanzahl gelesen."""
    if chat_id not in _anzahl_erwartet:
        return False
    _anzahl_erwartet.discard(chat_id)
    return True


def _zahl_aus(text: str) -> int | None:
    """Die erste Zahl in einer Nachricht, wenn sie im erlaubten Bereich liegt.

    Toleriert \"wir haetten gern 4\" und \"4 Figuren bitte\" -- die Gruppe
    tippt keine blanken Ziffern. Ausgeschrieben zaehlt auch: \"vier\" ist eine
    Zahl, und wer eine Zahl sagt, meint eine."""
    treffer = re.search(r"\d{1,2}", text or "")
    if treffer is not None:
        zahl = int(treffer.group(0))
    else:
        worte = {
            "eine": 1, "einer": 1, "eins": 1, "zwei": 2, "drei": 3, "vier": 4,
            "fuenf": 5, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8,
            "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12, "zwölf": 12,
        }
        gefunden = [
            wert for wort, wert in worte.items()
            if re.search(rf"\b{wort}\b", (text or "").lower())
        ]
        if not gefunden:
            return None
        zahl = gefunden[0]
    if FIGURENZAHL_MIN <= zahl <= FIGURENZAHL_MAX:
        return zahl
    return None


def biete_figurenanzahl(conn, tg, chat_id: int, text: str | None = None) -> int:
    """Die eigene Frage vor der Figurenliste: 1-6 und \"Andere Zahl\".

    Deterministisch, kein Modellaufruf (Zusage 2). Sie steht bewusst VOR dem
    Listenvorschlag: solange die Zahl aus einem Prompt kam, war sie eine
    Vorgabe des Bots -- jetzt ist sie eine Entscheidung der Gruppe, und der
    Vorschlag richtet sich danach (``ANWEISUNG_FIGURENZAHL``)."""
    for art in (ART_FIGUREN_ANZAHL, ART_FIGUREN_ANZAHL_FREI):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    leiste = [
        (zahl, _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL, zahl)))
        for zahl in FIGURENZAHLEN
    ]
    leiste.append(
        (
            _TEXT_FIGUREN_ANZAHL_FREI_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_FREI, None)),
        )
    )
    message_id = tg.sende_mit_knoepfen(
        chat_id, text or _TEXT_FIGUREN_ANZAHL_ERSTFRAGE, leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return message_id


def uebernimm_figurenanzahl(conn, tg, klm, e, chat_id: int, anzahl: int) -> None:
    """Speichert die Anzahl und laesst im Thread eine Liste mit genau so
    vielen Figuren vorschlagen -- der eine Weg, auf dem eine Zahl wirkt,
    egal ob sie aus einem Knopf oder aus einer Nachricht kam."""
    repo.setze_arbeitsstand(conn, chat_id, "figuren_anzahl", str(anzahl))
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Figurenanzahl: {anzahl}", quelle="knopf",
    )
    _starte_auftrag(
        conn, tg, klm, e, chat_id, ANWEISUNG_FIGURENZAHL.format(anzahl=anzahl),
    )


# --- Die Kette durch Phase 4 ----------------------------------------------
#
# Kernthema (Stufe 2) -> Kernfrage (Stufe 3) -> Filter am Kernthema
# (``kernzitate.py``, still im Thread) -> Figurenanzahl -> Figurenliste.
#
# Der Grund fuer die Kette (Birk, 05.09.2026 abends, nach dem Regie-Test): die
# Gruppe konnte den Weg vom Kernthema zu den Figuren nicht nachvollziehen,
# weil es ihn nicht gab -- die Figuren kamen aus den Interviews. Jetzt fuehrt
# jeder Schritt zum naechsten, ohne dass jemand raten muss, was jetzt dran
# ist. Kein Schritt ruft dabei selbst ein Modell (Zusage 2): was eines
# braucht, geht an einen eigenen Thread.

#: Die Arten, nach deren Speichern der naechste Schritt von selbst kommt.
#: Arten, die den Weg selbst weitertragen (statt der allgemeinen Frage
#: "Wollt ihr noch etwas hinzufuegen?"). Seit dem Umbau vom 05.09.2026
#: nachts ist das der **Rahmen**: steht das Setting, kommt sofort die Frage
#: nach der Figurenanzahl. Kernthema und Kernfrage bleiben rueckwaerts-
#: kompatibel drin -- angeboten werden sie nicht mehr.
_KETTE = ("rahmen", "kernthema", "kernfrage")


def _kette_weiter(conn, tg, klm, e, chat_id: int, art: str) -> None:
    """Was nach dem Speichern einer Kettenart passiert."""
    stand = repo.hole_arbeitsstand(conn, chat_id)
    if art == "rahmen":
        # Das Setting steht -- jetzt die Figuren, und wie viele es sein
        # sollen, sagt die Gruppe (deterministisch, kein Modellaufruf).
        biete_figurenanzahl(conn, tg, chat_id)
        return
    if art == "kernthema":
        _starte_auftrag(
            conn, tg, klm, e, chat_id,
            ANWEISUNG_KERNFRAGE.format(
                kernthema=(stand["kernthema"] if stand else "") or ""
            ),
        )
        return
    # Die Kernfrage steht: jetzt wird am Kernthema gefiltert -- still, im
    # Thread, ohne Liste im Chat. Danach kommt die Frage nach der
    # Figurenanzahl aus der Nachbereitung heraus, damit sie NACH der einen
    # Auswahl-Zeile steht und nicht davor.
    from interview_theater import kernzitate

    def _danach() -> None:
        biete_figurenanzahl(conn, tg, chat_id)

    thread = kernzitate.starte(conn, tg, klm, e, chat_id, nachbereitung=_danach)
    if thread is None:
        # Ohne Sprachmodell (Tests, ein Programmierfehler) bleibt der Weg
        # trotzdem offen: die Frage nach der Anzahl kommt sofort.
        biete_figurenanzahl(conn, tg, chat_id)


def _entwurfszeilen(conn, chat_id: int) -> list[str]:
    """Die Zeilen des aktuellen Figuren-Entwurfs
    (``arbeitsstand.figuren_entwurf``), eine je Figur."""
    from interview_theater import vorschlag

    stand = repo.hole_arbeitsstand(conn, chat_id)
    return vorschlag.zeilen(stand["figuren_entwurf"] if stand else "")


def biete_figurenliste(conn, tg, chat_id: int, wert: str, text: str | None = None) -> int:
    """Ebene 1: die Figurenliste mit "Anzahl aendern" · "Namen aendern" und
    der Grundleiste darunter (05.09.2026 abends, Birk).

    Der Entwurf wird dabei im Arbeitsstand festgehalten
    (``figuren_entwurf``) -- nicht als Figuren: erst "Gefaellt uns, weiter"
    legt sie an. Sonst staenden nach drei Runden Namensaenderung neun Figuren
    in der Datenbank, von denen die Gruppe sechs nie gewollt hat."""
    repo.setze_arbeitsstand(conn, chat_id, "figuren_entwurf", wert)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FIGUREN_ANZAHL_MENU)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_FIGUREN_NAMEN_MENU)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_SPEICHERN)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_ANDERS)
    _nimm_alte_leiste_ab(conn, tg, chat_id, ART_EIGENE)
    leiste = [
        (
            _TEXT_FIGUREN_ANZAHL_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_ANZAHL_MENU, None)),
        ),
        (
            _TEXT_FIGUREN_NAMEN_KNOPF,
            _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUREN_NAMEN_MENU, None)),
        ),
    ] + speicherleiste(conn, chat_id, "figuren", wert)
    message_id = tg.sende_mit_knoepfen(chat_id, text or wert, leiste)
    repo.merke_knopf_nachricht(
        conn, [_id_aus_daten(d) for _, d in leiste], message_id
    )
    return message_id


def _uebernimm_figurenliste(conn, tg, chat_id: int, wert: str) -> str:
    """"Gefaellt uns, weiter" (oder "Passt, aber anders") auf der
    Figurenliste: ALLE Figuren des Entwurfs anlegen und Ebene 2 starten.

    Die Zuordnung Figur -> Interview kommt aus der dritten Spalte der
    Entwurfszeile ("Interview 2"), sofern es dieses Interview gibt --
    dieselbe Nummerierung wie ``kontext.interviewbezeichnung``. Fehlt sie
    oder passt sie auf kein Interview, bleibt die Quelle leer; Ebene 2 fragt
    dann danach ("Anderes Interview")."""
    from interview_theater import vorschlag

    angelegt: list[str] = []
    for zeile in vorschlag.zeilen(wert):
        zerlegt = vorschlag.figuren(zeile)
        if not zerlegt:
            continue
        name, beschreibung = zerlegt[0]
        # Derselbe Schreibweg wie erkenner._wende_figur_an.
        repo.setze_figur(conn, chat_id, name, beschreibung)
        aufnahme_id = _interview_aus_zeile(conn, chat_id, zeile)
        if aufnahme_id is not None:
            figur = repo.hole_figur(conn, chat_id, name)
            if figur is not None and figur["quelle_aufnahme_id"] is None:
                repo.setze_figur_quelle(conn, figur["id"], aufnahme_id)
        angelegt.append(name)
    if not angelegt:
        log.error("Figuren-Knopf ohne verwertbare Zeile, chat_id=%s", chat_id)
        return _TEXT_UNBEKANNT
    repo.setze_arbeitsstand(conn, chat_id, "figuren_entwurf", wert)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", f"Figuren: {', '.join(angelegt)}",
        quelle="knopf",
    )
    tg.sende(chat_id, "Notiert:\n" + _figurenzeile(angelegt)
             + "\nFalls das nicht stimmt, sagt es mir.")
    return "Figuren uebernommen"


#: "Interview 2" am Ende einer Entwurfszeile.
_INTERVIEWNUMMER = re.compile(r"interview\s*(\d{1,3})", re.IGNORECASE)


def _interview_aus_zeile(conn, chat_id: int, zeile: str) -> int | None:
    """Die ``aufnahme_id`` hinter "Interview N" in einer Entwurfszeile, oder
    None. Gezaehlt wird wie in ``kontext.interviewbezeichnung``: die langen
    Aufnahmen in Entstehungsreihenfolge, ab 1."""
    treffer = _INTERVIEWNUMMER.search(zeile or "")
    if treffer is None:
        return None
    from interview_theater import aufnahme as aufnahme_modul

    koepfe = aufnahme_modul.interviews(conn, chat_id)
    nummer = int(treffer.group(1))
    if 1 <= nummer <= len(koepfe):
        return koepfe[nummer - 1]["id"]
    return None



# --- Figuren, Ebene 2: Figur fuer Figur -----------------------------------

_TEXT_FIGUR_PASST_KNOPF = "Passt"
_TEXT_FIGUR_INTERVIEW_KNOPF = "Anderes Interview"
_TEXT_FIGUR_DUKTUS_KNOPF = "Anderer Duktus"
_TEXT_FIGUR_ENTFERNEN_KNOPF = "Entfernen"
_TEXT_FIGUR_INTERVIEW_FRAGE = "Aus welchem Interview spricht {name}?"
#: Ebene 2 ist fertig -- ab hier gibt phasen.voraussetzungen[5] den Schritt
#: nach "Format & Rahmen" her (``figuren_fixiert_am``).
_TEXT_FIGUREN_FIXIERT = "Die Figuren stehen."
_TEXT_FIGUREN_KEINE = (
    "Es sind keine Figuren mehr uebrig. Sagt mir, wen ihr stattdessen wollt."
)
#: Was in der Vorstellung steht, solange noch kein Sprachprofil da ist.
_TEXT_DUKTUS_FEHLT = "Sprachduktus: entsteht gerade."
_TEXT_DUKTUS_OHNE_QUELLE = (
    "Sprachduktus: noch keiner - dafuer fehlt das Interview."
)
#: Die Zeile ueber den Belegzitaten. Die Zitate sind der Beleg fuer den
#: Duktus -- ohne sie ist die Beschreibung eine Behauptung.
_TEXT_ZITATE_VORSPANN = "So spricht sie zum Beispiel:"
#: Was die Gruppe liest, waehrend der Sprachprofil-Lauf im Thread haengt.
#: Ohne diese Zeile stand die Gruppe vor der Vorstellung mit "entsteht
#: gerade." und bekam nie die fertige Fassung (gemessen 05.09.2026).
_TEXT_DUKTUS_LAEUFT = (
    "Ich hoere mir gerade {quelle} an, um {name}s Sprache zu erfassen …"
)


def _figurenvorstellung(conn, chat_id: int, figur, ohne_beleg: bool = False) -> str:
    """Der Text, mit dem eine Figur in Ebene 2 vorgestellt wird: Name, Satz,
    Interview, Sprachduktus und die belegten Zitate.

    Rein aus der Datenbank, kein Modellaufruf (Zusage 2). Die Zitate stehen
    dabei, weil genau sie zeigen, was der Duktus behauptet -- die Gruppe
    nimmt eine Figur an ihrer Sprache ab, nicht an einer Beschreibung."""
    from interview_theater import kontext

    zeilen = [figur["name"]]
    if (figur["beschreibung"] or "").strip():
        zeilen.append(figur["beschreibung"].strip())
    if figur["quelle_aufnahme_id"] is not None:
        zeilen.append(
            kontext.interviewbezeichnung(conn, chat_id, figur["quelle_aufnahme_id"])
        )
        profil = (figur["sprachprofil"] or "").strip()
        if profil:
            zeilen.append(f"Sprachduktus: {profil}")
        elif ohne_beleg:
            from interview_theater import sprachprofil

            zeilen.append(
                sprachprofil._TEXT_KEIN_ZITAT.format(name=figur["name"])
            )
        else:
            zeilen.append(_TEXT_DUKTUS_FEHLT)
        zitate = [
            z.strip()
            for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER)
            if z.strip()
        ]
        if zitate:
            zeilen.append("")
            zeilen.append(_TEXT_ZITATE_VORSPANN)
            zeilen.extend(f"– {z}" for z in zitate)
    else:
        zeilen.append(_TEXT_DUKTUS_OHNE_QUELLE)
    return "\n".join(zeilen)


def naechste_offene_figur(conn, chat_id: int):
    """Die naechste Figur, die in Ebene 2 noch nicht abgenommen wurde -- oder
    None, wenn alle durch sind.

    "Abgenommen" heisst: ``geprueft_am`` ist gesetzt (ein Druck auf "Passt").
    Der Merkposten sitzt an der Figur und nicht in einer Warteschlange:
    entfernt die Gruppe eine Figur oder kommt spaeter eine dazu, stimmt die
    Liste ohne Zutun."""
    return next(
        (f for f in repo.figuren(conn, chat_id) if not f["geprueft_am"]), None
    )


def ebene2_erlaubt(conn, chat_id: int) -> bool:
    """Darf die Figurenarbeit Figur fuer Figur laufen (Interview-Zuordnung,
    Sprachduktus)?

    Erst ab der Schaerfung (Phase 6). In Phase 4 wird **erfunden**: die
    Figuren entstehen aus Begriffen, Fragen und Setting, und die Frage
    \"aus welchem Interview spricht sie?\" waere dort genau die Ruecklenkung
    aufs Material, die der Umbau vom 05.09.2026 nachts vermeidet. Die Liste
    ist damit nach Ebene 1 fixiert; das Interview kommt in Phase 6 aus der
    Zuordnung (``schaerfung.uebernimm_figur``)."""
    return phasen.aktuelle(conn, chat_id) >= PHASE_SCHAERFUNG


def stelle_figur_vor(conn, tg, klm, e, chat_id: int, figur=None) -> bool:
    """Stellt die naechste offene Figur mit ihren vier Knoepfen vor -- oder
    schliesst Ebene 2 ab, wenn keine mehr offen ist. Liefert True, solange
    noch eine Figur vorgestellt wurde.

    Fehlt das Sprachprofil, wird es **im Thread** erzeugt
    (``sprachprofil.starte``) -- ein Knopf-Handler ruft kein Modell
    (Zusage 2). Die Vorstellung geht dann NICHT sofort raus, sondern erst
    nach dem Lauf, aus dessen Nachbereitung heraus: vorher fehlen genau die
    Belegzitate, an denen die Gruppe die Figur abnimmt. Bis dahin liest sie
    eine Zeile, die sagt, was gerade passiert (gemessen 05.09.2026: die
    sofort gesendete Fassung mit "Sprachduktus: entsteht gerade." blieb fuer
    immer stehen)."""
    if not ebene2_erlaubt(conn, chat_id):
        # Phase 4: die Liste ist mit Ebene 1 fertig -- kein Durchgang Figur
        # fuer Figur, keine Interview-Frage, kein Sprachprofil-Lauf.
        return _schliesse_figuren_ab(conn, tg, chat_id)
    figur = figur if figur is not None else naechste_offene_figur(conn, chat_id)
    if figur is None:
        return _schliesse_figuren_ab(conn, tg, chat_id)

    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", figur["name"])
    if (klm is not None and figur["quelle_aufnahme_id"] is not None
            and not (figur["sprachprofil"] or "").strip()):
        from interview_theater import kontext, sprachprofil

        figur_id = figur["id"]

        def _nachher() -> None:
            """Laeuft im Sprachprofil-Thread, nachdem das Profil steht (oder
            endgueltig gescheitert ist). Die Figur wird frisch geladen --
            das Profil ist gerade erst geschrieben worden."""
            frisch = repo.hole_figur_nach_id(conn, figur_id)
            if frisch is not None:
                _sende_figurenvorstellung(
                    conn, tg, chat_id, frisch, ohne_beleg=True,
                )

        try:
            thread = sprachprofil.starte(
                conn, tg, klm, e, chat_id, [figur_id], nachbereitung=_nachher,
            )
        except Exception:
            log.exception("Sprachprofil-Start fehlgeschlagen, figur_id=%s", figur_id)
            thread = None
        if thread is not None:
            quelle = kontext.interviewbezeichnung(
                conn, chat_id, figur["quelle_aufnahme_id"]
            ) or "das Interview"
            tg.sende(
                chat_id,
                _TEXT_DUKTUS_LAEUFT.format(quelle=quelle, name=figur["name"]),
            )
            return True

    _sende_figurenvorstellung(conn, tg, chat_id, figur)
    return True


def _sende_figurenvorstellung(conn, tg, chat_id: int, figur,
                              ohne_beleg: bool = False) -> None:
    """Vorstellungstext plus die fuenf Knoepfe. Eigene Funktion, weil sie
    aus zwei Richtungen kommt: direkt (Profil steht schon) und aus der
    Nachbereitung des Sprachprofil-Threads. ``ohne_beleg`` heisst: der Lauf
    ist durch und hat trotzdem kein Profil geliefert -- dann steht statt
    "entsteht gerade" der Hinweis aus ``sprachprofil._TEXT_KEIN_ZITAT``,
    denn die Gruppe kann das beheben (ein anderes Interview nennen)."""
    name = figur["name"]
    for art in (ART_FIGUR_PASST, ART_FIGUR_INTERVIEW_MENU,
                ART_FIGUR_DUKTUS_MENU, ART_FIGUR_ENTFERNEN):
        _nimm_alte_leiste_ab(conn, tg, chat_id, art)
    leiste = [
        (_TEXT_FIGUR_PASST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_PASST, name))),
        (_TEXT_FIGUR_INTERVIEW_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_INTERVIEW_MENU, name))),
        (_TEXT_FIGUR_DUKTUS_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_DUKTUS_MENU, name))),
        (_TEXT_FIGUR_ENTFERNEN_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_FIGUR_ENTFERNEN, name))),
        (_TEXT_EIGENE_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_EIGENE, "figur"))),
    ]
    message_id = tg.sende_mit_knoepfen(
        chat_id, _figurenvorstellung(conn, chat_id, figur, ohne_beleg), leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)


def _schliesse_figuren_ab(conn, tg, chat_id: int) -> bool:
    """Ebene 2 ist durch: Merkposten setzen, bestaetigen, den Weg nach
    Phase 5 anbieten. Liefert immer False (es wurde keine Figur mehr
    vorgestellt)."""
    if not repo.figuren(conn, chat_id):
        tg.sende(chat_id, _TEXT_FIGUREN_KEINE)
        return False
    repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", repo._jetzt())
    repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", None)
    repo.schreibe_journal(
        conn, chat_id, "entschieden", "Figurenliste steht", quelle="knopf",
    )
    phasenknopf = _phasenknopf(conn, chat_id)
    if phasenknopf is not None:
        tg.sende_mit_knoepfen(chat_id, _TEXT_FIGUREN_FIXIERT, [phasenknopf])
    else:
        tg.sende(chat_id, _TEXT_FIGUREN_FIXIERT)
    return False


def _biete_interviews(conn, tg, chat_id: int, name: str) -> str:
    """Ein Knopf je vorhandenem Interview -- die Auswahl fuer "Anderes
    Interview". Ohne Interviews gibt es nichts zu waehlen."""
    from interview_theater import aufnahme as aufnahme_modul
    from interview_theater import kontext

    koepfe = aufnahme_modul.interviews(conn, chat_id)
    if not koepfe:
        tg.sende(chat_id, _TEXT_KEIN_INTERVIEW)
        return _TEXT_KEIN_INTERVIEW
    leiste = [
        (
            kontext.interviewbezeichnung(conn, chat_id, kopf["id"]),
            _daten(repo.lege_knopf_an(
                conn, chat_id, ART_FIGUR_INTERVIEW, f"{name}{TRENNER}{kopf['id']}"
            )),
        )
        for kopf in koepfe
    ]
    message_id = tg.sende_mit_knoepfen(
        chat_id, _TEXT_FIGUR_INTERVIEW_FRAGE.format(name=name), leiste
    )
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)
    return "Interview waehlen"


_TEXT_KEIN_INTERVIEW = "Es gibt noch kein Interview, aus dem sie sprechen koennte."


# --- Proaktive Frage beim Eintritt in eine Phase --------------------------

_TEXT_PROAKTIV = "Bevor ich vorschlage: habt ihr selbst schon Ideen?"
_TEXT_WIR_ZUERST_KNOPF = "Ja, wir zuerst"
_TEXT_SCHLAG_VOR_KNOPF = "Schlag du vor"
_TEXT_WIR_ZUERST = "Gut - ich hoere zu."


def biete_proaktiv(conn, tg, chat_id: int, phase: int) -> None:
    """Die Frage beim Eintritt in eine Phase (05.09.2026 abends, Birk):
    "Bevor ich vorschlage: habt ihr selbst schon Ideen?" mit zwei Knoepfen.

    Deterministischer Systemtext, kein Modellaufruf. Der Grund ist einer aus
    dem Raum: ein Bot, der beim Phasenwechsel sofort drei Vorschlaege
    hinlegt, nimmt der Gruppe den Moment, in dem sie selbst etwas hat -- und
    genau der ist die Arbeit. "Schlag du vor" holt den Vorschlag dann in
    einem eigenen Thread (``ablauf.starte_auftrag``)."""
    leiste = [
        (_TEXT_WIR_ZUERST_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_WIR_ZUERST, str(phase)))),
        (_TEXT_SCHLAG_VOR_KNOPF,
         _daten(repo.lege_knopf_an(conn, chat_id, ART_SCHLAG_VOR, str(phase)))),
    ]
    message_id = tg.sende_mit_knoepfen(chat_id, _TEXT_PROAKTIV, leiste)
    repo.merke_knopf_nachricht(conn, [_id_aus_daten(d) for _, d in leiste], message_id)


#: Was "Schlag du vor" je Phase vom Modell verlangt -- die Anweisung, die
#: ``ablauf.starte_auftrag`` an den Koerper haengt. Je Phase eine, weil in
#: jeder etwas anderes vorzuschlagen ist; fehlt eine, gibt es einen
#: allgemeinen Auftrag.
ANWEISUNGEN = {
    1: "Schlag der Gruppe eine Begriffsliste vor und haeng sie als Block "
       "'VORSCHLAG BEGRIFFE:' an.",
    2: "Schlag der Gruppe Interviewfragen vor und haeng sie als Block "
       "'VORSCHLAG FRAGEN:' an, eine Frage je Zeile.",
    # Phase 4: das SETTING zuerst -- und ausschliesslich aus den Begriffen
    # und Fragen der Gruppe. Kein Material: die Interviews stehen in diesem
    # Prompt gar nicht (``kontext.material_erlaubt``), und der Auftrag sagt
    # es noch einmal, damit das Modell nicht danach fragt.
    4: "Schlag drei Settings vor - Ort, Zeit, Anlass in je einer Zeile, frei "
       "erfunden aus den Begriffen und Fragen der Gruppe, NICHT aus "
       "Interviews. Haeng sie als Block 'VORSCHLAG RAHMEN:' an, einen "
       "Vorschlag je Zeile.",
    5: "Schlag die Geschichte im Groben vor: was passiert, wie es endet, "
       "welche Szenen. Frei erfunden aus Begriffen, Fragen, Setting und "
       "Figuren - NICHT aus Interviews. Haeng sie als Block "
       "'VORSCHLAG GESCHICHTE:' an: Zeile 1 der Bogen, Zeile 2 'Ende: ...', "
       "danach je Szene 'Titel — ein Satz — Figuren — Form'.",
}
_ANWEISUNG_ALLGEMEIN = (
    "Schlag der Gruppe den naechsten Schritt dieser Phase vor - konkret, "
    "aus dem Material, und schliess mit einer offenen Frage."
)

#: Die Anweisungen der Knopfwege, die einen Gespraechszug ausloesen.
ANWEISUNG_KERNTHEMA = (
    "Die Gruppe hat die Richtung '{richtung}' gewaehlt. Schlag dazu drei bis "
    "vier konkrete Kernthema-Formulierungen vor, jede mit Bezug aufs "
    "Material. Haeng sie als Block 'VORSCHLAG KERNTHEMA:' an, eine "
    "Formulierung je Zeile."
)
#: Stufe 3 (05.09.2026 abends): das gewaehlte Kernthema wird zur dramatischen
#: Frage geschaerft. Genau drei Zeilen, feste Beschriftungen -- daraus wird
#: ein Text im Arbeitsstand (``kernfrage``) und der Filter, an dem gleich
#: danach Zitate und Verdichtungen ausgewaehlt werden.
ANWEISUNG_KERNFRAGE = (
    "Das Kernthema der Gruppe ist '{kernthema}'. Schaerfe es zu EINER "
    "dramatischen Frage. Haeng sie als Block 'VORSCHLAG KERNFRAGE:' an, mit "
    "genau diesen drei Zeilen: 'Frage: Was passiert, wenn ...', 'Gegensatz: "
    "<zwei Wollen, die aufeinandertreffen>', 'Einsatz: <was auf dem Spiel "
    "steht>'. Keine Auswahl, kein zweiter Vorschlag - eine Frage."
)
ANWEISUNG_FIGURENZAHL = (
    "Schlag eine Figurenliste mit genau {anzahl} Figuren vor - **frei "
    "erfunden**, aus den Begriffen und Fragen der Gruppe und dem Setting. "
    "NICHT aus den Interviews: die kommen erst spaeter dazu und schaerfen, "
    "was ihr jetzt erfindet. Welche {anzahl} Figuren braucht dieses Setting? "
    "Jede will etwas. Haeng die Liste als Block 'VORSCHLAG FIGUREN:' an, "
    "eine Figur je Zeile in der Form 'Name - ein Satz'."
)
ANWEISUNG_NAMEN = (
    "Schlag drei Namen fuer diese Figur vor: {zeile}. Haeng sie als Block "
    "'VORSCHLAG NAMEN:' an, einen Namen je Zeile, sonst nichts."
)
ANWEISUNG_DUKTUS = (
    "Schlag zwei bis drei alternative Beschreibungen des Sprachduktus von "
    "{name} vor - je eine Zeile, konkret (Satzlaenge, Fuellwoerter, Tempo). "
    "Haeng sie als Block 'VORSCHLAG DUKTUS:' an, eine Beschreibung je Zeile."
)


def _starte_auftrag(conn, tg, klm, e, chat_id: int, anweisung: str) -> bool:
    """Gibt einen Gespraechszug mit Anweisung an einen eigenen Thread ab --
    der Weg, auf dem ein Knopf zu einem Modellaufruf kommt, ohne selbst
    einen zu machen (Zusage 2)."""
    from interview_theater import ablauf

    return ablauf.starte_auftrag(conn, tg, klm, e, chat_id, anweisung) is not None


def _werte_alle_aus(conn, tg, klm, e, chat_id: int) -> str:
    """Wertet ALLE beendeten, noch nicht verdichteten Interviews aus --
    nacheinander, in einem eigenen Thread (Zusage 2: kein Modellaufruf im
    Handler selbst).

    Nacheinander und nicht parallel: Infomaniak drosselt Parallelitaet mit
    429/5xx statt mit einer Warteschlange (AGENTS.md, Falle 8). Jede fertige
    Verdichtung geht von ``aufnahme._interview_abschliessen`` aus in den
    Chat, die Gruppe sieht also den Fortschritt."""
    import threading

    from interview_theater import aufnahme

    offen = aufnahme.unausgewertete_interviews(conn, chat_id)
    if not offen:
        tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_NICHTS)
        return _TEXT_AUSWERTEN_ALLE_NICHTS
    if klm is None:
        log.error("Auswerten-alle ohne Sprachmodell, chat_id=%s", chat_id)
        tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
        return _TEXT_AUSWERTEN_UNMOEGLICH

    ids = [kopf["id"] for kopf in offen]
    tg.sende(chat_id, _TEXT_AUSWERTEN_ALLE_LAEUFT)

    def _lauf() -> None:
        for kopf_id in ids:
            try:
                aufnahme._auswerten(conn, tg, klm, e, kopf_id)
            except Exception:
                log.exception("Auswertung fehlgeschlagen, aufnahme_id=%s", kopf_id)

    threading.Thread(target=_lauf, daemon=True).start()
    return _TEXT_AUSWERTEN_ALLE_LAEUFT


def _wirke(conn, tg, klm, e, knopf, chat_id: int) -> str:
    """Fuehrt die Wirkung eines beanspruchten Knopfes aus und liefert den
    kurzen Text fuer answerCallbackQuery.

    Wird NUR aufgerufen, wenn ``repo.beanspruche_knopf`` True geliefert hat --
    die Idempotenz haengt an dieser einen Bedingung und nicht daran, dass
    jede Wirkung fuer sich wiederholbar waere."""
    art = knopf["art"]
    meldung = _wirke_phase6(conn, tg, klm, e, knopf, chat_id)
    if meldung is not None:
        return meldung
    if art == ART_SPEICHERN:
        roh = str(knopf["wert"] or "")
        gespeicherte_art = roh.partition(TRENNER)[0].strip()
        if gespeicherte_art in _KETTE:
            # Kernthema und Kernfrage tragen den Weg selbst weiter (Stufe 2 ->
            # Stufe 3 -> Filter -> Figurenanzahl). Die allgemeine Weiterfrage
            # ("Wollt ihr noch etwas hinzufuegen?") wuerde sich dazwischen
            # stellen, deshalb ``weiterfrage=False``.
            meldung = _speichere(
                conn, tg, chat_id, roh, weiterfrage=False, nur_bestaetigen=True,
            )
            if meldung not in (_TEXT_UNBEKANNT, _TEXT_SCHON_GESETZT):
                repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", None)
                _kette_weiter(conn, tg, klm, e, chat_id, gespeicherte_art)
            return meldung
        # "Gefaellt uns, weiter" ueberschreibt nie still, was schon steht
        # (06.09.2026): ist das Feld gesetzt und keine Aenderung offen, ist
        # der Druck eine Bestaetigung (``_ist_bestaetigung``).
        meldung = _speichere(conn, tg, chat_id, roh, nur_bestaetigen=True)
        if gespeicherte_art == "figuren" and meldung not in (
            _TEXT_UNBEKANNT, _TEXT_SCHON_GESETZT,
        ):
            # Ebene 1 ist abgenommen -- ab hier geht es Figur fuer Figur
            # weiter (Ebene 2), ohne dass jemand etwas antippen muss.
            stelle_figur_vor(conn, tg, klm, e, chat_id)
        return meldung
    if art == ART_ANDERS:
        # "Passt, aber anders" SPEICHERT ebenfalls (05.09.2026 abends, Birk):
        # damit ueberhaupt etwas in der Datenbank steht, auch wenn die Gruppe
        # danach abbricht. Erst danach die gezielte Frage -- deterministisch,
        # kein Modellaufruf (Zusage 2). Die naechste Bot-Antwort traegt die
        # Leiste wieder, und ein "Gefaellt uns, weiter" darauf ueberschreibt
        # den Wert (Journal: eine zweite Zeile, nichts wird geaendert).
        roh = str(knopf["wert"] or "")
        gespeicherte_art = roh.partition(TRENNER)[0].strip()
        if gespeicherte_art in _NOTIERT or gespeicherte_art == "figuren":
            _speichere(conn, tg, chat_id, roh, weiterfrage=False)
            repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", gespeicherte_art)
        tg.sende(chat_id, _TEXT_ANDERS)
        return "Gespeichert, was soll anders sein?"
    if art == ART_EIGENE:
        # Speichert NICHT. Der naechste Gruppenbeitrag ist der Vorschlag, und
        # die Antwort darauf traegt die Leiste erneut.
        repo.setze_arbeitsstand(conn, chat_id, "aenderung_offen", str(knopf["wert"] or ""))
        tg.sende(chat_id, _TEXT_EIGENE)
        return "Erzaehlt"
    if art == ART_RICHTUNG:
        # Stufe 1 der zweistufigen Kernthema-Wahl: die Richtung wird
        # festgehalten, ``kernthema`` bleibt LEER -- eine Richtung ist kein
        # Kernthema, und ein halb gefuelltes Feld waere schlimmer als ein
        # leeres. Der zweite Schritt ist ein Gespraechszug im Thread.
        richtung = str(knopf["wert"] or "").strip()
        repo.setze_arbeitsstand(conn, chat_id, "kernthema_richtung", richtung)
        repo.schreibe_journal(
            conn, chat_id, "vorgeschlagen", f"Richtung: {richtung}", quelle="knopf",
        )
        _starte_auftrag(
            conn, tg, klm, e, chat_id,
            ANWEISUNG_KERNTHEMA.format(richtung=richtung),
        )
        return "Richtung uebernommen"
    if art == ART_FIGUREN_ANZAHL_MENU:
        # "Anzahl aendern" im Listen-Menue und die Erstfrage sind derselbe
        # Weg und schreiben dasselbe Feld -- nur der Fragetext ist ein
        # anderer, weil hier schon eine Liste dasteht.
        biete_figurenanzahl(conn, tg, chat_id, _TEXT_FIGUREN_ANZAHL_FRAGE)
        return "Wie viele?"
    if art == ART_FIGUREN_ANZAHL:
        roh_anzahl = str(knopf["wert"] or "").strip()
        anzahl = _zahl_aus(roh_anzahl)
        if anzahl is None:
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        uebernimm_figurenanzahl(conn, tg, klm, e, chat_id, anzahl)
        return f"{knopf['wert']} Figuren"
    if art == ART_FIGUREN_ANZAHL_FREI:
        # Kein Modellaufruf, kein Wert: nur der Merkposten, dass die naechste
        # Nachricht der Gruppe die Zahl ist (``ablauf.antworte`` liest ihn).
        erwarte_figurenanzahl(chat_id)
        tg.sende(chat_id, _TEXT_FIGUREN_ANZAHL_FREI_FRAGE)
        return "Sagt mir die Zahl"
    if art == ART_FIGUREN_NAMEN_MENU:
        zeilen = _entwurfszeilen(conn, chat_id)
        if not zeilen:
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        leiste = []
        for nr, zeile in enumerate(zeilen, start=1):
            name = zeile.split("—")[0].split(" - ")[0].strip()
            leiste.append(
                (
                    f"Figur {nr}: {name}",
                    _daten(repo.lege_knopf_an(
                        conn, chat_id, ART_FIGUR_NAME_MENU, str(nr - 1)
                    )),
                )
            )
        message_id = tg.sende_mit_knoepfen(chat_id, _TEXT_FIGUREN_NAMEN_FRAGE, leiste)
        repo.merke_knopf_nachricht(
            conn, [_id_aus_daten(d) for _, d in leiste], message_id
        )
        return "Welchen Namen?"
    if art == ART_FIGUR_NAME_MENU:
        zeilen = _entwurfszeilen(conn, chat_id)
        index = int(knopf["wert"])
        if index >= len(zeilen):
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        # Der Index wandert in den Merkposten, damit der Namensdruck weiss,
        # WELCHE Zeile er ersetzt -- der Knopf traegt nur den Namen.
        repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", str(index))
        _starte_auftrag(
            conn, tg, klm, e, chat_id,
            ANWEISUNG_NAMEN.format(zeile=zeilen[index]),
        )
        return "Namen vorschlagen"
    if art == ART_FIGUR_NAME:
        return _ersetze_namen(conn, tg, chat_id, str(knopf["wert"] or "").strip())
    if art == ART_FIGUR_PASST:
        figur = repo.hole_figur(conn, chat_id, str(knopf["wert"] or ""))
        if figur is not None:
            repo.setze_figur_geprueft(conn, figur["id"], repo._jetzt())
        stelle_figur_vor(conn, tg, klm, e, chat_id)
        return "Passt"
    if art == ART_FIGUR_INTERVIEW_MENU:
        return _biete_interviews(conn, tg, chat_id, str(knopf["wert"] or ""))
    if art == ART_FIGUR_INTERVIEW:
        name, _, roh_id = str(knopf["wert"] or "").partition(TRENNER)
        figur = repo.hole_figur(conn, chat_id, name)
        if figur is None or not roh_id.isdigit():
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        repo.setze_figur_quelle(conn, figur["id"], int(roh_id))
        # Das alte Sprachprofil gehoert zum alten Interview -- es wird neu
        # erzeugt (im Thread), und die Figur ist wieder offen.
        repo.setze_sprachprofil(conn, figur["id"], "", [])
        repo.setze_figur_geprueft(conn, figur["id"], None)
        stelle_figur_vor(
            conn, tg, klm, e, chat_id, repo.hole_figur(conn, chat_id, name)
        )
        return "Interview gewechselt"
    if art == ART_FIGUR_DUKTUS_MENU:
        name = str(knopf["wert"] or "")
        repo.setze_arbeitsstand(conn, chat_id, "figur_aktuell", name)
        _starte_auftrag(
            conn, tg, klm, e, chat_id, ANWEISUNG_DUKTUS.format(name=name)
        )
        return "Duktus-Vorschlaege"
    if art == ART_FIGUR_DUKTUS:
        stand = repo.hole_arbeitsstand(conn, chat_id)
        name = (stand["figur_aktuell"] if stand else "") or ""
        figur = repo.hole_figur(conn, chat_id, name)
        if figur is None:
            tg.sende(chat_id, _TEXT_UNBEKANNT)
            return _TEXT_UNBEKANNT
        # Die Zitate bleiben stehen: sie sind belegt (``zitat.pruefe``) und
        # haengen am Interview, nicht an der Beschreibung.
        zitate = [z for z in (figur["zitate"] or "").split(repo.ZITAT_TRENNER) if z]
        repo.setze_sprachprofil(
            conn, figur["id"], str(knopf["wert"] or "").strip(), zitate
        )
        repo.setze_figur_geprueft(conn, figur["id"], None)
        stelle_figur_vor(
            conn, tg, klm, e, chat_id, repo.hole_figur(conn, chat_id, name)
        )
        return "Duktus uebernommen"
    if art == ART_FIGUR_ENTFERNEN:
        name = repo.entferne_figur(conn, chat_id, str(knopf["wert"] or ""))
        if name:
            repo.schreibe_journal(
                conn, chat_id, "entschieden", f"Figur entfernt: {name}",
                quelle="knopf",
            )
            tg.sende(chat_id, f"{name} ist raus.")
        stelle_figur_vor(conn, tg, klm, e, chat_id)
        return "Entfernt"
    if art == ART_RAHMEN:
        return _speichere(
            conn, tg, chat_id, f"rahmen{TRENNER}{knopf['wert']}"
        )
    if art == ART_WIR_ZUERST:
        tg.sende(chat_id, _TEXT_WIR_ZUERST)
        return "Wir hoeren zu"
    if art == ART_SCHLAG_VOR:
        phase = int(knopf["wert"] or 0)
        if phase == PHASE_GESCHICHTE:
            # Phase 5 hat einen eigenen Weg (``szenenfolge.starte_geschichte``):
            # der Vorschlag ist Bogen + Ende + Szenenfolge mit fester
            # Zeilenform, und er entsteht OHNE Material. Eigener Thread.
            from interview_theater import szenenfolge

            szenenfolge.starte_geschichte(conn, tg, klm, e, chat_id)
            return "Ich schlage vor"
        if phase == PHASE_SZENEN:
            # Phase 6 hat einen eigenen Weg (``szenenfolge.starte``): der
            # Vorschlag ist eine Szenenfolge mit fester Zeilenform, kein
            # freier Gespraechszug -- und er traegt danach seine eigenen
            # Knoepfe ("Anzahl aendern", "Reihenfolge aendern"). Auch er
            # laeuft in einem eigenen Thread, kein Modellaufruf hier.
            from interview_theater import szenenfolge

            szenenfolge.starte(conn, tg, klm, e, chat_id)
            return "Ich schlage vor"
        _starte_auftrag(
            conn, tg, klm, e, chat_id,
            ANWEISUNGEN.get(phase, _ANWEISUNG_ALLGEMEIN),
        )
        return "Ich schlage vor"
    if art == ART_AUSWERTEN_ALLE:
        return _werte_alle_aus(conn, tg, klm, e, chat_id)
    if art == ART_TEIL_WEITER:
        # Kein Modellaufruf (Zusage 2), keine Schreibwirkung: die Aufnahme
        # laeuft ohnehin weiter. Der Knopf ist die Antwort auf eine Frage,
        # die sonst offen im Chat stuende -- und die Tastatur ist danach weg
        # (``behandle`` nimmt sie ab), was fuer sich schon die Rueckmeldung
        # ist.
        tg.sende(chat_id, _TEXT_TEIL_WEITER)
        return "Ich hoere weiter zu"
    if art == ART_TEIL_FERTIG:
        # Wortgleich dasselbe wie "Interview beenden": derselbe Umschalter,
        # dieselbe Verdichtung, dieselbe Nach-Interview-Leiste. Kein zweiter
        # Weg fuer dieselbe Sache -- deshalb der Umweg ueber /aufnahme statt
        # einer eigenen Abfolge hier.
        from interview_theater import befehle

        if not repo.ist_interviewmodus_an(conn, chat_id):
            tg.sende(chat_id, _TEXT_TEIL_SCHON_AUS)
            return _TEXT_TEIL_SCHON_AUS
        befehle._befehl_aufnahme(conn, tg, klm, e, chat_id)
        return "Interview beendet"
    if art == ART_KERNTHEMA:
        # Der eigentliche Punkt der Uebung: deterministisch schreiben, was
        # der Erkenner live nicht zuverlaessig traf.
        repo.setze_arbeitsstand(conn, chat_id, "kernthema", knopf["wert"])
        repo.schreibe_journal(
            conn, chat_id, "entschieden", f"Kernthema: {knopf['wert']}", quelle="knopf",
        )
        tg.sende(chat_id, f"Kernthema notiert: {knopf['wert']}")
        return "Kernthema uebernommen"
    if art == ART_AUFNAHME:
        # Wortgleich dasselbe wie /aufnahme -- inklusive der Verdichtung im
        # eigenen Thread. Kein zweiter Weg fuer dieselbe Sache.
        #
        # Import erst hier: ``befehle`` bietet Knoepfe an (biete_kernthema)
        # und ``knoepfe`` ruft einen Befehl auf -- ein Modulimport oben
        # waere ein Zyklus. Der Aufruf ist selten (ein Knopfdruck), der
        # Import danach im sys.modules-Cache.
        from interview_theater import befehle

        befehle._befehl_aufnahme(conn, tg, klm, e, chat_id)
        return "Aufnahme umgeschaltet"
    if art == ART_PHASE:
        nummer = int(knopf["wert"])
        if phasen.setze(conn, chat_id, nummer, "knopf"):
            tg.sende(chat_id, phasen.meldung(nummer))
        if nummer == PHASE_DURCHLAUF:
            # Der Durchlauf fragt nicht nach Ideen, er zeigt, was dasteht:
            # die Szenenfolge mit Status, ein Knopf je Szene und das
            # Textbuch (05.09.2026). Alles aus der Datenbank -- kein
            # Modellaufruf in diesem Handler (Zusage 2).
            biete_durchlauf(conn, tg, chat_id)
        elif nummer == PHASE_SCHAERFUNG:
            # Die Schaerfung fragt nicht nach Ideen: sie legt die Geschichte
            # neben die Interviews. Das Mapping laeuft automatisch beim
            # Eintritt, im Thread (Zusage 2).
            starte_schaerfung(conn, tg, klm, e, chat_id)
        else:
            # Beim Eintritt in eine Phase fragt der Bot zuerst die Gruppe,
            # statt sofort vorzuschlagen (Zusage: proaktiv, aber nicht
            # vorlaut).
            biete_proaktiv(conn, tg, chat_id, nummer)
        return f"Phase {nummer}"
    if art == ART_AUSWERTEN:
        # Zwei Faelle, beide deterministisch und ohne Modellaufruf in DIESEM
        # Handler (Zusage 2 im Moduldocstring):
        #
        # 1. Es gibt schon eine Verdichtung (der Normalfall seit 05.09.2026:
        #    verdichtet wird sofort, ausgespielt erst auf Wunsch) -- dann
        #    wird sie hier direkt aus der Datenbank in den Chat gestellt.
        #    Genau das hat im Live-Lauf gefehlt: die Gruppe fragte zweimal
        #    nach der Auswertung und bekam Text statt Inhalt.
        # 2. Es gibt keine (Interview unter ``aufnahme.MINDEST_WOERTER``) --
        #    dann laeuft wortgleich das, was ``/auswerten`` tut:
        #    ``aufnahme.starte_auswertung`` in einem eigenen Thread, und die
        #    fertige Verdichtung geht von dort in den Chat
        #    (``_interview_abschliessen`` mit ``erzwungen=True``).
        from interview_theater import aufnahme

        kopf_id = int(knopf["wert"])
        kopf = repo.hole_aufnahme(conn, kopf_id)
        if kopf is None:
            tg.sende(chat_id, _TEXT_AUSWERTEN_UNBEKANNT)
            return _TEXT_AUSWERTEN_UNBEKANNT
        name = kopf["name"] or "Das Interview"
        if aufnahme.zeige_verdichtung(conn, tg, e, kopf_id):
            return "Auswertung"
        if klm is None:
            log.error("Auswerten-Knopf ohne Sprachmodell, chat_id=%s", chat_id)
            tg.sende(chat_id, _TEXT_AUSWERTEN_UNMOEGLICH)
            return _TEXT_AUSWERTEN_UNMOEGLICH
        tg.sende(chat_id, f"Ich werte {name} aus.")
        aufnahme.starte_auswertung(conn, tg, klm, e, kopf_id)
        return "Auswertung laeuft"
    if art == ART_STAND:
        from interview_theater import befehle

        befehle._befehl_stand(conn, tg, chat_id, e)
        return "Stand"
    if art == ART_HILFE:
        from interview_theater import befehle

        befehle._befehl_hilfe(tg, e, chat_id)
        return "Hilfe"
    if art == ART_SZENENFORM:
        # Der wert traegt Nummer UND Form ("3:dialog") -- siehe
        # biete_szenenform. Getrennt wird am ERSTEN ':', damit ein spaeter
        # erweiterter Formname mit ':' nicht die Nummer zerlegt.
        roh_nummer, _, form = str(knopf["wert"]).partition(":")
        nummer = int(roh_nummer)
        szene_id = repo.stelle_szene_sicher(conn, chat_id, nummer)
        repo.setze_szenenfeld(conn, szene_id, "form", form)
        from interview_theater import szene as szene_modul

        tg.sende(
            chat_id,
            szene_modul.planungszeile(conn, repo.hole_szene(conn, szene_id)),
        )
        return f"Szene {nummer}: {form}"
    if art == ART_SZENE_USA:
        # ACHTUNG, hier ist am 05.09.2026 schon ein Fehler passiert:
        # repo.setze_szene_usa erwartet einen BOOL, nicht den String
        # "ja"/"nein". Ein String ist in Python immer wahr -- ein "nein"
        # haette als Zustimmung zur Datenuebermittlung in die USA geendet,
        # also genau falsch herum bei der einen Entscheidung, bei der das
        # niemand verzeiht. Deshalb der ausdrueckliche Vergleich.
        ja = str(knopf["wert"]).strip().lower() == "ja"
        repo.setze_szene_usa(conn, chat_id, ja)
        repo.schreibe_journal(
            conn, chat_id, "entschieden",
            "US-Modell fuer Szenentexte: ja" if ja else "US-Modell fuer Szenentexte: nein",
            quelle="knopf",
        )
        tg.sende(chat_id, _TEXT_USA_JA if ja else _TEXT_USA_NEIN)
        # Der Auftrag, der auf diese Antwort gewartet hat, laeuft jetzt --
        # ueber den Weg, den die Antwort festgelegt hat. Bisher tat das nur
        # der Erkenner-Pfad (gesprochenes "ja"); der Knopf setzte den Stand
        # und liess den Auftrag liegen (Live-Fall Testgruppe 05.09. 22:09:
        # "USA" gedrueckt, nichts passierte, ein spaeteres "ja" im Chat war
        # wirkungslos, weil der Stand nicht mehr "offen" war).
        auftrag = repo.hole_und_loesche_offenen_szenenauftrag(conn, chat_id)
        if auftrag:
            from interview_theater import szene

            szene.starte(conn, tg, klm, e, chat_id, auftrag)
        return "US-Modell: ja" if ja else "Bleibt in der Schweiz"
    # Unbekannte art: nur moeglich, wenn eine spaetere Fassung eine Art
    # einfuehrt und eine aeltere die Zeile liest. Nichts tun ist hier richtig.
    log.error("Unbekannte Knopf-art %r, chat_id=%s", art, chat_id)
    return _TEXT_UNBEKANNT


def behandle(conn, tg, klm, e, druck: dict) -> bool:
    """Verarbeitet einen normalisierten Knopfdruck
    (``telegram.lies_knopfdruck``). Liefert True, wenn er zu diesem Bot
    gehoerte und beantwortet wurde.

    Antwortet IMMER mit answerCallbackQuery, auch wenn nichts geschieht --
    ohne diese Antwort dreht sich in der App eine Ladeanzeige weiter, und das
    sieht fuer die Gruppe nach einem haengenden Bot aus.

    Ein Knopf aus einer anderen Gruppe (``knopf.chat_id`` passt nicht) wirkt
    nicht: dieselbe Datenbank traegt alle Gruppen des Workshops, und eine
    weitergeleitete Nachricht darf nie in fremde Daten schreiben."""
    knopf_id = _id_aus_daten(druck["data"])
    if knopf_id is None:
        return False

    chat_id = druck["chat_id"]
    knopf = repo.hole_knopf(conn, knopf_id)
    if knopf is None or (chat_id is not None and knopf["chat_id"] != chat_id):
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_UNBEKANNT)
        return True

    chat_id = knopf["chat_id"]
    if not repo.beanspruche_knopf(conn, knopf_id):
        # Zweiter Druck: beantworten, aber nichts wiederholen (AGENTS.md).
        tg.beantworte_knopf(druck["callback_query_id"], _TEXT_SCHON_BENUTZT)
        _entferne_tastatur(tg, chat_id, druck["message_id"])
        return True

    meldung = _wirke(conn, tg, klm, e, knopf, chat_id)
    tg.beantworte_knopf(druck["callback_query_id"], meldung)
    _entferne_tastatur(tg, chat_id, druck["message_id"])
    return True

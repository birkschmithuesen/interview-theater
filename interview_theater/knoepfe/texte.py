"""Die Konstanten der Knopf-Navigation: Arten, Wortlaute, Anweisungen.

Hierher gehoert alles, was ein Wert ist und keine Wirkung -- die
``ART_*``-Kennungen der Knopfzeilen, die Knopfbeschriftungen und Systemzeilen
im Wortlaut, die Phasennummern, mit denen die Angebote arbeiten, und die
``ANWEISUNG_*``-Vorlagen fuer die Auftragszuege.

**Warum an einer Stelle:** der Wortlaut ist das, was die Gruppe im Chat sieht,
und er wird oefter geaendert als die Logik darunter -- am Workshoptag auch
zwischen zwei Neustarts. ``tests/test_systemzeilen.py`` liest das Paket als
Ganzes auf verbotene Wendungen ab; eine Zeile, die hier steht, steht nicht
noch einmal woanders.

Dieses Modul importiert nichts aus dem Paket und ist damit die unterste
Schicht: jedes andere Modul darf daraus lesen, keines schreibt hierher
zurueck.
"""

import logging



#: Ein Logger fuer das ganze Paket, ausdruecklich benannt und nicht
#: ``__name__``: die Logzeilen der Knopf-Navigation sollen nach der Aufteilung
#: in Module (06.09.2026) weiter unter demselben Namen stehen wie vorher --
#: eine Logdatei aus dem Workshop bleibt so vergleichbar.
log = logging.getLogger("interview_theater.knoepfe")

#: Praefix in ``callback_data``. Ein Buchstabe, weil daneben nur noch die id
#: Platz hat -- und sie soll auch bei einer sechsstelligen id nicht an die
#: 64-Byte-Grenze stossen (``k:999999`` sind neun Bytes).
PRAEFIX = "k:"

ART_KERNTHEMA = "kernthema"

ART_AUFNAHME = "aufnahme"

ART_PHASE = "phase"

#: "Noch nicht" unter der proaktiven Phasenmeldung (06.09.2026): das Angebot
#: ist abgelehnt, der Merkposten ``arbeitsstand.phase_angeboten`` steht schon
#: -- es passiert also genau nichts ausser einer kurzen Bestaetigung. Ein
#: eigener Knopf und nicht "einfach nicht druecken", damit die Gruppe das
#: Angebot vom Tisch nehmen kann, statt es stehen zu lassen.
ART_NOCH_NICHT = "noch_nicht"

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

#: Die beiden Knoepfe unter der Auswertungs-Zeile (06.09.2026, Birk 09:55):
#: die Zusammenfassung (= derselbe Weg wie ``aufnahme.zeige_verdichtung``)
#: und das Transkript im Wortlaut (= der Weg von ``/wortlaut``, in Teilen,
#: wenn es laenger ist als ``telegram.NACHRICHT_GRENZE``). ``wert`` ist die
#: ``aufnahme.id`` des Interviewkopfes.
ART_ZUSAMMENFASSUNG = "zusammenfassung"

ART_TRANSKRIPT = "transkript"

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

#: Eine der zehn zur Wahl stehenden Fragen -- ``wert`` ist ihre NUMMER
#: (1-10), nicht der Text: der steht in ``arbeitsstand.fragen_auswahl``, und
#: ein Druck togglet nur, er speichert nichts.
ART_FRAGE_WAHL = "frage_wahl"

#: "Diese 3 nehmen" -- die angetippten Fragen werden zur Frageliste.
ART_FRAGEN_UEBERNEHMEN = "fragen_uebernehmen"

#: "Andere zehn" -- ein neuer Gespraechszug mit der Anweisung, zehn ANDERE
#: Fragen vorzuschlagen (die bisherigen stehen namentlich im Auftrag).
ART_FRAGEN_ANDERE = "fragen_andere"

#: "Eigene Idee" in der Fragenauswahl -- die naechste Nachricht der Gruppe
#: sind eigene Fragen; sie werden ergaenzt und die Auswahl kommt neu.
ART_FRAGEN_EIGENE = "fragen_eigene"

#: "Leitfaden zeigen" -- deterministisch aus der Datenbank, kein Modell.
ART_LEITFADEN = "leitfaden"

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

#: Phase 7 · Schaerfung des Stuecks: eine Szene im Volltext zeigen, das
#: Textbuch als Datei.
ART_DURCHLAUF_SZENE = "durchlauf_szene"

ART_TEXTBUCH = "textbuch"

#: Phase 4 · Geschichte: den Vorschlag (Bogen, Ende, Szenenfolge) speichern.
#: ``wert`` ist "<weiter|anders>|<Vorschlagstext>" wie bei der Szenenfolge.
ART_GESCHICHTE_SPEICHERN = "geschichte_speichern"

#: Phase 5 · Schaerfung: eine Szenen- bzw. Figuren-Schaerfung uebernehmen
#: (``wert`` ist die Szenennummer bzw. der Figurenname), eine weitere Runde
#: anstossen, oder weiter zu den Szenentexten.
ART_SCHAERFUNG_SZENE = "schaerfung_szene"

ART_SCHAERFUNG_FIGUR = "schaerfung_figur"

ART_SCHAERFUNG_RUNDE = "schaerfung_runde"

#: Phase 7 · Schaerfung des Stuecks (06.09.2026): je Befund "Szene N
#: ueberarbeiten" (``wert`` ist die ``stueckpruefung.id``) und "Lassen",
#: darunter "Noch eine Pruefrunde".
ART_PRUEFUNG_SZENE = "pruefung_szene"

ART_PRUEFUNG_LASSEN = "pruefung_lassen"

ART_PRUEFUNG_RUNDE = "pruefung_runde"


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
_TEXT_ANDERS = "Gespeichert. Was soll anders sein?"

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
    # Die Verfeinerungsebene der Fragen (06.09.2026): dieselbe Grundleiste,
    # dieselbe Notiert-Zeile, derselbe Schreibweg -- nur ein anderes Feld.
    "einleitungen": "Einleitungen",
    # Die weichen Fassungen (06.09.2026, 10:18): derselbe Weg, dieselbe
    # Leiste, dieselbe Notiert-Zeile -- nur ein anderes Feld.
    "fragen_weich": "Fragen in weicher Fassung",
}

#: Wo eine Art landet, wenn das Arbeitsstand-Feld anders heisst als der
#: Vorschlagsmarker. Eine Tabelle statt eines ``if`` in ``_speichere``: der
#: Marker heisst nach dem, was die Gruppe sieht (Einleitungen), die Spalte
#: nach dem, was drinsteht (``frage_einleitungen`` -- Einleitungen zu FRAGEN,
#: nicht zu Szenen).
_FELD_FUER = {"einleitungen": "frage_einleitungen"}

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

#: Der Sonderfall unter ``aufnahme.MINDEST_WOERTER``: nichts wurde
#: verdichtet, und die Gruppe kann darauf bestehen (06.09.2026).
_TEXT_TROTZDEM_AUSWERTEN_KNOPF = "Trotzdem auswerten"

#: Die zwei Knoepfe unter der Auswertungs-Zeile (06.09.2026).
_TEXT_ZUSAMMENFASSUNG_KNOPF = "Zusammenfassung zeigen"

_TEXT_TRANSKRIPT_KNOPF = "Transkript zeigen"

#: Was dasteht, wenn ein Interview gar kein Transkript hat.
_TEXT_KEIN_TRANSKRIPT = "Zu diesem Interview habe ich keinen Wortlaut."

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

#: Setting, Figuren & Geschichte (frei erfunden). Der Rahmen wird seit dem
#: Umbau vom 05.09.2026 nachts HIER gesetzt, die Geschichte seit dem
#: 06.09.2026 ebenfalls -- es ist EINE Station, ohne Zaesur dazwischen.
PHASE_SETTING = 4

#: Rueckwaertskompatibler Name: der Rahmen ist Teil von Phase 4 geworden.
PHASE_RAHMEN = PHASE_SETTING

#: Rueckwaertskompatibler Name: die Geschichte ist Teil von Phase 4 geworden
#: (06.09.2026). Dieselbe Nummer, damit kein Aufrufer eine Station meint,
#: die es nicht mehr gibt.
PHASE_GESCHICHTE = PHASE_SETTING

#: Die Schaerfung am Material -- hier kommen die Interviews wieder ins Spiel.
PHASE_SCHAERFUNG = 5

#: Die Phase, in der die Szenentexte entstehen, und die der Stueck-Pruefung.
#: Als Konstanten und nicht als 6 und 7 im Code: eine achte Phase soll
#: nichts brauchen ausser ``phasen.PHASEN``.
PHASE_SZENEN = 6

PHASE_STUECKPRUEFUNG = 7

#: Rueckwaertskompatibler Name: bis zum 06.09.2026 hiess Phase 7 (damals 8)
#: "Durchlauf".
PHASE_DURCHLAUF = PHASE_STUECKPRUEFUNG

_TEXT_SZENENFORM_FRAGE = "Welche Form soll Szene {nummer} haben?"

#: Markiert den Vorschlag des Bots in der Formleiste -- er steht zuerst, ist
#: aber sichtbar ein Vorschlag (Birk, 06.09.2026 00:30).
TEXT_FORM_VORSCHLAG_ZUSATZ = " (Vorschlag)"

_TEXT_USA_FRAGE_KNOEPFE = "Tippt an, was gelten soll:"

_TEXT_USA_JA_KNOPF = "Ja, US-Modell"

_TEXT_USA_NEIN_KNOPF = "Nein, Schweiz"

_TEXT_USA_JA = (
    "Gut, Szenen kommen ab jetzt vom US-Modell. Ich sage es vor jeder "
    "Szene nochmal."
)

_TEXT_USA_NEIN = "Verstanden, alles bleibt in der Schweiz. Ich frage nicht wieder."

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

#: Wie viele Fragen zur Wahl stehen und wie viele es am Ende sind. Zehn ist
#: eine Auswahl, aus der man waehlen kann, ohne zu lesen wie in einem
#: Fragebogen; drei ist, womit eine 15-Jaehrige eine fremde Person auf der
#: Strasse anspricht, ohne dass es ein Verhoer wird (Birk, 06.09.2026).
#: "Andere Zahl" gibt es hier bewusst NICHT -- die Zahl ist eine Vorgabe des
#: Stuecks, keine Entscheidung der Gruppe.
FRAGEN_ZUR_WAHL = 10

FRAGEN_ANZAHL = 3

#: Wie lang eine Frage auf einem Knopf sein darf. Telegram schneidet laengere
#: Beschriftungen auf dem Telefon selbst ab, und zwar ohne Hinweis -- besser
#: eine sichtbare Kuerzung als eine unsichtbare. Der volle Text steht im
#: Chat ueber den Knoepfen und in ``arbeitsstand.fragen_auswahl``.
KNOPF_LAENGE = 40

#: Der Haken vor einer gewaehlten Frage. Ein Zeichen, kein zweiter Knopf:
#: der Zustand muss auf dem Telefon in einem Blick lesbar sein.
_HAKEN = "✓ "

_TEXT_FRAGEN_UEBERNEHMEN_KNOPF = f"Diese {FRAGEN_ANZAHL} nehmen"

_TEXT_FRAGEN_ANDERE_KNOPF = f"Andere {FRAGEN_ZUR_WAHL}"

_TEXT_FRAGEN_EIGENE_KNOPF = "Eigene Idee"

#: Die Aufforderung ueber der Auswahl (06.09.2026, 10:05, Birk).
#:
#: **Kein Menue mehr.** Die zehn Toggle-Knoepfe funktionierten am Telefon
#: nicht: "sobald ich auf eine Frage klicke, verschwindet das Menue". Der
#: Weg ist jetzt der einfachste, den es gibt -- die Fragen stehen
#: ausgeschrieben und nummeriert im Text, und die Gruppe sagt die Nummern.
#: Sprechen kann sie ohnehin; ein Knopf, der auf dem Geraet der Gruppe
#: verschwindet, ist schlechter als gar keiner.
_TEXT_FRAGEN_WAHL = (
    f"Sagt mir die Nummern von genau {FRAGEN_ANZAHL} Fragen - getippt oder "
    "als Sprachnachricht."
)

#: Die Antwort auf "Diese 3 nehmen" bei falscher Anzahl. Sie geht als
#: answerCallbackQuery raus (das kleine graue Band oben in der App) und
#: nicht als Nachricht: eine Fehlbedienung soll den Chat nicht zumuellen.
_TEXT_FRAGEN_NICHT_DREI = f"Waehlt genau {FRAGEN_ANZAHL}."

#: Dieselbe Regel im Chat, wenn die Gruppe Nummern GESAGT hat: hier ist eine
#: Zeile richtig, weil die Gruppe auf eine Antwort wartet.
_TEXT_FRAGEN_NUMMERN_FALSCH = f"Bitte genau {FRAGEN_ANZAHL} Nummern."

_TEXT_FRAGEN_EIGENE = (
    "Schreibt eure Frage oder Fragen - ich nehme sie mit in die Auswahl."
)

_TEXT_FRAGEN_KEINE_AUSWAHL = "Diese Auswahl kenne ich nicht mehr."

#: Nach dem Uebernehmen: die drei Fragen stehen, und die Pruefung laeuft an.
_TEXT_FRAGEN_UEBERNOMMEN = "Notiert, eure {anzahl} Fragen:"

#: Dasselbe, wenn die Gruppe die Nummern GESAGT hat (06.09.2026): die
#: Nummern stehen mit drin, damit sie sieht, was der Bot verstanden hat.
_TEXT_FRAGEN_NOTIERT = "Notiert: Fragen {nummern}:"

#: Was der Bot sagt, waehrend die Sensibilitaetspruefung im Thread laeuft.
#: Sie ist kein Selbstzweck und wird deshalb begruendet: die Gruppe soll
#: wissen, warum der Bot nach dem Speichern noch etwas tut.
TEXT_PRUEFUNG_LAEUFT = (
    "Ich sehe die Fragen noch einmal durch: bei welchen braucht ihr einen "
    "Satz zur Einleitung, bevor ihr sie einer fremden Person stellt?"
)

_TEXT_LEITFADEN_KNOPF = "Leitfaden zeigen"


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


#: Die Arbeitszeilen, die SOFORT rausgehen, wenn ein laengerer Auftragszug
#: startet (06.09.2026, 10:10, Birk). Sie werden geloescht, sobald die
#: Antwort da ist (``ablauf.arbeitet_sichtbar``) -- eine Arbeitsmeldung, die
#: stehen bleibt, liest sich wie eine haengende Aufgabe.
TEXT_ARBEIT_SENSIBILITAET = "🤔 Ich sehe die Fragen kurz durch …"

TEXT_ARBEIT_EROEFFNUNG = "✍️ Ich schreibe euch einen Eroeffnungstext …"


# --- Phase 7 · Schaerfung des Stuecks (06.09.2026) ------------------------

_TEXT_PRUEFUNG_LAEUFT = (
    "Ich lese euer Stueck jetzt einmal am Stueck durch. Das dauert einen "
    "Moment."
)

_TEXT_PRUEFUNG_SZENE_KNOPF = "Szene {nummer} ueberarbeiten"

_TEXT_PRUEFUNG_LASSEN_KNOPF = "Lassen"

_TEXT_PRUEFUNG_RUNDE_KNOPF = "Noch eine Pruefrunde"

_TEXT_PRUEFUNG_LASSEN = "Gut, das bleibt so."

_TEXT_PRUEFUNG_UNBEKANNT = "Diesen Befund finde ich nicht mehr."

#: Was nach einer Ueberarbeitung dasteht: der Befund ist ueberholt, aber es
#: laeuft KEINE Pruefung von selbst nach (Birk) -- ein Modellaufruf je
#: Szenenaenderung waere ein Automatismus, den niemand bestellt hat.
_TEXT_PRUEFUNG_UEBERHOLT = (
    "Sobald die Szene neu steht, ist meine Pruefung von vorhin ueberholt. "
    "Wenn ihr wollt, lese ich das Stueck noch einmal als Ganzes."
)


# --- Verarbeitung ---------------------------------------------------------


#: Bestaetigung statt Ueberschreiben (06.09.2026, Birk, Testgruppe 21:50):
#: steht das Feld schon und hat niemand um eine Aenderung gebeten, ist
#: "Gefaellt uns, weiter" ein Ja zum Bestehenden, kein neuer Wert.
_TEXT_SCHON_GESETZT = "Steht schon so."


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


# --- Figuren, Ebene 2: Figur fuer Figur -----------------------------------

_TEXT_FIGUR_PASST_KNOPF = "Passt"

_TEXT_FIGUR_INTERVIEW_KNOPF = "Anderes Interview"

_TEXT_FIGUR_DUKTUS_KNOPF = "Anderer Duktus"

_TEXT_FIGUR_ENTFERNEN_KNOPF = "Entfernen"

_TEXT_FIGUR_INTERVIEW_FRAGE = "Aus welchem Interview spricht {name}?"

#: Ebene 2 ist fertig. Seit dem 06.09.2026 geht es damit NICHT in eine neue
#: Phase, sondern innerhalb von Phase 4 weiter zur Geschichte: eine kurze
#: Zeile und eine offene Frage, keine Phasenmeldung dazwischen (Birk).
_TEXT_FIGUREN_FIXIERT = "Die Figuren stehen."

#: Die Ueberleitung von der Figurenliste zur Geschichte -- Birks Wortlaut
#: der offenen Frage. Zwei Knoepfe wie bei jedem Eintritt in eine Ebene:
#: die Gruppe zuerst, oder ein Vorschlag vom Bot.
_TEXT_ZUR_GESCHICHTE = (
    "Die Figuren stehen - jetzt die Geschichte, im Groben.\n\n"
    "Was soll passieren, wie soll es ausgehen?"
)

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


_TEXT_KEIN_INTERVIEW = "Es gibt noch kein Interview, aus dem sie sprechen koennte."

_TEXT_PROAKTIV = "Bevor ich vorschlage: habt ihr selbst schon Ideen?"

_TEXT_WIR_ZUERST_KNOPF = "Ja, wir zuerst"

_TEXT_SCHLAG_VOR_KNOPF = "Schlag du vor"

_TEXT_WIR_ZUERST = "Gut - ich hoere zu."


#: Die proaktive Phasenmeldung (06.09.2026, Birk nach der Testgruppe): sobald
#: alles Noetige gespeichert ist, sagt der Bot es von selbst -- in EINER
#: kurzen, EIGENEN Nachricht, nicht als vierter Knopf unter 1 100 Zeichen
#: Fliesstext. Gemessen am Testabend: neun angebotene Phasenknoepfe, null
#: Druecke; sie hingen alle unter langen Texten.
_TEXT_PHASE_ANGEBOT = "{erledigt} steht. Weiter zu {phase}?"

#: Die Frage unter der Abschlussnachricht (06.09.2026): die Parameter stehen
#: darueber, hier steht nur noch, wohin es geht.
_TEXT_PHASE_WEITER = "Weiter zu {phase}?"

#: Der zweite Knopf hiess bis zum 06.09.2026 "Noch nicht". Er heisst jetzt
#: nach dem, was die Gruppe damit tut: unter einer Abschlussnachricht mit
#: allen Werten ist "Noch nicht" keine Antwort mehr -- "Noch etwas aendern"
#: schon. Die art (``ART_NOCH_NICHT``) und ihre Wirkung bleiben.
_TEXT_PHASE_NOCH_NICHT_KNOPF = "Noch etwas aendern"

_TEXT_NOCH_NICHT = "Gut, wir bleiben hier."


#: Was "Schlag du vor" je Phase vom Modell verlangt -- die Anweisung, die
#: ``ablauf.starte_auftrag`` an den Koerper haengt. Je Phase eine, weil in
#: jeder etwas anderes vorzuschlagen ist; fehlt eine, gibt es einen
#: allgemeinen Auftrag.
ANWEISUNGEN = {
    1: "Schlag der Gruppe eine Begriffsliste vor und haeng sie als Block "
       "'VORSCHLAG BEGRIFFE:' an.",
    2: "Schlag der Gruppe genau zehn Interviewfragen zur Auswahl vor. Haeng "
       "sie als Block 'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je Zeile, "
       "genau zehn Zeilen, ohne Nummerierung. Thematisch gestreut ueber die "
       "Begriffe der Gruppe, altersgerecht, und so, dass eine 15- bis "
       "18-Jaehrige sie einer FREMDEN Person auf der Strasse stellen kann. "
       "Wiederhol die Fragen nicht im Fliesstext - die Gruppe sieht sie auf "
       "den Knoepfen.",
    # Phase 4: das SETTING zuerst -- und ausschliesslich aus den Begriffen
    # und Fragen der Gruppe. Kein Material: die Interviews stehen in diesem
    # Prompt gar nicht (``kontext.material_erlaubt``), und der Auftrag sagt
    # es noch einmal, damit das Modell nicht danach fragt.
    4: "Schlag drei Settings vor - Ort, Zeit, Anlass in je einer Zeile, frei "
       "erfunden aus den Begriffen und Fragen der Gruppe, NICHT aus "
       "Interviews. Haeng sie als Block 'VORSCHLAG RAHMEN:' an, einen "
       "Vorschlag je Zeile.",
}

#: Die Geschichte ist seit dem 06.09.2026 Teil von Phase 4 und hat einen
#: eigenen Weg (``szenenfolge.starte_geschichte``) -- sie steht deshalb
#: nicht mehr in ``ANWEISUNGEN``, sondern als Anweisung dort.
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

#: "Andere zehn": die bisherigen Fragen stehen namentlich im Auftrag, damit
#: das Modell sie nicht umformuliert wieder vorlegt. Ohne diese Aufzaehlung
#: kaeme im zweiten Durchgang dieselbe Liste mit anderen Worten -- gemessen
#: an der Kernthema-Stufe, an der genau das passierte.
ANWEISUNG_FRAGEN_ANDERE = (
    "Schlag genau zehn ANDERE Interviewfragen vor. Diese hier hatten wir "
    "schon, nimm keine davon wieder und formuliere keine davon um:\n{alte}\n"
    "Haeng die neuen als Block 'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je "
    "Zeile, genau zehn Zeilen. Wiederhol sie nicht im Fliesstext."
)

#: Die Gruppe hat eigene Fragen diktiert -- sie kommen in die Auswahl, und
#: der Bot fuellt auf zehn auf, statt sie zu ersetzen.
ANWEISUNG_FRAGEN_EIGENE = (
    "Die Gruppe hat eigene Fragen genannt. Nimm sie unveraendert als erste "
    "Zeilen und ergaenze sie mit deinen Vorschlaegen auf genau zehn. Haeng "
    "alles als Block 'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je Zeile."
)

#: Die Sensibilitaetspruefung. Der Rahmen steht im Auftrag und nicht nur im
#: Phasen-Prompt: dieser Zug entscheidet, ob eine 15-Jaehrige vor einer
#: fremden Person einen Satz zur Hand hat oder nicht.
ANWEISUNG_EINLEITUNGEN = (
    "Sieh dir diese Interviewfragen der Gruppe an:\n{fragen}\n\n"
    "Die Interviews fuehren 15- bis 18-jaehrige Frauen mit FREMDEN Personen "
    "auf der Strasse oder im Verein. Pruefe jede Frage: beruehrt sie ein "
    "sensibles Thema (Familie, Herkunft, Religion, Gewalt, Liebe und Koerper, "
    "Geld, Krankheit, Flucht, Diskriminierung)? Formuliere JEDE sensible "
    "Frage zu EINEM weichen Gespraechsstueck um - zwei bis drei Saetze, die "
    "die Interviewerin am Stueck sagt: der Grund, die Freiheit nicht zu "
    "antworten, und die Frage selbst, in EINEM Fluss. Nicht Einleitung und "
    "Frage aneinandergehaengt, sondern ein Text, den man so ausspricht. "
    "Du-Form, sprechbar, im Ton einer 15- bis 18-Jaehrigen, die eine fremde "
    "Person anspricht - kein Behoerdendeutsch, keine Floskeln wie 'im Rahmen "
    "unseres Projektes'. Der Kern der Frage bleibt derselbe: erfinde kein "
    "neues Thema und lass keines weg. Haeng das als Block "
    "'VORSCHLAG FRAGEN WEICH:' an, je Zeile "
    "'<Fragennummer> — <weiche Fassung>' - nur fuer die sensiblen Fragen, "
    "die uebrigen bleiben, wie sie sind. Ist keine Frage sensibel, schreib "
    "in den Block genau die eine Zeile 'Keine der Fragen braucht eine "
    "besondere Einleitung.' Sag im Text davor in einem Satz, was du "
    "gefunden hast, und stell eine Frage an die Gruppe. Schreib die "
    "Fragenliste nicht noch einmal unveraendert ab."
)

#: Eroeffnung und Abschluss in einem Block -- es ist eine Entscheidung.
ANWEISUNG_EROEFFNUNG = (
    "Jetzt fehlt noch, womit das Interview anfaengt und aufhoert. Schlag "
    "einen Eroeffnungstext vor, den die Interviewerin einer fremden Person "
    "sagt, bevor sie die erste Frage stellt - drei bis fuenf Saetze: wer wir "
    "sind, dass wir ein Theaterprojekt im Verein machen, wofuer die Antworten "
    "verwendet werden (anonym, als Material fuer ein Stueck), dass man "
    "jederzeit aufhoeren kann, und die Bitte um Erlaubnis, das Gespraech "
    "aufzunehmen. Dazu einen kurzen Abschluss: Dank und was jetzt weiter "
    "passiert. Haeng beides als Block 'VORSCHLAG EROEFFNUNG:' an - zuerst "
    "die Eroeffnung, danach eine Zeile, die mit 'Abschluss:' beginnt. "
    "Sprache wie von einer 16-Jaehrigen, keine Behoerdensaetze."
)


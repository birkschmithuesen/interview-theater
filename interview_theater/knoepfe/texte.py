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
#: Die zwei Knoepfe des Phase-5-Gates (Padua, 07.10.2026,
#: ``workshop.p5_check_aktiv``, ``befehle.p5_gate``): die Werkbank-
#: Uebersicht ist richtig, dann startet Phase 5 -- oder sie ist es nicht,
#: dann bleibt die Gruppe in Phase 4 und sagt, was zu aendern ist.
ART_P5_CHECK_OK = "p5_check_ok"
ART_P5_CHECK_AENDERN = "p5_check_aendern"
#: Form je Szene (Phase 6) -- dasselbe Ziel wie ``/szene <n> form <wert>``.
#: Der Wert der Knopfzeile traegt beides, durch ':' getrennt: "3:dialog".
ART_SZENENFORM = "szenenform"
#: Stil je Szene (Phase 7, Feinschliff -- 06.09.2026, Birk 12:50). Wert wie
#: bei der Form: ``"<nummer>:<slug>"``.
ART_SZENENSTIL = "szenenstil"
#: Einwilligung ins US-Modell -- dasselbe Ziel wie ``/szene usa ja|nein``.
ART_SZENE_USA = "szene_usa"
#: Die Interviewsprache fuer Whisper (Karte A1, D2) -- nur in Profilen mit
#: sprache.whisper = "auto" (Padua), beim Eintritt in Phase 3.
ART_STT_SPRACHE = "stt_sprache"
#: Der Undo-Knopf unter einer "Notiert:"-Meldung des Erkenners (Karte U,
#: 01.10.2026). ``wert`` ist die ``erkenner_lauf.id`` -- eine Meldung, eine
#: Ruecknahme, keine Einzelauswahl.
ART_UNDO = "undo"
#: Der Redo-Knopf unter einer Undo-Erledigt-Quittung (Befund 1a, Padua
#: Phase-2-Ende 04.10.2026). ``wert`` ist dieselbe ``erkenner_lauf.id`` wie
#: beim Undo-Knopf -- der Spiegel davon, nur einmal moeglich.
ART_REDO = "redo"
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
#: "Take these" unter dem Top-5-Vorschlag des Begriffsboards (Karte
#: t_4517d4ad, D6): EIN Knopf, der Wert ist die Begriffsliste.
ART_BOARD_UEBERNEHMEN = "board_uebernehmen"
#: "Etwas aendern" unter der Abschlussnachricht des Begriffsboards (Birk
#: 05.10.2026): die Top 5 sind schon gespeichert, der Knopf fragt in EINEM
#: Satz, was sich aendern soll -- die Antwort geht ueber den Chat (Auto-
#: Speichern). Kein Wert, kein Modellaufruf.
ART_BOARD_AENDERN = "board_aendern"
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
#: Die Antwort auf \"Das klingt nach einem Interview (M:SS)\" -- eine lange
#: Sprachnachricht, die OHNE laufenden Interviewmodus ankam (06.09.2026,
#: Live-Fall Gruppe 1 13:32). Der ``wert`` traegt die ``aufnahme.id``: der
#: Knopf muss genau DIESE Aufnahme einsammeln koennen, auch wenn inzwischen
#: Minuten vergangen sind.
ART_OHNE_KNOPF_JA = "ohne_knopf_ja"
ART_OHNE_KNOPF_NEIN = "ohne_knopf_nein"
#: Die Folgefrage nach \"Ja, als Interview\": fertig auswerten oder offen
#: lassen. Der ``wert`` traegt die Kopf-id.
ART_OHNE_KNOPF_FERTIG = "ohne_knopf_fertig"
ART_OHNE_KNOPF_WEITER = "ohne_knopf_weiter"
#: Der eine Web-Knopf nach einem Interview (Phase 3 Web-UX, 02.10.2026):
#: ersetzt auf dem Web-Kanal die ganze Telegram-Leiste aus
#: ``biete_nach_aufnahme``. Kein ``wert`` -- die Wirkung liest den Chat.
ART_INTERVIEWS_FERTIG = "interviews_fertig"

# --- Phase 2 · Fragen einzeln durchgehen und der Leitfaden ----------------
#
# Birk, 06.09.2026: die Fragen-Erarbeitung wird Multiple-Choice -- das war
# der erste Umbau (Vorschlag, Auswahl per Nummer, Sensibilitaetspruefung als
# eigener Schritt danach).
#
# Padua, 02.10.2026: zweiter Umbau. Der Vorschlag traegt die
# Sensibilitaetspruefung jetzt selbst (im selben Modellzug), und die Auswahl
# laeuft nicht mehr ueber gesagte Nummern, sondern **Frage fuer Frage**: eine
# Nachricht je Frage, drei Knoepfe (Annehmen, Verwerfen, Schaerfen). Die
# Nummernwahl (``lies_fragennummern``) und die zugehoerigen Knoepfe
# (``ART_FRAGE_WAHL``, ``ART_FRAGEN_UEBERNEHMEN``, ``ART_FRAGEN_EIGENE``)
# sind damit Geschichte -- ihre Arten und Handler bleiben im Code, damit ein
# Druck aus einer alten, schon verschickten Nachricht nicht ins Leere laeuft
# (AGENTS.md, Fehlerhaltung), angeboten werden sie nicht mehr.
#
# Daraus der Leitfaden (``leitfaden.py``), unveraendert.

#: Eine der zur Wahl stehenden Fragen -- ``wert`` ist ihre NUMMER, nicht der
#: Text: der steht in ``arbeitsstand.fragen_auswahl``, und ein Druck togglet
#: nur, er speichert nichts. **Stillgelegt seit 02.10.2026**, siehe oben.
ART_FRAGE_WAHL = "frage_wahl"
#: "Diese 3 nehmen" -- die angetippten Fragen werden zur Frageliste.
#: **Stillgelegt seit 02.10.2026.**
ART_FRAGEN_UEBERNEHMEN = "fragen_uebernehmen"
#: "Andere Richtung" unter dem Fragenueberblick (02.10.2026): der Bot fragt
#: deterministisch nach der gewuenschten Richtung, die naechste freie
#: Nachricht der Gruppe loest einen neuen Vorschlag aus
#: (``fragen.nimm_offene_frage_text``). Bis 02.10.2026 hiess der Knopf
#: "Andere Fragen" und rief sofort einen neuen Vorschlag ohne Richtungsfrage
#: auf -- derselbe ``ART_*``, neues Verhalten, siehe ``_wirkung_fragen_andere``.
ART_FRAGEN_ANDERE = "fragen_andere"
#: "Eigene Idee" in der alten Fragenauswahl. **Stillgelegt seit 02.10.2026**
#: (ersetzt durch "Andere Richtung" mit anschliessender freier Nachricht).
ART_FRAGEN_EIGENE = "fragen_eigene"
#: "Fragen vorschlagen" in Padua Phase 2 (Birk, 05.10.2026): erzeugt NICHTS,
#: sondern fragt zuerst, ob die Gruppe selbst noch Fragen hat
#: (``fragen.frage_nach_eigenen``) -- eigene Fragen zuerst.
ART_FRAGEN_VORSCHLAGEN = "fragen_vorschlagen"
#: Die zwei Antworten auf diese Rueckfrage: "Wir haben noch welche" (laedt
#: ein, nichts entsteht) und "Ja, schlag welche vor" (die Gegenueberstellung
#: mit den KI-Fragen, ``fragen.ja_vorschlagen``).
ART_FRAGEN_NOCH_EIGENE = "fragen_noch_eigene"
ART_FRAGEN_JA_VORSCHLAGEN = "fragen_ja_vorschlagen"
#: "Leitfaden zeigen" -- deterministisch aus der Datenbank, kein Modell.
ART_LEITFADEN = "leitfaden"
#: "Ja, einzeln durchgehen" unter dem Fragenueberblick (02.10.2026): startet
#: die Frage-fuer-Frage-Stufe bei Frage 1.
ART_FRAGEN_EINZELN = "fragen_einzeln"
#: Die drei Knoepfe unter EINER vorgelegten Frage (02.10.2026). ``wert`` ist
#: in allen dreien die Fragennummer (1-basiert, Position in
#: ``fragen_auswahl``) -- nie der Text, der steht in der Tabelle ``knopf``.
ART_FRAGE_ANNEHMEN = "frage_annehmen"
ART_FRAGE_VERWERFEN = "frage_verwerfen"
ART_FRAGE_SCHAERFEN = "frage_schaerfen"
#: Das Angebot nach der letzten Entscheidung, wenn mindestens eine
#: angenommene Frage eine weiche Fassung hat (02.10.2026) -- ``wert`` bleibt
#: leer, es gibt je Gruppe genau ein offenes Angebot gleichzeitig.
ART_FRAGEN_WEICH_UEBERNEHMEN = "fragen_weich_uebernehmen"
ART_FRAGEN_WEICH_LASSEN = "fragen_weich_lassen"
#: Die Umformulier-Runde (Testkarte t_266e7485, 06.10.2026, nur Padua): nach
#: der Vorschau alt->neu nimmt die Gruppe entweder ALLE neuen Formulierungen
#: an oder behaelt ALLE alten -- einzelne Nummern laufen ueber eine freie
#: Chatnachricht (``knoepfe.fragen.nimm_offene_frage_text``), nicht ueber
#: einen Knopf je Frage (das waere bei zehn, zwanzig Fragen eine eigene
#: Tastatur je Nachricht). ``wert`` bleibt leer wie bei den Weich-Knoepfen.
ART_FRAGEN_UMFORMULIEREN_ALLE = "fragen_umformulieren_alle"
ART_FRAGEN_UMFORMULIEREN_KEINE = "fragen_umformulieren_keine"
#: Der Ausloeser fuer den versteckten Befehl ``/umformulieren`` selbst
#: (Review-Fix t_b371c0f1, 06.10.2026): ohne diesen Knopf hatte die
#: Umformulier-Runde keinen fuer die Gruppe sichtbaren Weg -- genau wie
#: ``/sortiert`` ueber den Knopf "Fertig sortiert" (web_vereint) erreichbar
#: ist, macht dieser Knopf ``/umformulieren`` nach "Fragen uebernommen"
#: erreichbar.
ART_FRAGEN_UMFORMULIEREN_ANBIETEN = "fragen_umformulieren_anbieten"

# --- Phase 6 · Szenen (05.09.2026) ----------------------------------------
#
# Die Knopf-Navigation durch Phase 6 und 7 (``szenenfolge.py``). Sie folgt
# derselben Grundregel wie alles hier: ein Vorschlag steht als Text im Chat,
# darunter haengen Knoepfe, und der Knopf traegt die Entscheidung selbst.
# Freie Nachrichten wirken daneben unveraendert weiter -- die Knoepfe sind
# ein Weg, kein Kaefig (docs/agents/entscheidungen.md).

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
#: "Wer spricht wie viel" -- die Sprechanteile je Figur (06.09.2026). Reine
#: Zaehlung ueber die Szentexte (``sprecher.anteile``), deterministisch aus
#: der Datenbank: Zusage 2 gilt, hier faellt kein Modellaufruf an.
ART_SPRECHANTEILE = "sprechanteile"
#: "Fruehere Fassungen" -- die Liste der frueher geschriebenen Fassungen
#: EINER Szene (06.09.2026, ``wert`` ist die Szenennummer). Deterministisch
#: aus ``szenenfassung``, kein Modellaufruf. Zurueckgesetzt wird nichts: das
#: waere eine Entscheidung mit Datenwirkung und ist bewusst nicht gebaut.
ART_FASSUNGEN = "fassungen"
#: Phase 4 · Geschichte: den Vorschlag (Bogen, Ende, Szenenfolge) speichern.
#: ``wert`` ist "<weiter|anders>|<Vorschlagstext>" wie bei der Szenenfolge.
ART_GESCHICHTE_SPEICHERN = "geschichte_speichern"
#: Phase 5 · Schaerfung: "Diese uebernehmen" auf der gezeigten Seite einer
#: Szenen- bzw. Figuren-Schaerfung (``wert`` traegt seit 07.10.2026 die
#: gezeigten ``schaerfung.id`` durch ``TRENNER`` getrennt, wie
#: ``ART_SCHAERFUNG_KEINE`` -- NICHT mehr alles, was je fuer dieses Ziel
#: zugeordnet wurde, siehe ``schaerfung.uebernimm_stellen``), eine weitere
#: Runde anstossen, oder weiter zu den Szenentexten.
ART_SCHAERFUNG_SZENE = "schaerfung_szene"
ART_SCHAERFUNG_FIGUR = "schaerfung_figur"
ART_SCHAERFUNG_RUNDE = "schaerfung_runde"
#: EINE Stelle aus dem Schaerfungs-Menue (06.09.2026, Analyse Abschnitt 2):
#: ``wert`` ist die ``schaerfung.id``. Ein Knopf je Option, statt einer
#: globalen Ja/Nein-Frage ueber einen Fliessblock.
ART_SCHAERFUNG_STELLE = "schaerfung_stelle"
#: "Keine davon": ``wert`` traegt die gezeigten ``schaerfung.id`` durch
#: ``TRENNER`` getrennt -- sie fallen weich heraus (N3), damit die naechste
#: Runde sie nicht erneut vorlegt.
ART_SCHAERFUNG_KEINE = "schaerfung_keine"
#: "Mehr zeigen" (07.10.2026, MAX_STELLEN als Gesamtgrenze aufgehoben):
#: ``wert`` ist "<sammelart>|<sammelwert>|<naechster_versatz>" -- blaettert
#: dieselbe Szene/Figur eine Seite weiter, ohne erneut zu modellieren (alles
#: steht schon in der Datenbank, kein Modellaufruf im Knopf-Handler).
ART_SCHAERFUNG_MEHR = "schaerfung_mehr"
#: Die zwei Wege nach der automatischen Zuordnung beim Eintritt in Phase 5
#: (Padua, 07.10.2026, "Entry zu voll"): "Sortieren" springt im Browser
#: direkt in den CoThinker-Tab (``_TEXT_SCHAERFUNG_SORTIEREN_KNOPF``, erkannt
#: in ``web_chat.py``s Knopf-Klick ueber den Beschriftungstext, derselbe Weg
#: wie ``aufnahme._TEXT_BUEHNE_NEUE_KARTE``), "Erst reden" stoesst eine kurze
#: Interviewzusammenfassung an (``schaerfung.starte_zusammenfassung``, Opus,
#: eigener Thread -- Zusage 2) und laesst danach freies Gespraech offen.
#: Kein ``wert`` noetig, beide Knoepfe wirken ohne Parameter.
ART_SCHAERFUNG_SORTIEREN = "schaerfung_sortieren"
ART_SCHAERFUNG_CHAT = "schaerfung_chat"
#: Phase 7 · Schaerfung des Stuecks (06.09.2026): je Befund "Szene N
#: ueberarbeiten" (``wert`` ist die ``stueckpruefung.id``) und "Lassen",
#: darunter "Noch eine Pruefrunde".
ART_PRUEFUNG_SZENE = "pruefung_szene"
ART_PRUEFUNG_LASSEN = "pruefung_lassen"
ART_PRUEFUNG_RUNDE = "pruefung_runde"
#: Phase 7 - Dramaturgie-Pruefung (06.09.2026, interview_theater/dramaturgie/).
#: ``ART_DRAMATURGIE`` stoesst den Lauf an, ``ART_DRAMATURGIE_SZENE`` traegt
#: die ``dramaturgie_befund.id`` und macht aus EINEM Befund EINEN
#: Szenenauftrag -- **der Bot schlaegt vor, er handelt nicht**: erst der
#: Knopfdruck loest einen Szenenlauf aus.
ART_DRAMATURGIE = "dramaturgie"
ART_DRAMATURGIE_SZENE = "dramaturgie_szene"
ART_DRAMATURGIE_LASSEN = "dramaturgie_lassen"


#: Trennzeichen im ``wert`` der Speicher-Leiste.
TRENNER = "|"

#: Die drei Knoepfe der **Grundleiste** -- sie stehen unter JEDER
#: Vorschlagsnachricht des Bots, in dieser Reihenfolge (05.09.2026 abends,
#: Birk). Der Wortlaut ist Absicht: er sagt, was die Gruppe TUT, nicht was
#: der Bot tut. "So speichern" ist deshalb ueberall durch "Gefaellt uns,
#: weiter" ersetzt.
#: Die Knopfregel vom 06.09.2026 (Birk, 10:55-11:10): Knoepfe gibt es nur,
#: wenn dahinter etwas FIXES gespeichert werden kann. Daraus folgen genau
#: drei Faelle -- (1) ein Optionen-Menue, (2) die Rueckspiegelung EINES
#: Wertes, (3) Phasen- und Kettenknoepfe. Unter einer offenen Frage steht
#: nichts.
#:
#: Die alte Grundleiste ("Eigene Idee" · "Passt, aber anders" · "Gefaellt
#: uns, weiter") ist damit weg: sie stand auch unter Listen, aus denen sich
#: gar kein einzelner Wert ergab, und "Gefaellt uns, weiter" nahm dann still
#: den ersten Vorschlag. Die Arten im Code bleiben (``ART_SPEICHERN``,
#: ``ART_ANDERS``, ``ART_EIGENE``) -- nur die Texte und die Zusammenstellung
#: sind neu.
_TEXT_EIGENE_KNOPF = "Anders"
_TEXT_ANDERS_KNOPF = "Nein, nochmal aendern"
_TEXT_SPEICHERN_KNOPF = "Ja, speichern"
_TEXT_BOARD_UEBERNEHMEN_KNOPF = "Diese nehmen"
#: Nach "Discussion done", wenn das Board die Top 5 schon gespeichert hat
#: (Birk 05.10.2026, Nachtrag 3/4 -- Wortlaut der englischen Fassung von
#: Birk): die Liste nach Rang, "gespeichert", EINE Frage mit zwei Knoepfen.
#: ``{anzahl}`` ist ein Zahlwort aus ``_ZAHLWOERTER``; fuer genau einen
#: Begriff gilt ``_TEXT_BOARD_GESPEICHERT_EINER``.
_TEXT_BOARD_GESPEICHERT = (
    "Das sind eure {anzahl} Begriffe – gespeichert. Gehen wir weiter?\n\n{liste}"
)
_TEXT_BOARD_GESPEICHERT_EINER = (
    "Das ist euer Begriff – gespeichert. Gehen wir weiter?\n\n{liste}"
)
#: Nach JEDER gespeicherten Begriffs-Korrektur in Phase 1 (Birk 05.10.2026,
#: Brief "p1-bleiben"): die knappe Form derselben Frage -- die Liste nach
#: der Korrektur, "gespeichert", weiter? Dieselben zwei Knoepfe wie oben
#: (``basis.biete_begriffe_aktualisiert``); die Phase wechselt nie von selbst.
_TEXT_BOARD_AKTUALISIERT = "Geaendert – gespeichert:\n\n{liste}\n\nWeiter?"
_ZAHLWOERTER = "ein,zwei,drei,vier,fuenf"
_TEXT_BOARD_WEITER_KNOPF = "Ja, weiter zu den Fragen"
_TEXT_BOARD_AENDERN_KNOPF = "Etwas aendern"
#: Die EINE Rueckfrage nach "Etwas aendern" -- deterministisch (Zusage 2).
_TEXT_BOARD_WAS_AENDERN = (
    "Was soll sich aendern – ein falsch verstandener Begriff, die "
    "Reihenfolge oder ein fehlender Begriff?"
)
_TEXT_BOARD_VORSCHLAG = (
    "Die Diskussion ist zu Ende. Auf eurem Begriffsboard stehen:\n"
    "{liste}\n\n"
    "Die mit ⭐ markierten fuenf sind der Vorschlag. Nehmt ihr diese? Ihr "
    "koennt mir auch eure eigenen fuenf Begriffe schicken - getippt oder "
    "als Sprachnachricht."
)
#: "Passt, aber anders" speichert und fragt dann gezielt -- deterministisch,
#: kein Modellaufruf (Zusage 2). Der erste Halbsatz ist die Quittung, der
#: zweite die Frage: eine offene Aufforderung ("sagt mir, was anders sein
#: soll") bekam im Probelauf ein Schulterzucken, die drei Beispiele nicht.
#: Seit 02.10.2026 (Birk, Padua) auch der Text von "Nein, nochmal aendern":
#: der Vorschlag wird VORLAEUFIG gespeichert.
_TEXT_ANDERS = "Vorerst gespeichert. Was soll anders sein?"
#: "Eigene Idee": nichts gespeichert, der naechste Gruppenbeitrag ist der
#: Vorschlag.
_TEXT_EIGENE = "Erzaehlt - ich baue es ein."
#: Nach einem "Gefaellt uns, weiter": bestaetigen, dann die eine Frage, die
#: den Zwischenraum offenhaelt, bevor der Phasenknopf kommt.
#: Karte t_c5d68218 (06.10.2026): eine Bestaetigungsfrage statt der
#: Aufforderung, noch etwas hinzuzufuegen -- der optionale, modellgestuetzte
#: Zusatz (Vorschlag/Rueckfrage) kommt, wenn ueberhaupt, als eigene
#: Nachricht danach (``nachspeichern.starte``), nie an dieser Stelle erzwungen.
_TEXT_NACH_SPEICHERN_FRAGE = "Passt das so fuer euch?"
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
#: Die Notiert-Zeile selbst und die Knopf-Quittung dazu (``basis._speichere``;
#: Karte A1, Aufgabe 11: vorher Inline-Literale).
_TEXT_NOTIERT_ZEILE = "Notiert:\n{feld}: {wert}"
_TEXT_FELD_UEBERNOMMEN = "{feld} uebernommen"

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
#: Der Undo-Knopf (Karte U). Ruhig: kein Emoji, ein Wort, letzte Zeile der
#: Tastatur -- mobil gilt ein Hauptknopf je Bildschirm, und Undo ist
#: Nebenknopf. ASCII-Umschrift wie jede Beschriftung in dieser Datei.
_TEXT_UNDO_KNOPF = "Rueckgaengig"
#: Was zurueckgenommen wurde -- dieselben Zeilen wie in der Meldung
#: (erkenner.undo_zeilen), keine zweite Formulierung.
_TEXT_UNDO_ERLEDIGT = "Rueckgaengig gemacht:\n{zeilen}"
#: Ein betroffenes Feld hat sich seit dem Lauf erneut geaendert: NICHTS wird
#: angefasst, und die Gruppe erfaehrt, wo sie stattdessen hingehen kann.
_TEXT_UNDO_GEAENDERT = "Seitdem geaendert -- bitte im Arbeitsstand korrigieren."
#: ``repo.nimm_erkenner_lauf_zurueck`` hat eine Ausnahme geworfen (Review-Fix
#: Aufgabe 6, z.B. "database is locked" beim Stempel-UPDATE -- vier Bots und
#: das Web teilen dieselbe Datei). Die Transaktion ist intern vollstaendig
#: zurueckgerollt (``except BaseException: conn.rollback(); raise`` in
#: ``repo.py``), nichts wurde zurueckgenommen -- und die Gruppe soll das
#: hoeren, statt gegen eine stumme Tastatur zu tippen.
_TEXT_UNDO_FEHLER = (
    "Das konnte ich nicht zuruecknehmen -- bitte im Arbeitsstand korrigieren."
)
#: Die kurzen Zeilen fuer answerCallbackQuery.
_ANTWORT_UNDO = "Zurueckgenommen."
_ANTWORT_UNDO_GEAENDERT = "Seitdem geaendert."
#: Die Journalzeile der Ruecknahme -- das Journal wird nur angehaengt, die
#: Zeilen des Laufs bleiben stehen (AGENTS.md).
_JOURNAL_UNDO = "Zurueckgenommen: {zeilen}"
#: Der Redo-Knopf (Befund 1a, Padua Phase-2-Ende) -- der Spiegel der
#: Undo-Konstanten direkt darueber, dieselbe Form und dieselben drei
#: Ausgaenge (erledigt, seitdem geaendert, Fehler).
_TEXT_REDO_KNOPF = "Wiederherstellen"
_TEXT_REDO_ERLEDIGT = "Wiederhergestellt:\n{zeilen}"
_TEXT_REDO_GEAENDERT = "Seitdem geaendert -- bitte im Arbeitsstand korrigieren."
_TEXT_REDO_FEHLER = (
    "Das konnte ich nicht wiederherstellen -- bitte im Arbeitsstand korrigieren."
)
_ANTWORT_REDO = "Wiederhergestellt."
_ANTWORT_REDO_GEAENDERT = "Seitdem geaendert."
_JOURNAL_REDO = "Wiederhergestellt: {zeilen}"
#: Die Knopfbeschriftungen heissen seit 05.09.2026 "Interview", nicht
#: "Aufnahme" (Birk, Live-Lauf Gruppe 3): "Aufnahme klingt, als liefe ein
#: Mikrofon -- es sind Sprachnachrichten." Der Modus, die Klassen und die
#: Tabellen heissen intern weiter aufnahme; geaendert hat sich, was die
#: Gruppe liest.
_TEXT_AUFNAHME_STARTEN = "Interview starten"
_TEXT_AUFNAHME_BEENDEN = "Interview beenden"
#: Karte t_1493c40d (06.10.2026, Birk): ab Phase 4 sind die Interviews
#: gelaufen -- "Interview starten" wuerde wortwoertlich DAS eine Interview
#: suggerieren, das es dort nicht mehr gibt. Der Knopf selbst bleibt sichtbar
#: (``knoepfe._aufnahme_anbieten``, nachtraegliches Interview ist ein
#: normaler Vorgang), nur sein Text in der Begruessungsleiste
#: (``knoepfe.biete_einstieg``) aendert sich ab Phase 4.
_TEXT_WEITERE_AUFNAHME_KNOPF = "Weitere Aufnahme"
#: Die zwei Knoepfe unter einem Teil-Transkript (05.09.2026).
_TEXT_TEIL_WEITER_KNOPF = "Interview geht weiter"
_TEXT_TEIL_FERTIG_KNOPF = "Interview ist fertig"
#: Was "Interview geht weiter" tut: eine Zeile, sonst nichts.
_TEXT_TEIL_WEITER = "Gut, ich hoere weiter zu."
#: Der seltene Fall, dass die Aufnahme schon aus ist, wenn der Knopf kommt.
_TEXT_TEIL_SCHON_AUS = "Die Aufnahme laeuft nicht mehr."

#: Die vier Beschriftungen fuer die lange Sprachnachricht ohne Interviewmodus
#: (06.09.2026). Bewusst als Aussagen der Gruppe formuliert, nicht als
#: Ja/Nein: die Gruppe steht im Raum und liest im Vorbeigehen.
_TEXT_OHNE_KNOPF_JA_KNOPF = "Ja, als Interview"
_TEXT_OHNE_KNOPF_NEIN_KNOPF = "Nein, war ein Beitrag"
_TEXT_OHNE_KNOPF_FERTIG_KNOPF = "Fertig, auswerten"
_TEXT_OHNE_KNOPF_WEITER_KNOPF = "Es kommt noch was"
#: \"Es kommt noch was\": der Modus bleibt an, der Kopf offen -- jede weitere
#: Sprachnachricht laeuft als Teil hinein.
_TEXT_OHNE_KNOPF_WEITER = "Gut, ich hoere weiter zu."
#: Die Aufnahme, um die es ging, ist inzwischen weg (geloescht, in ein
#: anderes Interview gezogen). Der Knopf bleibt trotzdem beantwortet.
_TEXT_OHNE_KNOPF_UNBEKANNT = "Diese Aufnahme kenne ich nicht mehr."

#: Der eine Web-Knopf nach einem Interview (Phase 3 Web-UX, 02.10.2026).
_TEXT_INTERVIEWS_FERTIG_KNOPF = "Interviews fertig"
#: Gedrueckt, aber noch mindestens ein Interview ohne Verdichtung offen --
#: der Wunsch wird gemerkt (``arbeitsstand.interviews_fertig_wunsch_seit``)
#: und schliesst automatisch nach der letzten Verdichtung weiter.
_TEXT_INTERVIEWS_NOCH_OFFEN = (
    "{anzahl} Interview(s) werden noch ausgewertet - es geht automatisch "
    "weiter, sobald sie fertig sind."
)
#: Steht unter der Abschlussnachricht, wenn ``schliesse_interviews_ab`` einen
#: Phasenwechsel ausgeloest hat: die Verdichtungen selbst stehen nicht mehr
#: im Chat (Phase 3 Web-UX), sondern im Tab Arbeitsstand der Gruppenseite.
_TEXT_ARBEITSSTAND_HINWEIS = "Die Auswertung aller Interviews findet ihr im Tab Arbeitsstand."

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
#: Das Angebot beim Uebergang in Phase 4 (Modellwahl-Karte, 02.10.2026):
#: dieselben beiden Knoepfe (ART_SZENE_USA, biete_szene_usa) wie bisher vor
#: der ersten Szene -- die Frage wandert zeitlich nach vorn, die Spalte
#: (gruppe.szene_usa_bestaetigt_am) bleibt dieselbe, also zaehlt eine
#: Antwort hier auch fuer die Szene (keine zweite Frage in Phase 6).
#: Benennt ausdruecklich, was NICHT in die USA geht (Audio, ganze Interviews,
#: Chatnamen -- Interviews bleiben in der Schweiz) und was abgeleitet schon
#: dort landet (woertliche Interviewzitate, sobald Phase 5 sie verwendet).
_TEXT_ANGEBOT_MODELLWAHL = (
    "Bevor es weitergeht, eine Entscheidung fuer euch.\n\n"
    "Bis jetzt lief alles in der Schweiz: eure Aufnahmen und Interviews "
    "bleiben das auch -- unbedingt.\n\n"
    "Fuer die Arbeit ab jetzt (das Gespraech mit mir, euer Arbeitsstand, "
    "eure Festlegungen, das Brainstorming-Protokoll und die Figuren) gibt "
    "es ein besseres Modell -- von Anthropic, in den USA. Wenn ihr es "
    "nehmt, geht das dafuer an einen Server dort; ab Phase 5 zaehlen dazu "
    "auch woertliche Zitate aus euren Interviews, wenn ihr sie fuer Szenen "
    "verwendet. Keine Audioaufnahmen, keine vollstaendigen Interviews, "
    "keine Namen aus diesem Chat.\n\n"
    "Wollt ihr das? Bei nein bleibt alles in der Schweiz -- das geht auch."
)
#: Die drei Knoepfe: fest benannt, Sprachnamen in ihrer eigenen Sprache --
#: nicht uebersetzt, wer Italienisch spricht, sucht "Italiano".
STT_KNOEPFE = (("auto", "Auto"), ("en", "English"), ("it", "Italiano"))
_TEXT_STT_SPRACHE_FRAGE = (
    "In welcher Sprache fuehrt ihr eure Interviews? Mit \"Auto\" hoere ich "
    "selbst heraus, welche es ist."
)
_TEXT_STT_SPRACHE_GESETZT = "Interviewsprache ab jetzt: {sprache}."
_TEXT_STT_SPRACHE_AUTO = "automatisch (ich erkenne sie selbst)"
_TEXT_STT_SPRACHE_KURZ = "Sprache gesetzt"
_JOURNAL_STT_SPRACHE = "Interviewsprache fuer Whisper: {sprache}"

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
#: Dasselbe in Phase 4 mit Prosa-Entwurf (Padua, Karte t_b19d37ac): ohne
#: Doppelpunkt, weil keine Szenenvorstellung mehr folgt.
_TEXT_FOLGE_GESPEICHERT_RAHMEN = "Notiert, {anzahl} Szenen."
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
TEXT_NEIN_AENDERN_KNOPF = "Nein, aendern"
TEXT_PASST_KNOPF = "Passt"
TEXT_NEU_KNOPF = "Neu schreiben"
TEXT_NAECHSTE_KNOPF = "Naechste Szene"
#: "Kuerzer" unter einem Szenentext und unter der Kurzgeschichte
#: (30.09.2026, Massnahme C4). Der Prozentwert steht in
#: ``kuerzung.PROZENT`` und wird am Aufrufort eingesetzt -- zwei Zahlen waeren
#: zwei Wahrheiten.
ART_SZENE_KUERZEN = "szene_kuerzen"
TEXT_KUERZEN_KNOPF = "Kuerzer ({prozent} %)"
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
#: Der Durchlauf ist der Ort, an dem die Gruppe das Stueck als Ganzes
#: ansieht -- und damit der Ort fuer die Frage, wer wie viel spricht.
TEXT_SPRECHANTEILE_KNOPF = "Wer spricht wie viel"
#: Der Knopf unter einer angesehenen Szene, wenn es fruehere Fassungen gibt.
TEXT_FASSUNGEN_KNOPF = "Fruehere Fassungen"
_TEXT_FASSUNGEN_KOPF = "Fruehere Fassungen von Szene {nummer}:"
#: Die Kopfzeile je Fassung. ``anders`` ist die Zeile "Anders gemacht:" des
#: Laufs, der sie geschrieben hat -- der Satz, an dem die Gruppe sie
#: wiedererkennt.
_TEXT_FASSUNG_KOPF = "--- Fassung {nummer} ({zeit}){anders} ---"
_TEXT_KEINE_FASSUNGEN = "Von Szene {nummer} gibt es nur die eine Fassung."
_TEXT_TEXTBUCH_BESCHREIBUNG = "Euer Textbuch - alle Szenen in einer Datei."
#: Die Probenansicht (06.09.2026) steht als Zeile NEBEN dem Datei-Knopf, nicht
#: an seiner Stelle: die Datei nimmt man mit, die Seite liest man in der Probe
#: (Rollenfilter, Schriftgroesse, Ausdruck). Als Text und nicht als Knopf, weil
#: eine Inline-Tastatur hier ``callback_data`` traegt und keinen Link -- und
#: weil ein Link, den man kopieren kann, im Probenraum weitergereicht wird.
_TEXT_PROBENANSICHT = (
    "\n\nZum Lesen in der Probe (Rollen hervorheben, groesser stellen, "
    "ausdrucken): {url}"
)
_TEXT_TEXTBUCH_FEHLER = (
    "Die Datei ist nicht durchgekommen. Ich kann euch die Szenen auch einzeln "
    "schicken."
)
_TEXT_SZENE_OHNE_TEXT = "Szene {nummer} ist noch nicht geschrieben."

#: Phase 5 · Geschichte.
_TEXT_GESCHICHTE_GESPEICHERT = "Notiert, eure Geschichte in {anzahl} Szenen:"
#: Nach der Wahl EINER Richtung (06.09.2026, Birk 11:42) -- die Szenenfolge
#: kommt danach als eigener Vorschlag, nicht in derselben Nachricht.
_TEXT_RICHTUNG_GESPEICHERT = "Notiert, eure Geschichte:"
_TEXT_GESCHICHTE_LEER = (
    "Aus dem Vorschlag konnte ich keine Geschichte lesen. Erzaehlt sie mir "
    "einfach."
)
#: Die angetippte Zeile war eine FORMWAHL, keine Handlung (06.09.2026, B1/B2
#: der Phase-4-Analyse). Die Wahl ist festgehalten, die Handlung fehlt noch --
#: und genau das muss dastehen: bis hierher hat der Bot in so einem Fall
#: "Notiert, eure Geschichte:" geantwortet und die Menuezeile darunter
#: gezeigt, und niemandem fiel auf, dass die Handlung nirgends stand.
_TEXT_NUR_FORMWAHL = (
    "Die Form je Szene habe ich festgehalten. Die Handlung fehlt mir noch: "
    "Was passiert, und wie geht es aus?"
)

#: Phase 6 · Schaerfung.
#: Phase 7 - Dramaturgie-Pruefung.
TEXT_DRAMATURGIE_KNOPF = "Dramaturgie pruefen"
_TEXT_DRAMATURGIE_LAEUFT = (
    "Ich sehe mir jetzt jede Szene einzeln an - Wendepunkt, Anschluss, "
    "Stimmen, offene Faeden. Das dauert ein paar Minuten."
)
_TEXT_DRAMATURGIE_LASSEN_KNOPF = "Lassen"
_TEXT_DRAMATURGIE_LASSEN = "Gut, das bleibt so."
_TEXT_DRAMATURGIE_UNBEKANNT = "Diesen Befund finde ich nicht mehr."
_TEXT_DRAMATURGIE_UEBERHOLT = (
    "Sobald die Szene neu steht, ist dieser Befund ueberholt. Wenn ihr wollt, "
    "sehe ich danach noch einmal nach."
)

TEXT_SCHAERFUNG_RUNDE_KNOPF = "Noch eine Runde"
#: Die zwei Knoepfe unter der automatischen Zuordnung beim Eintritt in Phase
#: 5 (``ART_SCHAERFUNG_SORTIEREN``/``ART_SCHAERFUNG_CHAT``). Deutsch ist hier
#: nur die Vorgabe (Dortmund hat ``diskussion_aktiv`` nie an, siehe oben) --
#: Padua spricht Englisch, siehe ``sprachen/en/texte.toml``.
TEXT_SCHAERFUNG_SORTIEREN_KNOPF = "\U0001f5c2 Stellen sortieren"
TEXT_SCHAERFUNG_CHAT_KNOPF = "\U0001f4ac Erst ueber die Interviews reden"
_TEXT_SCHAERFUNG_CHAT_NOTIERT = "Gut, ich fasse die Interviews kurz zusammen."
_TEXT_SCHAERFUNG_SORTIEREN_NOTIERT = "Gut, sortiert im CoThinker weiter."
#: Die beiden Sammelknoepfe unter dem Schaerfungs-Menue (06.09.2026).
_TEXT_SCHAERFUNG_ALLE_KNOPF = "Diese uebernehmen"
_TEXT_SCHAERFUNG_KEINE_KNOPF = "Keine davon"
#: "Mehr zeigen" (07.10.2026) -- blaettert dieselbe Szene/Figur weiter.
_TEXT_SCHAERFUNG_MEHR_KNOPF = "Mehr zeigen"
#: Die Seitenangabe in der Ueberschrift, nur wenn es mehr Stellen gibt als
#: auf einer Seite passen (sonst zeichengleich wie vor dem Umbau).
_TEXT_SCHAERFUNG_SEITE = " ({von}–{bis} von {gesamt})"
_TEXT_SCHAERFUNG_STELLE_UNBEKANNT = "Diese Stelle finde ich nicht mehr."
_TEXT_SCHAERFUNG_STELLE_UEBERNOMMEN = "Uebernommen: {ziel}."
_TEXT_SCHAERFUNG_VERWORFEN = "Gut, die lasse ich weg."
_TEXT_SCHAERFUNG_LAEUFT = (
    "Ich lege eure Geschichte neben die Interviews und suche, was dazu passt."
)
_TEXT_SCHAERFUNG_UEBERNOMMEN = "Uebernommen: {anzahl} Stellen."
_TEXT_DONE_KARTEN = "Uebernommen: {anzahl} Stellen. Eure Auswahl steht -- als Naechstes baut ihr daraus Szene fuer Szene eine Karte."
_TEXT_DONE_UEBERSICHT = "Uebernommen: {anzahl} Stellen. Jetzt fasse ich eure Geschichte als Uebersicht zusammen -- danach geht es Szene fuer Szene."
_TEXT_DONE_SZENE_DA = "Uebernommen: {anzahl} Stellen. Szene {nummer} steht schon im Skript-Tab -- lest sie und sagt, ob sie passt."
_TEXT_DONE_SZENE_NEU = "Uebernommen: {anzahl} Stellen. Ich schreibe jetzt Szene {nummer}."
_TEXT_SCHAERFUNG_NICHTS = "Dazu ist gerade nichts offen."
_TEXT_SCHAERFUNG_DURCH = (
    "Das war alles, was ich zuordnen konnte. Wollt ihr noch eine Runde, oder "
    "gehen wir an die Szenentexte?"
)


# --- Phase 2 · Fragen einzeln durchgehen, Leitfaden -----------------------
#
# Padua, 02.10.2026: der Vorschlag traegt die Sensibilitaetspruefung im selben
# Modellzug (keine Vorgabe mehr, wie viele Fragen es je Begriff sein muessen
# -- "No hard count anywhere", die Gruppe nimmt, was passt), danach einen
# Ueberblick mit einer Richtungsfrage, danach die Fragen einzeln.

#: Wie viele Fragen der Bot je Begriff VORSCHLAEGT -- eine Vorgabe fuer den
#: Vorschlag, keine fuer die Auswahl: die Gruppe nimmt an, verwirft oder
#: schaerft jede Frage einzeln, in beliebiger Zahl.
FRAGEN_JE_BEGRIFF = 5

#: "Ja, einzeln durchgehen" unter dem Ueberblick.
_TEXT_FRAGEN_EINZELN_KNOPF = "Ja, einzeln durchgehen"
#: "Andere Richtung" -- bis 02.10.2026 hiess der Knopf "Andere Fragen" und
#: loeste sofort einen neuen Vorschlag aus; jetzt fragt der Bot zuerst nach
#: der Richtung (``_TEXT_FRAGEN_RICHTUNG_GEFRAGT``).
_TEXT_FRAGEN_ANDERE_KNOPF = "Andere Richtung"
#: "Eigene Idee" in der stillgelegten Fragenauswahl -- nur noch als Text fuer
#: einen alten, schon verschickten Knopf (``_wirkung_fragen_eigene``).
_TEXT_FRAGEN_EIGENE_KNOPF = "Eigene Idee"
#: Die deterministische Richtungsfrage unter dem Ueberblick (02.10.2026,
#: Birk): ein Satz, zwei Knoepfe -- kein Modellaufruf, um sie zu stellen.
_TEXT_FRAGEN_RICHTUNG_FRAGE = (
    "Gehen die Fragen in die richtige Richtung? Wollen wir sie einzeln "
    "durchgehen?"
)
#: Nach "Andere Richtung": die naechste freie Nachricht ist die Antwort
#: darauf (``fragen.nimm_offene_frage_text``).
_TEXT_FRAGEN_RICHTUNG_GEFRAGT = "In welche Richtung soll es gehen?"
#: Die Antwort auf einen Knopf aus einer stillgelegten Nachricht (altes
#: ``ART_FRAGE_WAHL``/``ART_FRAGEN_UEBERNEHMEN``) -- der Weg wird gesagt,
#: statt dass der Druck ins Leere laeuft.
_TEXT_FRAGEN_WAHL = (
    "Diese Auswahl laeuft nicht mehr ueber Nummern -- antwortet auf die "
    "Frage, die gerade im Chat steht."
)
_TEXT_FRAGEN_EIGENE = (
    "Schreibt eure Frage oder Fragen - ich nehme sie mit in die Auswahl."
)
#: Ein Druck auf eine ueberholte Frage (eine neue Auswahlrunde hat
#: ``fragen_auswahl``/``fragen_entschieden`` schon ersetzt).
_TEXT_FRAGEN_KEINE_AUSWAHL = "Diese Auswahl kenne ich nicht mehr."
#: Keine einzige Frage angenommen -- der Bot sagt es und schlaegt neue vor,
#: statt mit einer leeren Frageliste weiterzumachen.
_TEXT_FRAGEN_KEINE_ANGENOMMEN = (
    "Keine der Fragen ist angenommen - ich schlage neue vor."
)
#: Nach der letzten Entscheidung: die angenommenen Fragen stehen.
_TEXT_FRAGEN_ABGESCHLOSSEN = "Notiert, eure {anzahl} Fragen:"
_JOURNAL_FRAGEN = "Fragen: {wert}"
_TEXT_FRAGEN_QUITTUNG = "Fragen uebernommen"

#: Das Angebot nach der letzten Entscheidung, wenn mindestens eine
#: ANGENOMMENE Frage eine weiche Fassung hat (02.10.2026, Birk: "Mach die
#: softere Formulierung nicht direkt bei der Frage, sondern als Angebot am
#: Ende von allen Fragen."). Listet nur die betroffenen Fragen mit ihrer
#: weichen Fassung -- die restlichen angenommenen Fragen stehen schon in der
#: Abschlussnachricht (``_TEXT_FRAGEN_ABGESCHLOSSEN``) und werden hier nicht
#: wiederholt.
_TEXT_FRAGEN_WEICH_ANGEBOT = (
    "Diese Fragen sind sensibel formuliert. Weicher gefragt:"
)
_TEXT_FRAGEN_WEICH_ZEILE = "{nummer}. {frage}\n   Weicher: {weich}"
_TEXT_FRAGEN_WEICH_UEBERNEHMEN_KNOPF = "Weiche Fassungen übernehmen"
_TEXT_FRAGEN_WEICH_LASSEN_KNOPF = "Wie sie sind lassen"
_TEXT_FRAGEN_WEICH_UEBERNOMMEN = "Weiche Fassungen übernommen"
_TEXT_FRAGEN_WEICH_BEHALTEN = "Original beibehalten"

#: Die Umformulier-Runde (Testkarte t_266e7485, 06.10.2026, nur Padua): hidden
#: Befehl ``/umformulieren`` fragt nach der EINEN Anweisung, die gleich alle
#: behaltenen Fragen umformuliert.
_TEXT_UMFORMULIEREN_WUNSCH_FRAGE = (
    "Wie sollen die Fragen umformuliert werden? Schreibt eine Anweisung, "
    "z.B. „konkreter machen“ oder „leichter zu beantworten“."
)
#: Die Vorschau alt->neu, EINE Nachricht fuer alle geaenderten Fragen.
_TEXT_UMFORMULIEREN_KOPF = "Vorschlag fuer die Umformulierung:"
_TEXT_UMFORMULIEREN_ZEILE = "{nummer}. {alt}\n   → {neu}"
#: Erklaert den Chatweg (accept-all/per-number) unter der Vorschau -- die
#: beiden Knoepfe decken nur "alle"/"keine" ab, einzelne Nummern laufen ueber
#: diese freie Nachricht.
_TEXT_UMFORMULIEREN_HINWEIS = (
    "Antwortet mit den Nummern, die ihr übernehmen wollt (z. B. „1, 3“), "
    "oder „alle“ - sonst bleiben die alten Formulierungen stehen."
)
_TEXT_UMFORMULIEREN_ALLE_KNOPF = "Alle übernehmen"
_TEXT_UMFORMULIEREN_KEINE_KNOPF = "Alte behalten"
#: Kein Vorschlag weicht vom Original ab -- es gibt nichts anzunehmen.
_TEXT_UMFORMULIEREN_UNVERAENDERT = (
    "Das Modell hat an keiner Frage etwas geändert."
)
_TEXT_UMFORMULIEREN_UEBERNOMMEN = "Aktualisiert, eure Fragen:"
#: Das Angebot direkt nach "Fragen uebernommen" (Review-Fix t_b371c0f1,
#: 06.10.2026): macht den versteckten Befehl ``/umformulieren`` fuer die
#: Gruppe erreichbar -- ohne diesen Knopf gab es keinen Ausloeser.
_TEXT_UMFORMULIEREN_ANBIETEN = "Wollt ihr die Formulierung der Fragen noch aendern?"
_TEXT_UMFORMULIEREN_ANBIETEN_KNOPF = "Fragen umformulieren"

#: Der Kopf einer einzelnen vorgelegten Frage (02.10.2026): "Frage 3/15 ·
#: Heimat". Ohne erkennbaren Begriff (Zeile ohne "Begriff: ") faellt die
#: Kurzform ohne Mittelpunkt zurueck.
_TEXT_FRAGE_KOPF = "Frage {nummer}/{gesamt} · {begriff}"
_TEXT_FRAGE_KOPF_OHNE_BEGRIFF = "Frage {nummer}/{gesamt}"
#: Steht darunter, wenn die Frage sensibel formuliert ist -- die weiche
#: Fassung samt einem kurzen Hinweis, dass sie sensibel ist.
_TEXT_FRAGE_WEICH_HINWEIS = (
    "Weichere Formulierung, weil das Thema sensibel ist:\n{weich}"
)
_TEXT_FRAGE_ANNEHMEN_KNOPF = "Annehmen"
_TEXT_FRAGE_VERWERFEN_KNOPF = "Verwerfen"
_TEXT_FRAGE_SCHAERFEN_KNOPF = "Schaerfen"
#: Nach "Schaerfen": die naechste freie Nachricht ist der Aenderungswunsch.
#: Dieselbe Frage beantwortet auch eine freie Nachricht OHNE Knopfdruck,
#: solange diese Frage die aktuelle ist (``fragen.nimm_offene_frage_text``).
_TEXT_FRAGE_WAS_AENDERN = "Was wollt ihr aendern?"
_TEXT_FRAGE_GESCHAERFT = "Frage ueberarbeitet"
#: Die sichtbare Quittung (Web-Toast/Telegram answerCallbackQuery) nach
#: Annehmen/Verwerfen -- Fund 02.10.2026, Birk: statt des generischen
#: "Notiert" (``_TEXT_FRAGE_ENTSCHIEDEN``, unveraendert als Fallback stehen
#: gelassen, falls ein aelterer Aufrufer noch danach sucht) soll dort die
#: tatsaechlich getroffene Entscheidung stehen.
_TEXT_FRAGE_ANGENOMMEN = "✓ Angenommen"
_TEXT_FRAGE_VERWORFEN = "✗ Verworfen"
_TEXT_FRAGE_ENTSCHIEDEN = "Notiert"
#: Nach einer direkten Uebergabe aus der CoThinker-Klickliste (Stift ✎,
#: Padua, Karte t_269062e2, 06.10.2026): Annehmen/Verwerfen springt dort
#: NICHT automatisch zur naechsten offenen Frage weiter (die Sortierung
#: bleibt offen) -- diese Zeile verweist stattdessen zurueck.
_TEXT_FRAGE_ZURUECK_ZUR_LISTE = "Zurück zur Liste: CoThinker-Tab"

# --- Eigene Fragen vs. KI (Padua Phase 1+2 Karte, Aufgabe 13, 03.10.2026) --
#
# KORREKTUR 10:25 (Birk, KORREKTUR-PHASE2-KEIN-KNOPF.md): KEIN "Fertig"-
# Knopf. ``VORSCHLAG EIGENE FRAGEN:`` ist die vollstaendige, kumulative
# Liste der eigenen Fragen -- der Code speichert sie nach jedem Zug
# (``knoepfe.fragen.uebernimm_eigene``) und startet die Gegenueberstellung
# mit den KI-Fragen (``knoepfe.fragen.versuche_gegenueberstellung``), sobald
# die Gruppe sagt, dass sie fertig ist.

#: Steht neben dem Block kein Antworttext, nur dieser Verweis -- der Stand je
#: Begriff steht im CoThinker, ohne Soll-Zahl (Birk, 05.10.2026; vorher hier
#: "Noch offen: Begriff (x/3)" nach jeder Bestaetigung).
_TEXT_FRAGEN_EIGENE_IM_COTHINKER = "Notiert. Eure Fragen je Begriff stehen im CoThinker."
#: Der Knopf, mit dem die Gruppe KI-Fragen anfordert (Padua Phase 2, Birk
#: 05.10.2026: "suggest questions") -- und die Rueckfrage zum Selberdenken,
#: die er zuerst ausloest. Ohne eine einzige eigene Frage die deutlichere
#: Fassung (Birks Regel: eigene Fragen zuerst).
_TEXT_FRAGEN_VORSCHLAGEN_KNOPF = "Fragen vorschlagen"
_TEXT_FRAGEN_SELBST_RUECKFRAGE = (
    "Bevor ich welche vorschlage: Sind alle Fragen, die ihr euch selbst "
    "ausgedacht habt, schon drin? Habt ihr noch etwas im Kopf – auch nur "
    "einen halben Gedanken?"
)
_TEXT_FRAGEN_SELBST_RUECKFRAGE_LEER = (
    "Ihr habt noch keine eigene Frage. Probiert erst eine? Auch eine grobe "
    "ist super."
)
_TEXT_FRAGEN_NOCH_EIGENE_KNOPF = "Wir haben noch welche"
_TEXT_FRAGEN_JA_VORSCHLAGEN_KNOPF = "Ja, schlag welche vor"
_TEXT_FRAGEN_NOCH_EIGENE = "Super – schreibt oder sprecht sie einfach, ich nehme sie auf."
#: Gespeichert, aber die KI-Fragen sind noch nicht da -- der Reveal kommt
#: automatisch, sobald der Hintergrundlauf fertig ist (``fragen_ki.starte``).
_TEXT_FRAGEN_EIGENE_WARTET_AUF_KI = (
    "Eure Fragen sind gespeichert - ich warte noch auf die KI-Fragen im "
    "Hintergrund."
)
#: Unter ``workshop.fragen_eigene_min`` eigenen Fragen (Padua: 5, Birk
#: 05.10.2026 14:05): ein alter "Suggest questions"-Knopf oder "eigene
#: Fragen fertig" startet nichts.
_TEXT_FRAGEN_EIGENE_ZU_WENIG = "Sammelt erst mindestens fünf eigene Fragen."
#: Die EINE kurze Ueberleitungszeile beim automatischen Start der
#: Gegenueberstellung (KORREKTUR-PHASE2-KEIN-KNOPF.md).
_TEXT_GEGENUEBERSTELLUNG_BEREIT = (
    "Eure Fragen und die der KI stehen sich jetzt gegenueber:"
)
#: Herkunfts-Kennzeichnung einer Frage beim Durchgehen (Aufgabe 13) -- reiner
#: Text, keine HTML/``data-*``-Attribute (``sichere_html``s feste Allowlist
#: kennt beides nicht).
_TEXT_HERKUNFT_EIGEN = " (eure)"
_TEXT_HERKUNFT_KI = " (KI)"
#: Padua 05.10.2026: die Fragen auf einmal sortieren statt nur Karte fuer
#: Karte -- Hinweis auf die Sortierliste im CoThinker (beim Start des
#: Durchgehens) und der Zaehler unter "show all" (``fragen.uebersicht_text``).
_TEXT_FRAGEN_COTHINKER_HINWEIS = (
    "Ihr könnt alle Fragen auch im CoThinker auf einmal sortieren: "
    "✓ behalten · ✗ weg · ✎ umformulieren, dann „Fertig sortiert“."
)
_TEXT_AUSWAHL_ZAEHLER = "{ja} behalten · {nein} weg · {schaerfen} umformulieren · {offen} offen"
#: Der Satz, den das Padua-Profil-Prompt
#: (``workshop/padua-2026/prompts/phasen/2.md``) das Modell woertlich sagen
#: laesst, wenn die Gruppe mit ihren eigenen Fragen fertig ist und zur
#: Gegenueberstellung will -- KEIN Marker (Marker werden nicht
#: uebersetzt, siehe ``vorschlag.py``), ein gewoehnlicher Satz im
#: Fliesstext, deshalb braucht er eine EN-Fassung
#: (``sprachen/en/texte.toml``, geprueft von ``_fruehzeitig_fertig``
#: case-/whitespace-unabhaengig).
_SATZ_EIGENE_FRAGEN_FRUEHER_FERTIG = "Eigene Fragen fertig."

# --- Eigene Fragen vs. KI: die Auswertung (Aufgabe 14, 03.10.2026) ---------
#
# Die zusaetzliche Zeile unter der Abschlussnachricht von Phase 2
# (``_TEXT_FRAGEN_ABGESCHLOSSEN``) -- NUR wenn der A/B-Vergleich fuer diese
# Runde tatsaechlich lief (``fragen.fragen_herkunft_final`` traegt
# mindestens einen nicht-leeren Eintrag). Ohne das bleibt der klassische
# Abschlusstext byte-identisch zu vor Aufgabe 14
# (``test_klassischer_abschlusstext_bleibt_byte_identisch``).
_TEXT_FRAGEN_AUSWERTUNG = "Ihr habt {ki} KI-Fragen und {eigen} eigene behalten."
#: Eine Zeile je Begriff mit eigenem Begriffsnamen, nur eingesetzt, wenn
#: ``fragen_auswertung.aus_daten`` mindestens einen Begriff erkannt hat.
_TEXT_FRAGEN_AUSWERTUNG_ZEILE = "{begriff}: {eigen} eigene, {ki} KI"

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

#: Wie viele Optionen ein Menue hoechstens traegt. Vier plus "Anders" ist auf
#: dem Telefon noch eine Leiste; mehr ist eine Liste.
MAX_AUSWAHL = 4

#: Die Hoechstlaenge einer Menue-Beschriftung (Birk, 06.09.2026, 11:05):
#: "1 · <Titel>". Laengeres schneidet Telegram auf dem Telefon ab, und ein
#: abgeschnittener Knopf ist keine Auswahl mehr.
MENUE_KNOPF_LAENGE = 30
#: Der Ausweg unter jedem Menue -- speichert nichts, macht den Weg frei.
_TEXT_MENUE_ANDERS_KNOPF = _TEXT_EIGENE_KNOPF

#: **Ersatzlos gestrichen am 06.09.2026** (Birk, 11:00): frueher trug die
#: Grundleiste unter einer Optionenliste den ERSTEN Vorschlag als
#: speicherbaren Wert -- "Gefaellt uns, weiter" nahm also still Option 1,
#: auch wenn die Gruppe Option 3 meinte. Bei mehreren Optionen gibt es jetzt
#: keinen Sammelknopf mehr, nur die nummerierten Optionen selbst.
_ERSTER_ALS_WERT: dict[str, str] = {}


#: Die Arbeitszeilen, die SOFORT rausgehen, wenn ein laengerer Auftragszug
#: startet (06.09.2026, 10:10, Birk). Sie werden geloescht, sobald die
#: Antwort da ist (``ablauf.arbeitet_sichtbar``) -- eine Arbeitsmeldung, die
#: stehen bleibt, liest sich wie eine haengende Aufgabe.
TEXT_ARBEIT_EROEFFNUNG = "✍️ Jetzt die Einleitung fuers Interview: wie ihr anfangt und aufhoert …"
#: Journalzeile und Knopf-Quittung, wenn Eroeffnung und Abschluss stehen
#: (``fragen._speichere_eroeffnung``).
_JOURNAL_EROEFFNUNG_FESTGELEGT = "Eroeffnung und Abschluss festgelegt"
_TEXT_EROEFFNUNG_QUITTUNG = "Eroeffnung uebernommen"


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


# --- Phase 6 · die Kurzgeschichte (06.09.2026, Birk 11:50) ---------------

#: Der Knopf, aus dem der Prosa-Lauf startet -- und **nur** aus ihm: der
#: Gespraechs-Bot loest keinen Lauf aus (Birk, 12:25).
ART_GESCHICHTE_SCHREIBEN = "geschichte_schreiben"
#: "Passt" / "Anders" / "Neu" unter der fertigen Kurzgeschichte.
ART_GESCHICHTE_PASST = "geschichte_passt"
ART_GESCHICHTE_ANDERS = "geschichte_anders"
ART_GESCHICHTE_NEU = "geschichte_neu"
#: "Kuerzer" unter der ganzen Kurzgeschichte -- dieselbe Beschriftung
#: (``TEXT_KUERZEN_KNOPF``), anderer Weg: ein Prosalauf ueber alle
#: Abschnitte statt ein Szenenlauf.
ART_GESCHICHTE_KUERZEN = "geschichte_kuerzen"

TEXT_GESCHICHTE_SCHREIBEN_KNOPF = "Geschichte schreiben"
_TEXT_GESCHICHTE_PASST_KNOPF = "Passt so"
_TEXT_GESCHICHTE_ANDERS_KNOPF = "Etwas aendern"
_TEXT_GESCHICHTE_NEU_KNOPF = "Ganz neu schreiben"
_TEXT_GESCHICHTE_ANDERS = (
    "Sagt mir, was anders soll - ich nehme es in den naechsten Lauf mit."
)
_TEXT_GESCHICHTE_PASST = "Gut. Dann geht es im Feinschliff Abschnitt fuer Abschnitt weiter."
#: Die Zeile ueber dem Startknopf. Sie sagt, was passiert -- nicht, dass es
#: schon passiert (der Bot kuendigt nichts an, was er nicht tut).
_TEXT_KURZGESCHICHTE_BEREIT = (
    "Ich kann eure Geschichte jetzt am Stueck schreiben - aus Setting, "
    "Figuren und eurer Richtung. Sagt Bescheid, wann."
)


# --- Padua Phasen TEIL 1 (03.10.2026): Stufe A von Phase 5 (Prose Draft) --

#: "Yes, save" / "No, change it again" unter der generierten
#: Geschichts-Uebersicht (``entwurf.py``) -- dieselbe "Rueckspiegelung EINES
#: Wertes" wie bei ``grundleiste``/``speicherleiste``, deshalb dieselben
#: Beschriftungen (``TEXT_WEITER_KNOPF``/``TEXT_ANDERS_KNOPF``) statt
#: near-duplizierter Strings.
ART_UEBERSICHT_PASST = "uebersicht_passt"
ART_UEBERSICHT_ANDERS = "uebersicht_anders"
_TEXT_UEBERSICHT_FIXIERT = "Alles klar -- ich schreibe jetzt die erste Szene."
_TEXT_UEBERSICHT_WIRD_NEU_ERZEUGT = "Gut, ich erzeuge eine neue Uebersicht."

#: Stufe B (Szene fuer Szene): "Yes, save" auf einem Prosa-Entwurf laeuft
#: ueber den bestehenden Knopf ``ART_SZENE_PASST`` (phasengebunden in
#: ``wirkung._wirkung_szene_passt``), deshalb keine eigene ART hier -- nur
#: die beiden Antworttexte. Deutsch bleibt die Konstante (bitgleich), die
#: englische Padua-Fassung steht in ``sprachen/en/texte.toml`` (Karte A1).
_TEXT_NAECHSTE_SZENE_WIRD_GESCHRIEBEN = "Alles klar -- ich schreibe jetzt die naechste Szene."
_TEXT_ALLE_SZENEN_ENTWORFEN = "Alle Szenen haben einen Entwurf. Weiter geht's mit der Ueberarbeitung."


# --- Padua Phasen TEIL 2 (03.10.2026): Pruefen vor jeder Anzeige ----------

#: "Erste Fassung zeigen" unter dem Hinweis nach einem Prueflauf
#: (``szenen.zeige_geprueft_szene``/``zeige_geprueft_geschichte``). ``wert``
#: ist die Szenennummer, ``""`` heisst die ganze Geschichte. Kein
#: Modellaufruf: der Knopf sagt nur, wo die Fassung steht.
ART_ERSTENTWURF = "erstentwurf"
#: Der Hinweis statt des Volltexts (Padua: kein Volltext im Chat).
_TEXT_SZENE_BEREIT = "Szene {nummer} von {gesamt} ist fertig: {titel}."
_TEXT_GESCHICHTE_BEREIT = "Die ganze Geschichte steht ({gesamt} Szenen)."
#: Wo der Text steht: im Web-Kanal der Tab, in Telegram der Link darauf.
_TEXT_SKRIPT_TAB = "Lest sie im Script-Tab."
_TEXT_SKRIPT_LINK = "Lest sie im Script-Tab: {url}"
#: Was nach dem Lesen kommt; ``knopf`` ist die Beschriftung des ersten Knopfs.
_TEXT_SZENE_NAECHSTER_SCHRITT = (
    "Kommt danach hierher zurueck: Tippt auf \"{knopf}\" oder sagt mir, was ich aendern soll.")
_TEXT_ERSTENTWURF_KNOPF = "Erste Fassung zeigen"
_TEXT_ERSTENTWURF = "Die Fassung vor der Pruefung steht im Script-Tab unter \"Erste Fassung\"."
_TEXT_KEIN_ERSTENTWURF = "Dazu gibt es noch keine fruehere Fassung."
#: Hoechstens so viele Zeichen der Zusammenfassung im Hinweis.
HINWEIS_ZUSAMMENFASSUNG_MAX = 300

#: Phase 7 (Stage Version, Task 9): die Sprechweisen aller Figuren in EINER
#: Nachricht, "Yes, save" / "No, change it again" darunter. Kein
#: Modellaufruf in den Handlern -- "No" fragt nur nach; die Antwort im Chat
#: setzt der Erkenner (``sprechweise_setzen``, Task 10).
ART_SPRECHWEISEN_PASST = "sprechweisen_passt"
ART_SPRECHWEISEN_ANDERS = "sprechweisen_anders"
_TEXT_SPRECHWEISEN_KOPF = "So spricht jede Figur:"
_ZEILE_SPRECHWEISE = "- {name}: {sprachstil}"
#: Steht, solange eine Figur noch keine Sprechweise hat (der Lauf ist
#: gescheitert) -- sie laesst sich im Chat setzen.
_TEXT_SPRECHWEISE_OFFEN = "(noch offen -- sagt mir, wie sie spricht)"
_TEXT_SPRECHWEISEN_AENDERN = (
    "Sagt mir, wer anders sprechen soll -- etwa so: \"Mira: kurze Saetze, "
    "viel Slang\""
)

# Internet-Recherche (Karte t_c5117c91, InScribe): ein eigener Materialstrang
# neben dem Interview. Angebot am Anfang von Phase 5 UND auf Anfrage ab Phase
# 4 (befehle.py, /stand), nur mit dem Profilschalter ``recherche`` (Vorgabe
# aus). Drei Schritte, drei Knoepfe: Angebot -> Fragenvorschlag -> Frage
# waehlen -> Lauf im Thread (Zusage 2, wie ueberall hier).
ART_RECHERCHE = "recherche"
ART_RECHERCHE_FRAGE = "recherche_frage"
_TEXT_RECHERCHE_KNOPF = "Recherche"
_TEXT_RECHERCHE_ANBIETEN = "Soll ich dazu im Netz nachschauen?"
_TEXT_RECHERCHE_FRAGEN_LAEUFT = "Ich ueberlege mir drei Forschungsfragen ..."
_TEXT_RECHERCHE_FRAGEN_TEXT = (
    "Welche Frage sollen wir klaeren? Oder schreibt eure eigene, z. B. "
    "\"Recherche: ...\""
)
_TEXT_RECHERCHE_KEINE_FRAGEN = "Mir faellt dazu gerade keine Frage ein."
_TEXT_RECHERCHE_LAEUFT = "Ich schaue im Netz nach (30-60 Sekunden) ..."
_TEXT_RECHERCHE_NICHTS_GEFUNDEN = "Ich habe dazu nichts Verifizierbares gefunden."
_ANTWORT_RECHERCHE_GESTARTET = "Ich schaue nach."


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
#: "Wollt ihr noch etwas hinzufuegen?"). **Rahmen ist seit dem Brainstorming-
#: Umbau (Padua, 02.10.2026) kein Kettenglied mehr**: Phase 4 ist freies
#: Brainstorming ohne feste Reihenfolge, die Figurenanzahl-Frage kommt nicht
#: mehr automatisch aus dem Setting heraus (sie laeuft seitdem ueber den
#: normalen Speicherweg mit ``uebergang=True``). Kernthema und Kernfrage
#: bleiben rueckwaertskompatibel drin -- angeboten werden sie nicht mehr,
#: aber ``/kernthema`` + eine modellgebaute Kernfrage erreichen sie noch.
_KETTE = ("kernthema", "kernfrage")



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


#: Der Sprachstil je Figur (06.09.2026, Birk 12:20). Zwei Arten: das Menue
#: legt der Stil-Lauf hin, der Druck schreibt ``figur.sprachstil`` bzw.
#: ``figur.quelle_aufnahme_id``.
ART_FIGUR_STIL = "figur_stil"
#: "Eigener Stil" -- der Freitextweg unter dem Menue. Speichert nichts; die
#: naechste Nachricht der Gruppe ist der Stil.
ART_FIGUR_STIL_FREI = "figur_stil_frei"
#: "Zufaellig zuordnen" -- alle Figuren ohne Quelle bekommen in EINEM Druck
#: eines der vorhandenen Interviews (06.09.2026, Analyse
#: ``docs/analyse-phase5-chaos-2026-09-06.md`` Abschnitt 1).
#:
#: Bis dahin entstand ``figur.quelle_aufnahme_id`` nur als Nebenprodukt der
#: Stilwahl: ein Modellaufruf JE FIGUR. Gemessen am 06.09.2026: 12 Laeufe,
#: 718 s reine Modellzeit -- und fuenf von 16 Figuren blieben trotzdem ohne
#: Quelle. Die drei Zusagen sind eingehalten: ``callback_data`` traegt nur
#: ``k:<id>`` (``wert`` bleibt leer, es gibt nichts zu parametrisieren),
#: **kein Modellaufruf** (reine DB-Operation), und idempotent -- doppelt
#: ueber ``repo.beanspruche_knopf`` und ueber die Wirkung selbst, die nur
#: Figuren OHNE Quelle anfasst.
ART_FIGUREN_ZUFALL = "figuren_zufall"

_TEXT_FIGUREN_ZUFALL_KNOPF = "Zufaellig zuordnen"
_TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW = (
    "Dafuer brauche ich mindestens ein Interview."
)
_TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN = (
    "Jede Figur hat schon ein Interview. Aendern koennt ihr jede einzeln."
)
_TEXT_FIGUREN_ZUFALL_FERTIG = (
    "Zugeordnet: {figuren} Figuren auf {interviews} Interviews. Aendern "
    "koennt ihr jede einzeln."
)

_TEXT_STIL_FRAGE = "Wie spricht {name}?"
_TEXT_STIL_EIGENER_KNOPF = "Eigener Stil"
_TEXT_STIL_EIGENER = "Erzaehlt, wie sie spricht - ich baue es ein."
_TEXT_STIL_GESPEICHERT = "Notiert, so spricht {name}."


_TEXT_KEIN_INTERVIEW = "Es gibt noch kein Interview, aus dem sie sprechen koennte."


# --- Proaktive Frage beim Eintritt in eine Phase --------------------------

_TEXT_PROAKTIV = "Bevor ich vorschlage: habt ihr selbst schon Ideen?"
_TEXT_WIR_ZUERST_KNOPF = "Ja, wir zuerst"
_TEXT_SCHLAG_VOR_KNOPF = "Schlag du vor"
_TEXT_WIR_ZUERST = "Gut - ich hoere zu."


#: Die proaktive Phasenmeldung (06.09.2026, Birk nach der Testgruppe): sobald
#: alles Noetige gespeichert ist, sagt der Bot es von selbst -- in EINER
#: kurzen, EIGENEN Nachricht, nicht als vierter Knopf unter 1 100 Zeichen
#: Fliesstext. Gemessen am Testabend: neun angebotene Phasenknoepfe, null
#: Druecke; sie hingen alle unter langen Texten.
#: ``{phase}`` ist seit dem 02.10.2026 (Birk) ``phasen.bezeichnung`` -- also
#: "2 · Fragen", Nummer UND Titel (siehe ``phasen.knopfbezeichnung``).
_TEXT_PHASE_ANGEBOT = "{erledigt} steht. Weiter zu Phase {phase}?"
#: Was je Zielphase erledigt ist -- der halbe Satz vor "Weiter zu ...".
#: Kurz und konkret, damit die Gruppe sieht, WORAUF sich das Angebot stuetzt,
#: ohne dass der Bot den Arbeitsstand nacherzaehlt.
_ERLEDIGT_FUER = {
    2: "Eure Begriffe",
    3: "Eure Fragen",
    4: "Die Interviews sind ausgewertet und",
    5: "Setting, Figuren und Geschichte",
    6: "Geschichte und Szenenfolge",
    7: "Alle Szenentexte",
}
#: Die Frage unter der Abschlussnachricht (06.09.2026): die Parameter stehen
#: darueber, hier steht nur noch, wohin es geht. Seit dem 02.10.2026 (Birk,
#: Padua-Probe: "On to Questions" sagte der Gruppe nicht, dass "Questions"
#: die naechste PHASE ist) mit Nummer und Titel: ``{phase}`` ist
#: ``phasen.bezeichnung`` ("2 · Fragen") -> "Weiter zu Phase 2 · Fragen?".
_TEXT_PHASE_WEITER = "Weiter zu Phase {phase}?"
#: Der zweite Knopf hiess bis zum 06.09.2026 "Noch nicht". Er heisst jetzt
#: nach dem, was die Gruppe damit tut: unter einer Abschlussnachricht mit
#: allen Werten ist "Noch nicht" keine Antwort mehr -- "Noch etwas aendern"
#: schon. Die art (``ART_NOCH_NICHT``) und ihre Wirkung bleiben.
_TEXT_PHASE_NOCH_NICHT_KNOPF = "Noch etwas aendern"
#: Derselbe Knopf (``ART_NOCH_NICHT``), wenn die Abschlussnachricht die
#: Speicherleiste ersetzt (Padua Hotfix B5, 02.10.2026,
#: ``stationen.sende_abschluss_statt_meldung``): dann heisst er nach dem Feld,
#: das gerade gespeichert wurde. Schluessel = Leistenart
#: (``erkenner._LEISTENARTEN``, ``basis.speicherleiste``); fehlt eine Art,
#: bleibt es bei "Noch etwas aendern".
_TEXT_AENDERN_KNOPF_FUER = {
    "begriffe": "Begriffe aendern",
    "fragen": "Fragen aendern",
    "rahmen": "Setting aendern",
    "geschichte": "Geschichte aendern",
}
_TEXT_NOCH_NICHT = "Gut, wir bleiben hier."
#: Die Beschriftung des Phasenknopfs (``basis.biete_phase``,
#: ``basis._phasenknopf``, ``stationen.biete_phase_proaktiv``). ``{phase}``
#: ist ``phasen.bezeichnung`` -> "Weiter zu Phase 2 · Fragen" (02.10.2026).
_TEXT_WEITER_ZU_KNOPF = "Weiter zu Phase {phase}"
#: Rueckfall fuer ``_ERLEDIGT_FUER`` -- im Aufruf, nicht in einer Signatur (K1).
_TEXT_ALLES_NOETIGE = "Alles Noetige"

#: Die Knopfbeschriftungen des Phase-5-Gates (Padua, 07.10.2026,
#: ``basis.biete_p5_check``).
_TEXT_P5_CHECK_OK_KNOPF = "✅ Passt alles - Textentwurf starten"
_TEXT_P5_CHECK_AENDERN_KNOPF = "✏️ Etwas aendern"
#: Die Rueckfrage nach "Etwas aendern" -- die Gruppe bleibt in Phase 4.
_TEXT_P5_CHECK_AENDERN_FRAGE = "Was soll ich aendern? Sagt es mir einfach."
_JOURNAL_P5_CHECK_BESTAETIGT = "Werkbank vor Phase 5 bestaetigt"

#: Die frueheren Inline-Literale aus ``figuren.py`` (Aufgabe 12, A1):
#: Knopf-Quittungen (answerCallbackQuery), Journalzeilen, Chatzeilen.
_TEXT_NAME_GEAENDERT_QUITTUNG = "Name geaendert"
_JOURNAL_FIGURENANZAHL = "Figurenanzahl: {anzahl}"
_JOURNAL_FIGUREN = "Figuren: {namen}"
#: Kopf vor der Figurenzeile aus ``erkenner._figuren_zeile``.
_TEXT_NOTIERT_KOPF = "Notiert:\n"
_TEXT_FIGUREN_QUITTUNG = "Figuren uebernommen"
_TEXT_SPRACHDUKTUS_ZEILE = "Sprachduktus: {profil}"
#: Rueckfall fuer ``{quelle}`` in ``_TEXT_DUKTUS_LAEUFT``.
_TEXT_DAS_INTERVIEW = "das Interview"
_JOURNAL_FIGURENLISTE_STEHT = "Figurenliste steht"
_TEXT_INTERVIEW_WAEHLEN_QUITTUNG = "Interview waehlen"

#: Die frueheren Inline-Literale aus ``szenen.py`` (Aufgabe 12, A1).
#: ``_TEXT_SZENE_KOPF`` ist Kopf eines Szenentexts, Knopf-Quittung und
#: Listeneintrag im Hinweis auf spaetere Szenen.
_TEXT_SZENE_KOPF = "Szene {nummer}"
#: Eine Szene mit Angabe dahinter: Form je Szene (Journal, Festlegung) und
#: die Quittung nach einem Feldvorschlag.
_TEXT_SZENE_EINTRAG = "Szene {nummer}: {was}"
_JOURNAL_SZENENFOLGE = "Szenenfolge: {liste}"
_TEXT_SZENEN_UEBERNOMMEN_QUITTUNG = "{anzahl} Szenen uebernommen"
_TEXT_FESTLEGUNG_FORMEN = "Form je Szene — {liste}"
_JOURNAL_FORM_JE_SZENE = "Form je Szene: {liste}"
_TEXT_FORMWAHL_QUITTUNG = "Formwahl uebernommen, Geschichte fehlt noch"
_JOURNAL_GESCHICHTE = "Geschichte: {geschichte}"
_TEXT_RICHTUNG_QUITTUNG = "Richtung uebernommen"
_TEXT_GESPEICHERT_WAS_ANDERS_QUITTUNG = "Gespeichert, was soll anders sein?"
#: Name aus dem Plan; der Text ist die Knopf-Quittung von
#: ``szenen._nach_szenen_gespeichert``, keine Journalzeile.
_JOURNAL_GESCHICHTE_MIT_SZENEN = "Geschichte mit {anzahl} Szenen uebernommen"
_TEXT_SCHLAGE_ANGABEN_VOR = "Ich schlage die fehlenden Angaben vor"
_TEXT_SZENE_LAEUFT_QUITTUNG = "Szene {nummer} laeuft"

#: Was nach einem Druck kurz eingeblendet wird (answerCallbackQuery,
#: Karte A1 aus Literalen gebildet). Ein bis vier Woerter. Die Rueckgaben
#: der Handler in ``wirkung.py`` (Aufgabe 13); wo derselbe Wortlaut schon
#: als Quittung aus ``figuren``/``szenen`` in der Tabelle steht
#: (``_TEXT_SZENE_KOPF``, ``_TEXT_SZENE_EINTRAG``, ``_TEXT_RICHTUNG_QUITTUNG``,
#: ``_TEXT_GESPEICHERT_WAS_ANDERS_QUITTUNG``), liest der Handler jene.
_ANTWORT_LAEUFT_SCHON = "Laeuft schon"
_ANTWORT_GESCHICHTE_LAEUFT = "Geschichte laeuft"
_ANTWORT_PASST = "Passt"
_ANTWORT_WAS_ANDERS = "Was soll anders sein?"
_ANTWORT_SZENE_GESCHAERFT = "Szene {nummer} geschaerft"
_ANTWORT_FIGUR_GESCHAERFT = "{name} geschaerft"
_ANTWORT_UEBERNOMMEN = "Uebernommen: {was}"
_ANTWORT_NOCH_EINE_RUNDE = "Noch eine Runde"
_ANTWORT_WIE_VIELE = "Wie viele?"
_ANTWORT_SZENEN_ANZAHL = "{anzahl} Szenen"
_ANTWORT_REIHENFOLGE = "Sagt mir die Reihenfolge"
_ANTWORT_WELCHE_FORM = "Welche Form?"
_ANTWORT_SZENE_RAUS = "Szene {nummer} raus"
_ANTWORT_SZENE_STEHT = "Szene {nummer} steht"
_ANTWORT_WAS_ANDERS_WERDEN = "Was soll anders werden?"
_ANTWORT_SZENE_BLEIBT = "Szene {nummer} bleibt"
_ANTWORT_LETZTE = "Das war die letzte"
_ANTWORT_SZENE_UEBERARBEITET = "Szene {nummer} wird ueberarbeitet"
_ANTWORT_BLEIBT = "Bleibt"
_ANTWORT_SZENEN_EINZELN = "Ich sehe die Szenen einzeln durch"
_ANTWORT_NOCH_EINMAL = "Ich lese noch einmal"
_ANTWORT_TEXTBUCH = "Textbuch"
_ANTWORT_ERZAEHLT = "Erzaehlt"
_ANTWORT_ANDERE_VOR = "Ich schlage andere vor"
_ANTWORT_LEITFADEN = "Leitfaden"
_ANTWORT_FIGUREN_ANZAHL = "{anzahl} Figuren"
_ANTWORT_ZAHL = "Sagt mir die Zahl"
_ANTWORT_WELCHER_NAME = "Welchen Namen?"
_ANTWORT_NAMEN_VORSCHLAGEN = "Namen vorschlagen"
_ANTWORT_INTERVIEW_GEWECHSELT = "Interview gewechselt"
_ANTWORT_DUKTUS_VORSCHLAEGE = "Duktus-Vorschlaege"
_ANTWORT_DUKTUS_UEBERNOMMEN = "Duktus uebernommen"
_ANTWORT_STIL_UEBERNOMMEN = "Stil uebernommen"
_ANTWORT_ZUGEORDNET = "Zugeordnet: {anzahl}"
_ANTWORT_ENTFERNT = "Entfernt"
_ANTWORT_WIR_HOEREN_ZU = "Wir hoeren zu"
_ANTWORT_ICH_SCHLAGE_VOR = "Ich schlage vor"
_ANTWORT_HOERE_WEITER_ZU = "Ich hoere weiter zu"
_ANTWORT_INTERVIEW_BEENDET = "Interview beendet"
_ANTWORT_ANGELEGT = "{name} angelegt"
_ANTWORT_ALS_BEITRAG = "Als Beitrag genommen"
_ANTWORT_KERNTHEMA = "Kernthema uebernommen"
_ANTWORT_AUFNAHME_UMGESCHALTET = "Aufnahme umgeschaltet"
_ANTWORT_PHASE = "Phase {nummer}"
_ANTWORT_AUSWERTUNG_LAEUFT = "Auswertung laeuft"
_ANTWORT_AUSWERTUNG = "Auswertung"
_ANTWORT_ZUSAMMENFASSUNG = "Zusammenfassung"
_ANTWORT_TRANSKRIPT = "Transkript"
_ANTWORT_STAND = "Stand"
_ANTWORT_HILFE = "Hilfe"
#: ``{stil}`` ist der Slug des Stils oder ``_TEXT_STIL_OHNE_WORT``.
_ANTWORT_SZENE_STIL = "Szene {nummer}: Stil {stil}"
_ANTWORT_USA_JA = "US-Modell: ja"
_ANTWORT_USA_NEIN = "Bleibt in der Schweiz"
_ANTWORT_P5_CHECK_OK = "Bestaetigt"
_ANTWORT_P5_CHECK_AENDERN = "Sagt mir, was zu aendern ist"
#: Toast, wenn ein anderer Phasenknopf ("Weiter zu Phase N", "Ja,
#: speichern") durch das Phase-5-Gate abgefangen wird (``befehle.p5_gate``).
_ANTWORT_P5_CHECK_NOETIG = "Erst die Werkbank pruefen"

#: Die uebrigen frueheren Inline-Literale aus ``wirkung.py`` (Aufgabe 13):
#: Journalzeilen (gehen ueber ``kontext._baue_journal`` in den Prompt),
#: Chatzeilen und eine Knopfbeschriftung.
_JOURNAL_SZENE_ABGENOMMEN = "Szene {nummer} abgenommen: {titel}"
_JOURNAL_RICHTUNG = "Richtung: {richtung}"
_TEXT_FIGUR_NR_KNOPF = "Figur {nr}: {name}"
_JOURNAL_SPRACHSTIL = "Sprachstil {name}: {stil}"
_JOURNAL_ZUFALL_ZUGEORDNET = (
    "Interviews zufaellig zugeordnet: {figuren} Figuren auf "
    "{interviews} Interviews"
)
_JOURNAL_FIGUR_ENTFERNT = "Figur entfernt: {name}"
_TEXT_FIGUR_RAUS = "{name} ist raus."
#: Rueckfall fuer einen Interviewnamen am Satzanfang (vgl.
#: ``_TEXT_DAS_INTERVIEW`` mitten im Satz).
_TEXT_DAS_INTERVIEW_ANFANG = "Das Interview"
#: ``{weiter}`` ist ``aufnahme._TEXT_INTERVIEW_OHNE_KNOPF_WEITER``.
_TEXT_INTERVIEW_STEHT = "{name} steht. {weiter}"
_JOURNAL_KERNTHEMA = "Kernthema: {kernthema}"
_TEXT_KERNTHEMA_NOTIERT = "Kernthema notiert: {kernthema}"
_TEXT_ICH_WERTE_AUS = "Ich werte {name} aus."
_TEXT_IM_WORTLAUT = "{name}, im Wortlaut:\n{text}"
_TEXT_SZENE_STIL_GESETZT = "Szene {nummer}, Stil: {stil} (Vorlage: {herkunft})."
_TEXT_SZENE_OHNE_STIL = "Szene {nummer}: ohne Stilvorlage, es bleibt bei der Form."
_JOURNAL_SZENE_STIL = "Szene {nummer} Stil: {stil}"
#: Das Wort fuer "kein Stil" in Journal und Einblendung.
_TEXT_STIL_OHNE_WORT = "ohne"
#: Die Journalzeile der USA-Einwilligung. Die Entscheidung selbst faellt am
#: internen Knopfwert ``"ja"`` (``_wirkung_szene_usa``), nie an diesem Text.
_JOURNAL_USA_JA = "US-Modell fuer Szenentexte: ja"
_JOURNAL_USA_NEIN = "US-Modell fuer Szenentexte: nein"


#: Was "Schlag du vor" je Phase vom Modell verlangt -- die Anweisung, die
#: ``ablauf.starte_auftrag`` an den Koerper haengt. Je Phase eine, weil in
#: jeder etwas anderes vorzuschlagen ist; fehlt eine, gibt es einen
#: allgemeinen Auftrag.
ANWEISUNGEN = {
    1: "Schlag der Gruppe eine Begriffsliste vor und haeng sie als Block "
       "'VORSCHLAG BEGRIFFE:' an.",
    2: "Schlag der Gruppe Interviewfragen zur Auswahl vor: GENAU FUENF je "
       "Kernbegriff der Gruppe, nach Begriffen geordnet (erst alle fuenf zum "
       "ersten Begriff, dann die fuenf zum zweiten usw.). Haeng sie als Block "
       "'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je Zeile im Format "
       "'Begriff: Frage', ohne Nummerierung. JEDE Frage steht im SATZBAU fuer "
       "sich: inhaltlich duerfen sie aufeinander folgen, aber keine Frage "
       "darf sprachlich auf etwas Vorheriges zeigen (kein 'und dann?', kein "
       "'in dem Moment', kein 'davon', kein 'diese Person', kein 'dabei') - "
       "was eine Frage aus einer vorherigen aufgreift, spricht sie noch "
       "einmal selbst aus ('Wenn du mal Rassismus erlebt hast: Was hat dir in "
       "dem Moment geholfen?') - jede muss allein vorgelesen verstaendlich "
       "sein, weil die Gruppe drei beliebige heraus nimmt. "
       "Altersgerecht, und so, dass eine 15- bis 18-Jaehrige sie einer "
       "FREMDEN Person auf der Strasse stellen kann. Wiederhol die Fragen "
       "nicht im Fliesstext - die Gruppe sieht die nummerierte Liste und "
       "nennt drei Nummern.",
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

# --- Phase 2 · Verfeinerung (06.09.2026) ----------------------------------

#: Die Sensibilitaetspruefung laeuft seit 02.10.2026 IM selben Modellzug wie
#: der Vorschlag selbst (``prompts/phasen/2.md``), nicht mehr als eigener
#: Schritt danach -- dieser Satz wird an mehrere ANWEISUNG-Texte angehaengt,
#: damit er nur einmal formuliert ist.
_ANWEISUNG_FRAGEN_SENSIBEL = (
    "Pruef jede Frage: beruehrt sie ein sensibles Thema (Familie, Herkunft, "
    "Religion, Gewalt, Liebe und Koerper, Geld, Krankheit, Flucht, "
    "Diskriminierung)? Formuliere jede sensible Frage zusaetzlich zu EINEM "
    "weichen Gespraechsstueck um - zwei bis drei Saetze, Du-Form, sprechbar, "
    "im Ton einer 15- bis 18-Jaehrigen, die eine fremde Person anspricht; der "
    "Kern der Frage bleibt derselbe. Gibt es mindestens eine sensible Frage, "
    "haeng die weichen Fassungen als Block 'VORSCHLAG FRAGEN WEICH:' an, je "
    "Zeile '<Nummer> — <weiche Fassung>', nummeriert wie in der Liste "
    "darueber -- ist keine Frage sensibel, lass diesen Block ganz weg."
)
#: "Andere Richtung": die bisherigen Fragen stehen namentlich im Auftrag,
#: damit das Modell sie nicht umformuliert wieder vorlegt -- ohne diese
#: Aufzaehlung kaeme im zweiten Durchgang dieselbe Liste mit anderen Worten
#: (gemessen an der Kernthema-Stufe, an der genau das passierte).
#: ``{richtung_satz}`` ist vorformatiert und bleibt leer, wenn es keine
#: ausdrueckliche Richtung gibt (z. B. nach "keine Frage angenommen").
ANWEISUNG_FRAGEN_ANDERE = (
    "Schlag neue Interviewfragen vor, fuenf je Begriff, nach Begriffen "
    "geordnet. Diese hier hatten wir schon, nimm keine davon wieder und "
    "formuliere keine davon um:\n{alte}\n{richtung_satz}"
    "Haeng sie als Block 'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je Zeile "
    "im Format 'Begriff: Frage'. Wiederhol sie nicht im Fliesstext.\n"
    + _ANWEISUNG_FRAGEN_SENSIBEL
)
#: Wie ``{richtung_satz}`` lautet, wenn die Gruppe eine Richtung genannt hat
#: (sonst bleibt er ein leerer String).
_TEXT_FRAGEN_RICHTUNG_SATZ = "Die Gruppe moechte diese Richtung: {richtung}\n"
#: Die Gruppe hat eigene Fragen diktiert -- sie kommen in die Auswahl, und
#: der Bot fuellt auf, statt sie zu ersetzen. (Bleibt ungenutzt im neuen
#: Ablauf -- die Richtung geht ueber ``ANWEISUNG_FRAGEN_ANDERE``.)
ANWEISUNG_FRAGEN_EIGENE = (
    "Die Gruppe hat eigene Fragen genannt. Nimm sie unveraendert als erste "
    "Zeilen und ergaenze sie mit deinen Vorschlaegen auf genau zehn. Haeng "
    "alles als Block 'VORSCHLAG FRAGENAUSWAHL:' an, eine Frage je Zeile."
)
#: Eine einzelne Frage wird auf Wunsch der Gruppe ueberarbeitet
#: (02.10.2026, "Schaerfen" bzw. eine freie Nachricht waehrend diese Frage
#: die aktuelle ist). ``{sensibel_hinweis}`` traegt die bisherige weiche
#: Fassung, wenn es eine gab -- das Modell soll wissen, dass sie beim
#: Ueberarbeiten erhalten oder bewusst fallengelassen wird.
ANWEISUNG_FRAGE_SCHAERFEN = (
    "Die Gruppe moechte diese Interviewfrage {nummer} aendern:\n{frage}\n"
    "{sensibel_hinweis}"
    "Das soll sich aendern: {wunsch}\n"
    "Schreib eine ueberarbeitete Fassung und haeng sie als Block "
    "'VORSCHLAG FRAGE:' an, genau eine Zeile im Format 'Begriff: Frage'. "
    + _ANWEISUNG_FRAGEN_SENSIBEL
)
#: Traegt die bisherige weiche Fassung in ``ANWEISUNG_FRAGE_SCHAERFEN``, wenn
#: es eine gab -- sonst bleibt der Platzhalter ein leerer String.
_TEXT_FRAGE_SCHAERFEN_SENSIBEL_HINWEIS = (
    "Bisher war sie weich formuliert: {weich}\n"
)
#: Die Umformulier-Runde (Testkarte t_266e7485, 06.10.2026, nur Padua): EIN
#: gebuendelter Aufruf statt einer Schaerfung je Frage -- dieselben Ton-
#: Regeln wie ``ANWEISUNG_FRAGE_SCHAERFEN`` (``_ANWEISUNG_FRAGEN_SENSIBEL``,
#: ueber ``_ohne_weich_auftrag`` fuer Padua ohnehin herausgeschnitten), keine
#: neu erfundenen. ``{sprache}`` ist der Sprachname der aktiven Sprachschicht
#: (``sprache.SPRACHNAMEN``) -- das Modell soll in der Sprache der Gruppe
#: antworten, nicht zwingend auf Englisch.
ANWEISUNG_FRAGEN_UMFORMULIEREN = (
    "Die Gruppe moechte alle {anzahl} behaltenen Interviewfragen nach "
    "dieser Anweisung neu formulieren: {wunsch}\n"
    "Die aktuellen Fragen, nummeriert:\n{fragen}\n"
    "Schreib fuer JEDE Nummer eine ueberarbeitete Fassung, in derselben "
    "Reihenfolge, genau {anzahl} Zeilen im Format 'Begriff: Frage', ohne "
    "Nummerierung. Antworte auf {sprache}. Haeng sie als Block 'VORSCHLAG "
    "FRAGEN UMFORMULIERUNG:' an, nichts sonst in diesem Block. "
    + _ANWEISUNG_FRAGEN_SENSIBEL
)
#: Eroeffnung und Abschluss in einem Block -- es ist eine Entscheidung.
#:
#: ``{{projekt_kurz}}`` kommt aus dem Workshop-Profil (06.09.2026): worum es
#: in dem Stueck geht, ist die Angabe, die sich zwischen zwei Einsatzorten
#: als Erstes aendert. Gefuellt wird beim Aufruf und **vor** ``.format`` --
#: ``str.format`` machte aus ``{{x}}`` sonst ein woertliches ``{x}``.
ANWEISUNG_EROEFFNUNG = (
    "Jetzt fehlt noch, womit das Interview anfaengt und aufhoert. Schlag "
    "einen Eroeffnungstext vor, den die Interviewerin einer fremden Person "
    "sagt, bevor sie die erste Frage stellt - drei bis fuenf Saetze: wer wir "
    "sind, worum es geht ({{projekt_kurz}}), wofuer die Antworten "
    "verwendet werden (anonym, als Material fuer ein Stueck), dass man "
    "jederzeit aufhoeren kann, und die Bitte um Erlaubnis, das Gespraech "
    "aufzunehmen. Dazu einen kurzen Abschluss: Dank und was jetzt weiter "
    "passiert. Haeng beides als Block 'VORSCHLAG EROEFFNUNG:' an - zuerst "
    "die Eroeffnung, danach eine Zeile, die mit 'Abschluss:' beginnt. "
    "Sprache wie von einer 16-Jaehrigen, keine Behoerdensaetze. Der Text "
    "steht NUR im Block - schreib ihn nicht zusaetzlich davor in den "
    "Fliesstext; davor hoechstens ein Satz und eine Frage."
)

from interview_theater import sprache  # noqa: E402  (unten: kein Zyklus beim Import)

T = sprache.Texte(__name__)

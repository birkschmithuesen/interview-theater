"""Datenbankschema und Verbindungsaufbau (SPEC-kontext-architektur.md § 3.1)."""

import re
import sqlite3

# Woertlich aus SPEC-kontext-architektur.md § 3.1 uebernommen, nur um
# "IF NOT EXISTS" ergaenzt, damit initialisiere() gefahrlos mehrfach laufen kann.
SCHEMA = """
-- Pro Bot-Token, nicht pro Gruppe: die getUpdates-Position
CREATE TABLE IF NOT EXISTS bot_zustand (
  bot_name              TEXT PRIMARY KEY,
  letzte_update_id      INTEGER,
  gestartet_am          TEXT,
  letzte_aktivitaet_am  TEXT
);

CREATE TABLE IF NOT EXISTS gruppe (
  chat_id                         INTEGER PRIMARY KEY,
  bot_name                        TEXT NOT NULL,
  titel                           TEXT,
  erste_nachricht_am              TEXT,
  -- Antwort- und Extraktionsstand
  letzte_beantwortete_message_id  INTEGER DEFAULT 0,
  letzte_extrahierte_message_id   INTEGER DEFAULT 0,
  -- Journal-Extraktor-Wasserzeichen (Verdraengung statt jedem Zug, siehe journal.py)
  letzte_journalisierte_message_id INTEGER DEFAULT 0,
  -- Schalter
  wortlaut_modus                  TEXT,     -- NULL=aus, '*'=alle, sonst Aufnahmename
  szene_usa_bestaetigt_am         TEXT,     -- gesetzt = Gruppe hat dem US-Modell fuer Szenen zugestimmt (05.09.)
  szene_usa_angeboten_am          TEXT,     -- gesetzt = der Bot hat den Wechsel schon vorgeschlagen
  szene_usa_offener_auftrag       TEXT,     -- der Szenenauftrag, der auf die Antwort wartet
  gruendlich_naechster_zug        INTEGER NOT NULL DEFAULT 0,  -- Modus B einmalig (§ 4.5)
  whisper_stumm_seit              TEXT,     -- gesetzt = Ausfall gemeldet (§ 10.4)
  interviewmodus_seit             TEXT,     -- gesetzt = Interviewmodus an (teil-b.md Aufgabe 5, § 10.1)
  -- Zufallstoken fuer die Gruppenseite /g/<token> der Weboberflaeche
  -- (NACHTRAG-weboberflaeche-und-sprache.md N1-B): kein Login, wer die URL
  -- hat, sieht die Gruppe. Erzeugt der Bot (repo.stelle_web_token_sicher),
  -- weil der Webserver die Datenbank read-only oeffnet.
  web_token                       TEXT,
  -- Whisper-Sprache dieser Gruppe (Karte A1): NULL = Profilwert
  -- (sprache.whisper), sonst 'auto' oder ein ISO-639-1-Code. Additiv
  -- nachgeruestet ueber _migriere_fehlende_spalten.
  stt_sprache                     TEXT,
  -- Welcher Kanal diese Gruppe bedient (30.09.2026): 'telegram' (Vorgabe) oder
  -- 'web'. Additiv nachgeruestet ueber _migriere_fehlende_spalten.
  kanal                           TEXT NOT NULL DEFAULT 'telegram',
  -- Bis wann die Tippanzeige im Web gilt (ISO 8601). Eine Spalte statt einer
  -- Zeile je Aufruf, siehe den Kommentar an web_post.
  web_tippt_bis                   TEXT,
  -- Wann der Gruppe zuletzt gesagt wurde, dass der Tagesdeckel erreicht ist
  -- (Karte Padua S). In der DATENBANK und nicht im Prozess: ein Neustart
  -- meldete sonst sofort wieder, und der Nachhol-Arbeiter laeuft im
  -- Minutentakt. Additiv nachgeruestet ueber _migriere_fehlende_spalten.
  kostenpause_gemeldet_am         TEXT
);

CREATE TABLE IF NOT EXISTS nachricht (
  chat_id        INTEGER NOT NULL,
  message_id     INTEGER NOT NULL,
  telegram_user  INTEGER,
  absender       TEXT,                      -- Vorname oder 'Bot'
  ist_bot        INTEGER NOT NULL DEFAULT 0,
  -- text|sprache|foto|sticker|sonstiges|transkript
  -- 'transkript' ist das Echo eines Interview-Teils, das der Bot zur
  -- Kontrolle in den Chat schreibt (§ 10.6). Es wird gespeichert wie jede
  -- andere Nachricht, geht aber weder ins Erkenner- noch ins
  -- Gespraechsfenster: Interviewinhalt ist nicht Gruppenabsicht.
  typ            TEXT NOT NULL,
  text           TEXT,
  gesendet_am    TEXT NOT NULL,             -- ISO 8601
  unterdrueckt   INTEGER NOT NULL DEFAULT 0,-- 1 = nie Antwort auslösen (Nachtstau)
  -- 1 = der Text ist das Transkript einer Sprachnachricht (Padua Hotfix
  -- Befund 1, 02.10.2026). ``typ`` bleibt dabei 'text' -- Fenster, Erkenner,
  -- Journal und ``unbeantwortete`` laufen unveraendert --, nur
  -- ``kontext.sprecherzeile`` markiert die Zeile im Gespraechs-Prompt als
  -- gesprochen. Additiv nachgeruestet ueber _migriere_fehlende_spalten.
  gesprochen     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_nachricht_zeit ON nachricht(chat_id, message_id);

-- Sprachaufnahmen UND Textimporte. Eine Statusmaschine fuer beides (§ 10).
--
-- Ein Interview ist eine Einheit (Nachtrag 05.09.2026, § 10.6): der KOPF
-- (klasse='lang', teil_von NULL) traegt Name, zusammengefuegtes Transkript
-- und Verdichtung, jede einzelne Sprachnachricht dazu ist ein TEIL
-- (klasse='teil', teil_von = id des Kopfes) mit eigener Audiodatei und
-- eigenem Transkript. Additiv: bestehende Zeilen haben teil_von NULL und
-- bleiben damit je ein eigenstaendiges Interview mit Transkript am Kopf.
CREATE TABLE IF NOT EXISTS aufnahme (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  message_id      INTEGER NOT NULL,
  name            TEXT,                     -- 'Maria'; Ersatz: 'Interview 3'
  klasse          TEXT NOT NULL,            -- kurz (Gespraechsbeitrag) | lang (Interview-Kopf) | teil (eine Sprachnachricht darin)
  quelle          TEXT NOT NULL,            -- sprache | text
  audio_pfad      TEXT,                     -- NULL bei quelle='text' und beim Kopf
  transkript      TEXT,
  dauer_sekunden  INTEGER,
  status          TEXT NOT NULL,            -- laeuft|empfangen|transkribiert|fertig|fehlgeschlagen
  fehlertext      TEXT,
  versuche        INTEGER NOT NULL DEFAULT 0,
  empfangen_am    TEXT NOT NULL,
  -- Gesetzt = diese Zeile ist ein Teil des Interviews mit dieser id.
  teil_von        INTEGER,
  -- Gesetzt = die Gruppe hat "fertig" gesagt. Ein Kopf mit beendet_am und
  -- status='laeuft' wartet nur noch darauf, dass seine Teile durch sind
  -- (aufnahme.schliesse_ab, aufgegriffen vom Nachhol-Arbeiter).
  beendet_am      TEXT,
  -- Gesetzt = weich geloescht (N5, 05.09.2026). Die Material-Sperre gilt fuer
  -- Aufnahmen der Gruppe, die Inhalt tragen; ein halluziniertes oder
  -- versehentliches Interview ist entfernbar, wenn die Gruppe es sagt. Die
  -- Audiodatei bleibt auf der Platte -- die Loeschzusage erfuellt weiterhin
  -- allein scripts/loeschen.py.
  entfernt_am     TEXT,
  -- Gesetzt = diese Zeile ist eine KOPIE aus einer anderen Gruppe
  -- (scripts/interviews_uebernehmen.py, 06.09.2026). Form:
  -- "<quell_chat_id>:<alte_aufnahme_id>". Zwei Aufgaben: Herkunft belegen
  -- (das Material gehoert weiter der Gruppe, die es aufgenommen hat) und
  -- Idempotenz -- ein zweiter Lauf ueberspringt, was diesen Marker schon
  -- traegt. Additiv; bestehende Zeilen tragen NULL und sind damit eigenes
  -- Material.
  uebernommen_von TEXT,
  uebernommen_am  TEXT
);
-- Bewusst KEIN Index auf teil_von: initialisiere() faehrt erst das ganze
-- SCHEMA und ergaenzt danach fehlende Spalten -- ein Index auf eine Spalte,
-- die es in einer Alt-Datenbank noch nicht gibt, liesse den Start mit
-- "no such column: teil_von" scheitern, bevor die Migration ueberhaupt
-- laeuft. Ein Workshop-Wochenende bringt Dutzende Aufnahmen, keine
-- Millionen.
CREATE INDEX IF NOT EXISTS idx_aufnahme_offen ON aufnahme(status);

CREATE TABLE IF NOT EXISTS verdichtung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  aufnahme_id      INTEGER NOT NULL,
  zusammenfassung  TEXT NOT NULL,
  erstellt_am      TEXT NOT NULL,
  -- Gesetzt = weich geloescht (N5): faellt mit dem Interview, zu dem sie
  -- gehoert. Geaendert wird eine Verdichtung weiterhin nie -- ausser durch
  -- eine Transkriptkorrektur, die dieselbe Ersetzung ueberall vornimmt.
  entfernt_am      TEXT
);

CREATE TABLE IF NOT EXISTS verdichtung_thema (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  verdichtung_id  INTEGER NOT NULL,
  thema           TEXT NOT NULL,
  -- Dasselbe Ergebnis in höchstens acht Wörtern (N3/N6): die Kurzform, aus
  -- der die Summary-Zeile je Interview auf der Gruppenseite und die eine
  -- Zeile je Interview auf dem Dashboard entstehen. Additiv; fehlt sie,
  -- zeigen beide Ansichten `thema`.
  kurz            TEXT,
  beleg_zitat     TEXT,                     -- NULL, wenn Prüfung nach § 5 fehlschlug
  zitat_geprueft  INTEGER NOT NULL DEFAULT 0,
  -- Gesetzt = dieses Thema gehoert zum Kernthema der Gruppe (05.09.2026
  -- abends): der Filter am Kernthema laeuft einmal, nachdem die Kernfrage
  -- steht (interview_theater/kernzitate.py), und markiert die Themen, die
  -- zur Kernfrage passen. Ab den Figuren sieht das Modell nur noch diese --
  -- nicht mehr alle Verdichtungen und keine Transkripte (kontext.baue).
  zum_kernthema_am TEXT
);

-- Welche Kernbegriffe der Gruppe eine Verdichtung traegt (06.09.2026).
--
-- n:m, deshalb eine eigene Tabelle und keine Spalte an ``verdichtung``: ein
-- Interview traegt mehrere Begriffe, ein Begriff sammelt mehrere Interviews.
-- Der Begriff steht als TEXT und nicht als id -- es gibt keine Begriffstabelle:
-- ``arbeitsstand.begriffe`` ist Freitext, den die Gruppe jederzeit umschreibt
-- (interview_theater/begriffe.py zerlegt ihn). Eine Fremdschluesselbeziehung
-- auf etwas, das es als Zeile nicht gibt, waere eine Erfindung.
--
-- Die Zeilen sind ABGELEITET, nicht entschieden: sie entstehen deterministisch
-- aus Zusammenfassung und Kernthemen der Verdichtung und werden bei jedem Lauf
-- fuer diese Verdichtung ersetzt (repo.setze_verdichtung_begriffe). Deshalb
-- gibt es hier kein ``entfernt_am`` -- weiches Loeschen haelt Entscheidungen
-- fest, und eine Zuordnung ist keine. Die Verdichtung selbst bleibt dabei
-- unberuehrt (AGENTS.md: Verdichtungen werden nie nachtraeglich geaendert).
--
-- UNIQUE ueber (verdichtung_id, begriff): derselbe Begriff steht an einer
-- Verdichtung genau einmal, auch wenn ein Nachtragslauf zweimal faellt.
CREATE TABLE IF NOT EXISTS verdichtung_begriff (
  id              INTEGER PRIMARY KEY,
  chat_id         INTEGER NOT NULL,
  verdichtung_id  INTEGER NOT NULL,
  aufnahme_id     INTEGER,
  begriff         TEXT NOT NULL,
  -- Woher die Zuordnung kommt: 'abgleich' = deterministischer Begriffsabgleich
  -- (interview_theater/begriffe.py). Als Feld angelegt, damit eine spaetere,
  -- andere Herkunft unterscheidbar bliebe, ohne die Tabelle zu aendern.
  quelle          TEXT NOT NULL DEFAULT 'abgleich',
  erstellt_am     TEXT NOT NULL,
  UNIQUE (verdichtung_id, begriff)
);
CREATE INDEX IF NOT EXISTS idx_verdichtung_begriff_chat
  ON verdichtung_begriff(chat_id, verdichtung_id);

-- Die geprueften Belegzitate, die zum Kernthema passen (05.09.2026 abends).
--
-- Warum eine eigene Tabelle und kein Flag an verdichtung_thema: ein Kernzitat
-- traegt mehr als eine Markierung -- einen Rang (die Reihenfolge, in der das
-- Modell sie fuer tragend haelt) und einen Halbsatz, warum es passt. Beides
-- steht im Kernpaket, das ab den Figuren den Platz der Transkripte einnimmt.
-- Die Zitate sind nie neu erfunden: jedes wird gegen das Original in
-- verdichtung_thema.beleg_zitat geprueft (zitat.pruefe), sonst verworfen.
CREATE TABLE IF NOT EXISTS kernzitat (
  id                   INTEGER PRIMARY KEY,
  chat_id              INTEGER NOT NULL,
  verdichtung_thema_id INTEGER,
  aufnahme_id          INTEGER,
  zitat                TEXT NOT NULL,
  begruendung          TEXT,
  rang                 INTEGER,
  erstellt_am          TEXT NOT NULL,
  entfernt_am          TEXT                 -- gesetzt = weich geloescht (N3)
);

CREATE TABLE IF NOT EXISTS arbeitsstand (
  chat_id                INTEGER PRIMARY KEY,
  begriffe               TEXT,
  -- Die Interviewfragen als eine Liste in einem Feld (Phase 2, Korrektur vom
  -- 04.09.2026 abends): Fragen formulieren und Interviews fuehren sind zwei
  -- Arbeiten. Additiv wie phase -- eine bestehende Datenbank bekommt die
  -- Spalte ueber _migriere_fehlende_spalten.
  fragen                 TEXT,
  kernthema              TEXT,
  kernthema_begruendung  TEXT,
  -- Phase 5 heisst seit dem 05.09.2026 "Format & Rahmen" (Birk: "Es muss
  -- nicht immer einen Konflikt geben -- es kann ein Lied sein oder eine
  -- harmonische Liebesszene. Das Ganze wird vermutlich ein Musical.").
  -- ``format``: was entsteht und welche Formen vorkommen duerfen, als ein
  -- Text ("Musical: Dialog, Lied, Rap"). ``rahmen``: worin es spielt --
  -- Ort(e), Zeit, Anlass, roter Faden.
  format                 TEXT,
  rahmen                 TEXT,
  -- Zwischenstand der zweistufigen Kernthema-Wahl (05.09.2026): Stufe 1 ist
  -- eine grobe Richtung, Stufe 2 die Formulierung. Die Richtung wird
  -- festgehalten, ohne ``kernthema`` zu setzen -- sonst stuende eine halbe
  -- Entscheidung im Arbeitsstand.
  kernthema_richtung     TEXT,
  -- Stufe 3 der Kernthema-Arbeit (05.09.2026 abends): die dramatische Frage.
  -- Drei Zeilen -- \"Frage: Was passiert, wenn ...\", \"Gegensatz: <zwei
  -- Wollen>\", \"Einsatz: <was auf dem Spiel steht>\". Sie ist der Filter, an
  -- dem die Kernzitate und die passenden Verdichtungen ausgewaehlt werden,
  -- und sie steht ab da im Kernpaket ganz vorn: Figuren und Szenen kommen
  -- aus dem Kernthema, nicht aus den Interviews.
  kernfrage              TEXT,
  -- Die Geschichte im Groben (Phase 5, Umbau 05.09.2026 nachts): Zeile 1 der
  -- Bogen in einem Satz, Zeile 2 das Ende. Sie tritt im Kernpaket an die
  -- Stelle, an der bis dahin das Kernthema stand -- die Gruppe erfindet sie
  -- frei, aus Begriffen und Fragen, nicht aus dem Material.
  geschichte             TEXT,
  -- Wie viele Figuren das Stueck haben soll -- die Gruppe sagt es vor der
  -- Figurenliste per Knopf (1-6 oder \"Andere Zahl\", 1-12). Frueher stand
  -- \"zwei bis vier\" im Prompt; das war eine Vorgabe des Bots an eine
  -- Entscheidung der Gruppe.
  figuren_anzahl         TEXT,
  -- Die Figurenliste, solange sie noch ein Entwurf ist (Ebene 1: Anzahl und
  -- Namen aendern). Eine Zeile je Figur, Form ``Name — Satz — Interview N``
  -- wie im Vorschlagsblock. Erst \"Gefaellt uns, weiter\" legt daraus echte
  -- Figuren an.
  figuren_entwurf        TEXT,
  -- Zeitpunkt, zu dem die Figurenliste Figur fuer Figur durchgegangen und
  -- damit fixiert wurde (Ebene 2). Voraussetzung fuer Phase 5 -- auch bei
  -- nur einer Figur.
  figuren_fixiert_am     TEXT,
  -- Die Figur, die in Ebene 2 gerade vorgestellt wird. Merkposten fuer die
  -- Knopfwege, die ueber einen Modellaufruf laufen (Duktus-Vorschlaege).
  figur_aktuell          TEXT,
  -- Die Art, zu der die Gruppe gerade "Passt, aber anders" gedrueckt hat.
  -- Der Wert ist dabei GESPEICHERT worden (damit etwas dasteht) -- die
  -- Leiste muss trotzdem wiederkommen, sonst gaebe es keinen Weg, den
  -- ueberarbeiteten Vorschlag abzunehmen. Genau das haelt dieses Feld fest;
  -- ein Speichern oder eine "Eigene Idee" raeumt es wieder ab.
  aenderung_offen        TEXT,
  -- Bleibt als OPTIONALES Feld: ein durchgehender Konflikt ist eine
  -- Rahmen-Entscheidung, keine Pflicht. Gesetzt wird er weiter ueber
  -- hauptkonflikt_setzen; /stand und Web zeigen ihn nur, wenn er dasteht.
  hauptkonflikt          TEXT,
  -- Die Arbeitsphase 1-7 (interview_theater/phasen.py). NULL = noch nie gesetzt
  -- und gilt dann wie 1. Gesetzt wird sie ausschliesslich von der Gruppe
  -- (phase_setzen, /phase) -- nie still erraten, und seit dem 05.09.2026 auch
  -- nicht mehr vom Bot selbst (SPEC § 0 Leitsatz 3, Nachtrag).
  -- Alt-Datenbanken tragen hier noch die achtstufige Nummerierung; sie wird
  -- einmalig umgerechnet, siehe _migriere_phasennummern.
  phase                  INTEGER,
  -- Zuletzt angebotene Phase: verhindert, dass der Hinweisblock in
  -- kontext.baue jeden Zug erneut nach demselben Wechsel fragt.
  phase_angeboten        INTEGER,
  -- Wann die Gruppe die aktuelle Phase betreten hat (06.09.2026 13:30,
  -- Birk: "wenn explizit in eine Phase gesprungen wird, nicht automatisch
  -- in eine andere springen -- egal ob Interviews vorhanden sind"). Das
  -- proaktive Angebot zaehlt nur Material, das NACH diesem Zeitpunkt
  -- entstanden ist: eine Gruppe, die nach 3 zurueckgeht, wird nicht von
  -- ihren Vortags-Interviews sofort wieder nach 4 geschoben.
  phase_gesetzt_am       TEXT,
  -- Die zehn zur Wahl gestellten Interviewfragen (Phase 2, 06.09.2026,
  -- Birk: die Fragen-Erarbeitung ist eine Mehrfachauswahl, kein Diktat).
  -- Eine Frage je Zeile, in der Reihenfolge des Vorschlagsblocks -- die
  -- Nummer einer Zeile ist zugleich der Wert ihres Knopfes.
  fragen_auswahl         TEXT,
  -- Welche davon angetippt sind: die Nummern, mit Komma getrennt. Der
  -- Zustand der Mehrfachauswahl steht damit in der Datenbank und nicht in
  -- der Telegram-Tastatur -- ein Neustart mitten in der Auswahl verliert
  -- nichts, und ein zweiter Druck auf denselben Knopf nimmt die Wahl
  -- zurueck, statt sie zu verdoppeln.
  fragen_gewaehlt        TEXT,
  -- Die Verfeinerungsebene der Fragen (Phase 2, 06.09.2026, Birk). Stehen
  -- die Fragen, prueft der Bot sie einmal auf sensible Themen und schlaegt
  -- je heikler Frage eine Einleitung vor -- ein bis zwei Saetze, die die
  -- Interviewerin vor der Frage sagt (warum sie fragt, dass man nicht
  -- antworten muss). Die Interviews fuehren 15-18-Jaehrige mit FREMDEN
  -- Personen; die Einleitung ist der Unterschied zwischen einer Frage und
  -- einem Uebergriff. Eine Zeile je Frage, Form ``<Nummer> — <Einleitung>``.
  -- Darf leer bleiben ("Keine der Fragen braucht eine besondere
  -- Einleitung.") -- das ist ein Ergebnis, kein fehlender Wert.
  frage_einleitungen     TEXT,
  -- Die WEICHE FASSUNG einer sensiblen Frage (06.09.2026, 10:18, Birk):
  -- statt "Einleitung + Frage" aneinandergehaengt wird die heikle Frage zu
  -- EINEM Gespraechsstueck umformuliert -- zwei bis drei Saetze, Du-Form,
  -- sprechbar, im Ton einer 15- bis 18-Jaehrigen, die eine fremde Person
  -- anspricht. Der KERN bleibt in ``fragen`` (er ist das, worueber die
  -- Gruppe entschieden hat); hier steht, wie sie es sagt. Eine Zeile je
  -- Frage, Form ``<Nummer> — <weiche Fassung>``, additiv nachgeruestet.
  -- Nicht-sensible Fragen haben keine Zeile: sie brauchen keine.
  fragen_weich           TEXT,
  -- Was die Interviewerin zu Beginn sagt: wer wir sind, was wir machen,
  -- wofuer die Antworten verwendet werden (anonym, Material fuer ein
  -- Stueck), dass man jederzeit aufhoeren kann, die Bitte um Erlaubnis zur
  -- Aufnahme. Voraussetzung fuer Phase 3 (``phasen.voraussetzungen``):
  -- ohne Eroeffnung geht niemand auf eine fremde Person zu.
  interview_eroeffnung   TEXT,
  -- Der Abschluss: Dank und was mit den Antworten weiter passiert. Eigenes
  -- Feld und nicht Teil der Eroeffnung, weil er im Leitfaden GANZ UNTEN
  -- steht (``leitfaden.baue``) -- ein Text, zwei Orte.
  interview_abschluss    TEXT,
  -- Der Laengen-Faktor der Gruppe (30.09.2026, Karte R). Gesetzt, wenn die
  -- Gruppe "Kuerzer" fuer das GANZE Stueck gedrueckt oder eine Laenge
  -- ausdruecklich genannt hat ("Instagram-Kuerze", Dortmund 06.09.2026):
  -- ein Faktor auf jedes kuenftige Wortbudget, 0,25 heisst ein Viertel.
  -- TEXT wie figuren_anzahl, damit derselbe eine Schreibweg
  -- (repo.setze_arbeitsstand) genuegt und "nicht gesetzt" NULL bleibt.
  -- Additiv nachgeruestet ueber _migriere_fehlende_spalten; ohne aktives
  -- Workshop-Profil liest die Spalte niemand.
  laengen_faktor         TEXT,
  geaendert_am           TEXT
);

-- Das Sprachprofil (05.09.2026, Birk: "das ist das Wichtigste") ist der
-- Grund, warum sich zwei Figuren im Szenentext hoerbar unterscheiden:
-- ``sprachprofil`` ist die Analyse (Satzlaenge, Fuellwoerter, Abbrueche,
-- Dialekt/Fremdsprache, Tempo -- 3-5 Zeilen), ``zitate`` sind 3-5 woertliche
-- Saetze aus dem Interview, `|`-getrennt, die als Few-Shots fuer die
-- Sprechweise in den Szenen-Prompt gehen. ``quelle_aufnahme_id`` haelt fest,
-- aus welchem Interview beides stammt -- die Zuordnung schlaegt der Bot vor,
-- die Gruppe nickt sie ab (Erkenner-art figur_quelle_setzen).
CREATE TABLE IF NOT EXISTS figur (
  id                  INTEGER PRIMARY KEY,
  chat_id             INTEGER NOT NULL,
  name                TEXT NOT NULL,
  beschreibung        TEXT,
  beleg_zitat         TEXT,
  sprachprofil        TEXT,
  -- Der in Phase 4 GEWAEHLTE Sprachstil (06.09.2026, Birk 12:20): eine
  -- Entscheidung der Gruppe ("Titel: Beispielsatz"), additiv neben
  -- sprachprofil, das aus einem Modellaufruf ueber ein Interview stammt.
  -- Zwei Spalten und nicht eine, weil es zwei Herkuenfte sind: hier waehlt
  -- die Gruppe, dort misst der Verdichter.
  sprachstil          TEXT,
  zitate              TEXT,
  quelle_aufnahme_id  INTEGER,
  -- Wann die Gruppe diese Figur in Ebene 2 abgenommen hat ("Passt").
  -- Merkposten fuer den Durchgang Figur fuer Figur (knoepfe.py): er sitzt
  -- an der Figur und nicht in einer Warteschlange, damit die Liste stimmt,
  -- auch wenn zwischendurch eine Figur entfernt wird oder dazukommt.
  geprueft_am         TEXT,
  geaendert_am        TEXT,
  entfernt_am         TEXT                  -- gesetzt = weich geloescht (N3)
);

-- Eine Szene ist seit dem 05.09.2026 zuerst eine PLANUNG und erst danach ein
-- Text (Birk, Ping-Pong 04.09. abends). Die Felder unten sind das, was die
-- Gruppe entscheidet, bevor geschrieben wird; der Bot schlaegt sie alle vor
-- (auch die Form), durchgesetzt wird nichts.
--
-- Pflicht fuer den Szenen-Aufruf sind form, ort, figuren und was_passiert
-- (szene.PFLICHTFELDER, Sperre in T5); der Rest ist optional. Es gibt
-- bewusst KEIN Feld "Funke" und keinen Konflikt je Szene -- eine Szene darf
-- ein Lied sein.
CREATE TABLE IF NOT EXISTS szene (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  nummer            INTEGER,
  titel             TEXT,
  kurzbeschreibung  TEXT,                   -- eine Zeile, geht immer mit
  -- Was in dieser Szene passiert, 3-5 Saetze (06.09.2026, Birk: "Jede Szene
  -- soll eine Zusammenfassung haben, was in der Szene passiert; wenn die
  -- originale Szene nicht mehr reinpasst, geht die Zusammenfassung in den
  -- Kontext."). Sie kommt vom Szenen-Modell selbst mit -- dritte Pflichtzeile
  -- der Antwort (ZUSAMMENFASSUNG:, szene.zerlege) --, kostet also keinen
  -- zweiten Aufruf, und wird bei jeder Fassung neu geschrieben. Bestehende
  -- Szenen aus der Zeit davor haben sie nicht; dann greift der Rueckfall in
  -- szene._szenen_zusammenfassung (Stichzeilen plus Schluss). Additiv
  -- nachgeruestet ueber _migriere_fehlende_spalten.
  zusammenfassung   TEXT,
  -- Dialog | Lied | Rap | Monolog | Chor | stumm (frei, aber diese Namen
  -- bevorzugt). Entscheidet, welcher Formen-Block in den Szenen-Prompt geht
  -- (prompts/formen/<form>.md).
  form              TEXT,
  -- Was der Bot in der Szenenfolge als Form VORGESCHLAGEN hat -- und warum
  -- (Birk, 06.09.2026 00:30: \"Die Form Monolog habe ich niemals eingegeben
  -- und aktiv bestaetigt.\"). Der Vorschlag steht hier und NICHT in ``form``:
  -- gesetzt wird die Form allein durch einen Knopfdruck der Gruppe, Szene
  -- fuer Szene. Ohne bestaetigte ``form`` wird nicht geschrieben
  -- (szene.PFLICHTFELDER).
  form_vorschlag       TEXT,
  form_vorschlag_grund TEXT,
  -- Die STILVORLAGE dieser Szene (06.09.2026, Birk 12:50): ein Slug aus
  -- ``prompts/stile/<slug>.md`` ("schlagabtausch", "litanei", "herkules").
  -- Birk: "alle Gruppen sollen auf alle Stile zugreifen koennen, als
  -- Auswahl, mit Nennung des Originalmaterials". Bis dahin hing der Stil am
  -- Bot (eine Overlay-Datei je Gruppe) und war damit nicht waehlbar.
  -- Leer heisst "ohne Stilvorlage" -- dann bleibt es bei den Formregeln.
  -- Wirkt nur bei ``form != prosa``: die Prosafassung ist eine Geschichte,
  -- kein Buehnentext, und ein Rap-Mass darauf waere sinnlos. Additiv
  -- nachgeruestet ueber _migriere_fehlende_spalten.
  stil              TEXT,
  ort               TEXT,
  zeit              TEXT,                   -- Tageszeit, "danach", "am nächsten Morgen"
  anlass            TEXT,                   -- warum sind sie hier
  was_passiert      TEXT,                   -- 1-3 Sätze Handlung
  was_anders        TEXT,                   -- was am Ende anders ist als am Anfang
  kernsaetze        TEXT,                   -- Sätze, die wörtlich vorkommen sollen
  ton               TEXT,                   -- Register: leise, komisch, harmonisch, hitzig
  volltext          TEXT,                   -- nur die zuletzt geänderte Szene geht mit
  -- Die PROSAFASSUNG der Szene (06.09.2026, Birk, 10:30): "In der Phase des
  -- Szenenbauens soll vom Format her zuerst eine Geschichte rauskommen, so
  -- wie wir sie als Buch lesen -- kein Theaterskript-Dialog, sondern eine
  -- Beschreibung von dem, was passiert." Phase 6 schreibt hierher, Phase 7
  -- uebersetzt sie in die gewaehlte Form nach ``volltext``. Beide bleiben
  -- stehen: die Prosa ist die Vorlage, gegen die der Theatertext geprueft
  -- werden kann. Additiv nachgeruestet ueber _migriere_fehlende_spalten.
  prosa             TEXT,
  -- Gesetzt = die Gruppe hat den Text mit "Passt" abgenommen (Phase 6,
  -- knoepfe.ART_SZENE_PASST). Ein Volltext allein heisst nur "geschrieben":
  -- unter jedem frischen Szenentext haengen vier Knoepfe, und erst einer
  -- davon macht daraus ein Ergebnis.
  fertig_am         TEXT,
  -- Alle frueheren Fassungen dieser Szene, durch
  -- szenenfolge.FASSUNGSTRENNER getrennt. "Passt, aber anders" schreibt die
  -- Szene neu -- die alte Fassung wird dabei nicht weggeworfen: eine Gruppe,
  -- die um 16 Uhr merkt, dass die erste Fassung besser war, hat sie sonst
  -- nirgends mehr.
  fruehere_fassungen TEXT,
  geaendert_am      TEXT NOT NULL,
  entfernt_am       TEXT                    -- gesetzt = weich geloescht (N3)
);
CREATE INDEX IF NOT EXISTS idx_szene_aktuell ON szene(chat_id, geaendert_am DESC);

-- Jede Fassung einer Szene, nur angehaengt (06.09.2026).
--
-- Bis dahin ersetzte jeder Szenenlauf den Volltext. Die Gruppe konnte nicht
-- zurueck, und in der Probe will man zwei Fassungen nebeneinander lesen.
-- Seitdem schreibt jeder erfolgreiche Lauf seine Fassung ZUSAETZLICH hierher;
-- ``szene.volltext`` bleibt genau wie bisher die aktuelle Fassung, damit kein
-- Aufrufer ausserhalb etwas anderes lesen muss.
--
-- Dasselbe Prinzip wie beim Journal: **nur anhaengen, nie aendern, nie
-- loeschen**. Deshalb gibt es hier kein ``entfernt_am`` und keine
-- Aktualisierungsfunktion in repo.py.
--
-- ``nummer`` zaehlt je Szene fortlaufend ab 1. ``volltext`` ist der Text, den
-- der Lauf geliefert hat -- in Phase 6 die Prosafassung der Geschichte, im
-- Feinschliff der Theatertext; welcher es war, sagt die Szene selbst.
-- ``anders_gemacht`` ist die Pflichtzeile ``Anders gemacht:`` desselben Laufs
-- und dient auf der Gruppenseite als Beschriftung des aufklappbaren Blocks.
CREATE TABLE IF NOT EXISTS szenenfassung (
  id               INTEGER PRIMARY KEY,
  chat_id          INTEGER NOT NULL,
  szene_id         INTEGER NOT NULL,
  nummer           INTEGER NOT NULL,
  volltext         TEXT,
  zusammenfassung  TEXT,
  anders_gemacht   TEXT,
  erstellt_am      TEXT NOT NULL,
  anbieter         TEXT,
  modell           TEXT
);
CREATE INDEX IF NOT EXISTS idx_szenenfassung_szene
  ON szenenfassung(szene_id, nummer);

-- Die Schaerfung am Material (Phase 6, Umbau 05.09.2026 nachts).
--
-- Ein Schema-Aufruf mappt jeden passenden **geprueften** Verdichtungseintrag
-- auf eine Szene und/oder eine Figur; jede Zeile hier ist eine solche
-- Zuordnung samt Begruendung. Additiv (``runde``): die Gruppe darf \"Noch
-- eine Runde\" druecken, dann laeuft das Mapping mit dem geschaerften Stand
-- erneut und schreibt Zeilen mit runde+1 dazu -- die alten bleiben stehen.
-- ``entfernt_am`` ist das weiche Loeschen wie ueberall (N3).
--
-- Die Zitate haengen an den Zuordnungen: sie stehen nicht hier, sondern in
-- ``verdichtung_thema.beleg_zitat`` -- geprueft (``zitat.pruefe``), nie
-- kopiert und nie neu erfunden.
CREATE TABLE IF NOT EXISTS schaerfung (
  id                   INTEGER PRIMARY KEY,
  chat_id              INTEGER NOT NULL,
  verdichtung_thema_id INTEGER NOT NULL,
  szene_id             INTEGER,
  figur_id             INTEGER,
  begruendung          TEXT,
  runde                INTEGER NOT NULL DEFAULT 1,
  uebernommen_am       TEXT,
  erstellt_am          TEXT NOT NULL,
  entfernt_am          TEXT
);
CREATE INDEX IF NOT EXISTS idx_schaerfung_chat ON schaerfung(chat_id, id);

-- Die Pruefung des GANZEN Stuecks (Phase 7, 06.09.2026). Je Runde und Frage
-- eine Zeile: Bewertung 1-5, zwei Saetze Begruendung, EIN Vorschlag, und die
-- Szene, auf die er zeigt (NULL, wenn er keine nennt). Additiv wie alles
-- andere: eine zweite Runde loescht die erste nicht, sie kommt daneben --
-- die Gruppe soll sehen, ob sich etwas gebessert hat.
CREATE TABLE IF NOT EXISTS stueckpruefung (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  runde        INTEGER NOT NULL DEFAULT 1,
  frage        TEXT NOT NULL,
  bewertung    INTEGER,
  begruendung  TEXT,
  vorschlag    TEXT,
  szene_nummer INTEGER,
  erstellt_am  TEXT NOT NULL,
  entfernt_am  TEXT
);
CREATE INDEX IF NOT EXISTS idx_stueckpruefung_chat ON stueckpruefung(chat_id, id);

-- Die Dramaturgie-Pruefung (06.09.2026, interview_theater/dramaturgie/).
--
-- Die feinkoernige Ebene NEBEN der Stueckpruefung: die gibt sechs Noten
-- ueber das ganze Stueck, diese hier gibt einzelne Befunde mit Szene, Figur
-- und Belegzitat -- und **keine Note**. Deshalb eine eigene Tabelle und
-- keine Spalte mehr in ``stueckpruefung``: die beiden beantworten
-- verschiedene Fragen, und eine gemeinsame Zeile haette an der Haelfte der
-- Spalten NULL.
--
-- ``quelle`` trennt die beiden Wege, die hier zusammenlaufen: 'mechanik'
-- (deterministisch gezaehlt, kein Modell) und 'judge' (ein Modellaufruf, eine
-- Frage). ``beleg_geprueft`` ist die Zusage aus Recherche § 4 -- ein Beleg
-- ohne 1 davor hat die Substring-Pruefung NICHT bestanden und darf nirgends
-- angezeigt werden, wo Belegzitate stehen (dieselbe Grenze wie bei
-- ``verdichtung_thema.zitat_geprueft``).
--
-- Additiv wie alles andere: ``runde`` zaehlt hoch, eine zweite Runde
-- loescht die erste nicht.
CREATE TABLE IF NOT EXISTS dramaturgie_befund (
  id             INTEGER PRIMARY KEY,
  chat_id        INTEGER NOT NULL,
  runde          INTEGER NOT NULL DEFAULT 1,
  pruefung       TEXT NOT NULL,            -- b1|a2|a6|c1|namensstabilitaet|…
  szene          INTEGER,
  figur          TEXT,
  schwere        TEXT,                     -- hart|verdacht|hinweis bzw.
                                            -- blocker|hoch|mittel|niedrig
  text           TEXT NOT NULL,
  beleg          TEXT,
  beleg_geprueft INTEGER NOT NULL DEFAULT 0,
  vorschlag      TEXT,
  -- Wohin die Korrektur zeigt (A10/A11, 07.09.2026): 'text' = der Schreiber
  -- zieht nach, 'parameter' = der TEXT hat recht und die Festlegung der
  -- Gruppe ist veraltet. NULL bei jeder anderen Frage.
  --
  -- **Die Spalte ist eine Sperre und keine Notiz.** fanout.auftraege laesst
  -- aus 'parameter' nie einen Schreibauftrag entstehen -- das gaebe den Text
  -- an den Schreiber, damit er ihn auf eine ueberholte Planung
  -- zurueckbiegt, also das Gegenteil des Befunds. Solange die Richtung nur
  -- im Arbeitsspeicher stand, griff diese Sperre nur im frischen Lauf und
  -- nicht mehr, sobald dieselben Befunde aus der Datenbank gelesen wurden
  -- (knoepfe.zeige_dramaturgie, scripts/dramaturgie_pruefen.py und die
  -- Rueckkopplungsschleife tun genau das).
  richtung       TEXT,                     -- text|parameter|NULL
  quelle         TEXT NOT NULL,            -- mechanik|judge
  erstellt_am    TEXT NOT NULL,
  entfernt_am    TEXT
);
CREATE INDEX IF NOT EXISTS idx_dramaturgie_chat ON dramaturgie_befund(chat_id, id);

-- Die Bewertungen einer Dramaturgie-Runde (07.09.2026, die Rueckkopplung).
--
-- **Warum das nicht in ``dramaturgie_befund`` passt.** Dort steht, was
-- schieflaeuft; eine erfuellte Frage erzeugt dort zu Recht keine Zeile
-- (``fanout._befund_aus``: "Score 2 ist kein Befund"). Fuer die Frage, ob eine
-- Ueberarbeitung geholfen hat, ist genau das die falsche Zaehlung: ein guter
-- Text erzeugt keine Befunde, und "null Befunde" heisst dann nicht "besser
-- geworden", sondern "war schon gut". Verglichen werden deshalb die **Scores
-- je Frage und Szene** zwischen zwei Runden -- und dafuer muss auch die Zwei
-- irgendwo stehen.
--
-- ``szene`` ist NULL, wo die Frage dem ganzen Stueck gilt (A2, A6, A11 laufen
-- als EIN Aufruf ueber die Synopsen-Kette). Es ist die Adresse, unter der
-- **gefragt** wurde, nicht die, die der Judge in seiner Antwort nennt --
-- sonst haetten zwei Runden verschiedene Schluessel und liessen sich nicht
-- vergleichen.
--
-- Es steht hier **kein Score ohne verifiziertes Belegzitat**: ein verworfener
-- Score (``beleg.Belegstand.unsicher``) ist keine schlechtere Note, er ist
-- keine, und eine Bilanz aus verworfenen Noten waere eine erfundene Messung.
-- Deshalb ist ``score`` NOT NULL.
--
-- Kein ``entfernt_am``: das ist eine Messung und keine Festlegung der Gruppe;
-- was gemessen wurde, wird nicht zurueckgenommen (wie ``aufruf``).
CREATE TABLE IF NOT EXISTS dramaturgie_bewertung (
  id          INTEGER PRIMARY KEY,
  chat_id     INTEGER NOT NULL,
  runde       INTEGER NOT NULL,
  pruefung    TEXT NOT NULL,              -- b1|a2|a6|a9|a10|a11|c1
  szene       INTEGER,                    -- NULL = die Frage gilt dem Stueck
  score       INTEGER NOT NULL,           -- 0|1|2
  erstellt_am TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dramaturgie_bewertung_chat
  ON dramaturgie_bewertung(chat_id, runde);

-- Wer in einer Szene vorkommt: nur Figuren aus dem Arbeitsstand, deshalb eine
-- Verknuepfung und keine Namensliste in einem Textfeld. Eine weich geloeschte
-- Figur verschwindet damit von selbst aus jeder Szene (repo.szene_figuren
-- filtert ueber figur.entfernt_am), ohne dass irgendwo aufgeraeumt werden
-- muesste.
CREATE TABLE IF NOT EXISTS szene_figur (
  chat_id    INTEGER NOT NULL,
  szene_id   INTEGER NOT NULL,
  figur_id   INTEGER NOT NULL,
  PRIMARY KEY (szene_id, figur_id)
);

CREATE TABLE IF NOT EXISTS journal (
  id                INTEGER PRIMARY KEY,
  chat_id           INTEGER NOT NULL,
  art               TEXT NOT NULL,          -- vorgeschlagen|verworfen|entschieden|offen
  text              TEXT NOT NULL,
  quelle            TEXT NOT NULL,          -- extraktor|befehl
  bis_message_id    INTEGER,
  erstellt_am       TEXT NOT NULL,
  -- Weiches Loeschen (NACHTRAG-weboberflaeche-und-sprache.md N3): das Journal
  -- bleibt nur-anhaengend, ein zurueckgenommener Eintrag wird nicht geloescht,
  -- sondern hier gestempelt -- und ein neuer Eintrag "Zurueckgenommen: ..."
  -- haelt den Weg sichtbar.
  entfernt_am       TEXT
);
CREATE INDEX IF NOT EXISTS idx_journal_chat ON journal(chat_id, id);

-- Die Auffangtabelle fuer alles, was die Gruppe festlegt und wofuer es kein
-- Feld gibt (06.09.2026, docs/analyse-phase4-datenverlust-2026-09-06.md).
--
-- Der Befund dahinter: von 42 Festlegungen einer Gruppe in Phase 4 sind 22
-- verloren. Das Schema kennt nur einen festen Satz vorab definierter Slots
-- (``arbeitsstand.rahmen``, ``figur.beschreibung``, ``szene.ort`` ...); fuer
-- jede relevante Angabe ausserhalb dieses Rasters gab es kein Feld, nur einen
-- ``journal``-Eintrag -- und der faellt nach ``kontext.JOURNAL_EINTRAEGE``
-- weiteren Zeilen aus dem Prompt und kommt nie zurueck. Verloren gingen so
-- unter anderem: die Gruppenzugehoerigkeit jeder Figur, die Herkuenfte, die
-- Vorgabe "nur eine Szene, erste Folge einer Serie" und die Laengenvorgabe
-- fuer die Szenentexte.
--
-- **Bewusst NICHT im ``journal``.** Das Journal ist per AGENTS.md eine
-- CHRONIK ("nur-anhaengend, es gibt bewusst kein aktualisiere_journal") und
-- wird im Kontext gekappt, weil es sonst den Prompt flutet. Eine Festlegung
-- braucht das Gegenteil: sie soll vollstaendig und dauerhaft mitgehen.
-- Beides in einer Tabelle zu mischen erzwingt genau die Kappung, die den
-- Verlust erzeugt hat.
--
-- Nur-anhaengend wie das Journal, weiches Loeschen ueber ``entfernt_am``
-- (N3) -- das ist hier Pflicht und nicht Kuer: eine veraltete Festlegung
-- ("ein zweiter Ort ist die Schule", elf Minuten nach ihrer Ruecknahme
-- geschrieben) erbt sonst den alten Fehler.
CREATE TABLE IF NOT EXISTS festlegung (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  -- figur|gruppe|ort|struktur|form|stil|sonstiges (repo.FESTLEGUNG_BEREICHE).
  -- Bewusst KEIN Name eines bestehenden Arbeitsstandfeldes: was in ein Feld
  -- passt, gehoert ins Feld -- sonst stuende derselbe Fakt an zwei Stellen
  -- und beide widerspraechen sich irgendwann (Analyse § 4.4 Risiko 2).
  bereich      TEXT NOT NULL,
  -- Worauf sie sich bezieht: Figurenname, Gruppenname, Szenennummer. Optional
  -- -- eine Strukturfestlegung ("nur eine Szene") bezieht sich auf alles.
  bezug        TEXT,
  text         TEXT NOT NULL,           -- die Festlegung, eine Zeile
  quelle       TEXT NOT NULL,           -- erkenner|befehl|web
  erstellt_am  TEXT NOT NULL,
  entfernt_am  TEXT                     -- gesetzt = weich geloescht (N3)
);
CREATE INDEX IF NOT EXISTS idx_festlegung_chat ON festlegung(chat_id, id);

-- Inline-Knoepfe (05.09.2026, interview_theater/knoepfe.py).
--
-- Warum eine eigene Tabelle: Telegram begrenzt `callback_data` auf 64 Bytes.
-- Ein Kernthema-Vorschlag ist regelmaessig laenger als das -- also traegt der
-- Knopf nur seine eigene id (`k:<id>`, hoechstens 21 Bytes), und der
-- eigentliche Wert steht hier. Damit steht ausserdem KEIN Inhalt der Gruppe
-- in einem Feld, das ueber Telegram-Buttons hin- und herwandert.
--
-- `benutzt_am` ist die Idempotenz-Sperre: der Druck wird per
-- `UPDATE ... WHERE benutzt_am IS NULL` beansprucht, und nur wer diesen einen
-- UPDATE gewinnt, fuehrt die Wirkung aus. Zweimal tippen (oder zwei Leute
-- gleichzeitig) legt damit nichts doppelt an.
CREATE TABLE IF NOT EXISTS knopf (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  art          TEXT NOT NULL,            -- kernthema|aufnahme|phase|format|
                                          -- szenenform|szene_usa
  wert         TEXT,                     -- Kernthema-Volltext, Phasennummer,
                                          -- Format, "<nr>:<form>" bzw. ja|nein
  erstellt_am  TEXT NOT NULL,
  benutzt_am   TEXT,                     -- gesetzt = schon gedrueckt
  message_id   INTEGER                   -- Nachricht, unter der er haengt --
                                          -- noetig, um eine alte, ungenutzte
                                          -- Speicher-Leiste abzunehmen
);
CREATE INDEX IF NOT EXISTS idx_knopf_chat ON knopf(chat_id, id);

-- Die Ruecknahme eines Erkennerlaufs (Karte U, 01.10.2026).
--
-- Der Anlass (Birk, 30.09.2026): Korpus und Simulation bilden die echte
-- Chatrealitaet der Studierenden nur begrenzt ab, und ein falsch
-- gespeicherter Wert darf deshalb nicht STILL bleiben. Unter jeder
-- "Notiert:"-Meldung steht seitdem ein Undo-Knopf, und was er
-- wiederherstellt, liegt hier -- **nicht** als Nachbau je Erkenner-Art
-- (das waere eine zweite Wahrheit neben erkenner._wende_*_an), sondern als
-- DIFFERENZ zweier Schnappschuesse um ``erkenner.wende_an`` herum
-- (interview_theater/ruecknahme.py).
--
-- ``meldung`` sind die Zeilen der Notiert-Meldung ohne Kopf -- dieselbe
-- Quelle wie die Meldung selbst (erkenner.undo_zeilen), damit "Rueckgaengig
-- gemacht:" nicht anders klingt als "Notiert:". ``message_id`` ist die
-- Nachricht, unter der der Knopf haengt: nach einer wirksamen Ruecknahme
-- werden ihre Grundleisten-Knoepfe verfallen gelassen, sonst schriebe
-- "Ja, speichern" den gerade zurueckgenommenen Wert wieder (der Wert steckt
-- im Knopf). ``zurueckgenommen_am`` ist die zweite Idempotenz-Sperre neben
-- ``knopf.benutzt_am`` -- bedingtes UPDATE in derselben Transaktion wie die
-- Ruecknahme, SQLite entscheidet.
CREATE TABLE IF NOT EXISTS erkenner_lauf (
  id                  INTEGER PRIMARY KEY,
  chat_id             INTEGER NOT NULL,
  meldung             TEXT,
  message_id          INTEGER,
  erstellt_am         TEXT NOT NULL,
  zurueckgenommen_am  TEXT
);
CREATE INDEX IF NOT EXISTS idx_erkenner_lauf_chat ON erkenner_lauf(chat_id, id);

-- Ein Schritt der Ruecknahme: eine Zeile einer verfolgten Tabelle.
--
-- ``schluessel`` ist das JSON-Objekt der Primaerschluesselspalten
-- (sort_keys, weil ``szene_figur`` einen zusammengesetzten hat),
-- ``vorher``/``nachher`` die JSON-Objekte der verglichenen Spalten.
-- ``art``: ``geaendert`` (beide da), ``angelegt`` (nur nachher -- die
-- Ruecknahme entfernt weich, N3) oder ``geloescht`` (nur vorher -- die
-- Ruecknahme fuegt wieder ein; im Betrieb nur bei ``szene_figur``,
-- repo.setze_szene_figuren loescht dort hart).
--
-- ``nachher`` ist zugleich die "Seitdem geaendert"-Probe: stimmt der
-- aktuelle Wert nicht mehr damit, wird NICHTS geaendert.
CREATE TABLE IF NOT EXISTS erkenner_lauf_schritt (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER NOT NULL,
  lauf_id      INTEGER NOT NULL,
  tabelle      TEXT NOT NULL,
  schluessel   TEXT NOT NULL,
  art          TEXT NOT NULL,           -- geaendert|angelegt|geloescht
  vorher       TEXT,
  nachher      TEXT,
  erstellt_am  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_erkenner_lauf_schritt_lauf
  ON erkenner_lauf_schritt(lauf_id);

-- Der Web-Kanal (30.09.2026, Karte Padua A2): der Webserver ist fuer den Bot
-- das, was Telegrams Server heute ist. Browser-Ereignisse liegen hier als
-- Eingang ('ein'), Bot-Ausgaben als Ausgang ('aus').
--
-- EINE Tabelle fuer beide Richtungen, und das ist der Kern: ``id`` ist
-- zugleich die ``message_id`` und die ``update_id``. Zaehlten Gruppe und Bot
-- in getrennten Folgen, laege jede Gruppennachricht ab dem zweiten Zug unter
-- dem Wasserzeichen ``gruppe.letzte_beantwortete_message_id``, und der Bot
-- beantwortete sie nie (gemessen in simulation/attrappe.naechste_message_id).
-- Telegram vergibt die ids ebenfalls fortlaufend je Chat, ueber alle Absender.
--
-- Die Tippanzeige steht NICHT hier, sondern in gruppe.web_tippt_bis:
-- arbeitszeilen.TIPP_S = 4,0 s heisst bei einem vierminuetigen Szenenlauf 60
-- Aufrufe, und eine Tippanzeige ist keine Nachricht.
--
-- AUTOINCREMENT (Abschlussreview I2): ohne es vergaebe SQLite nach dem
-- Loeschweg einer Gruppe (loesche_gruppe nimmt ihre Zeilen) die frei
-- gewordenen hoechsten ids erneut -- und eine neue Zeile laege unter dem
-- Offset eines Bots, der die alte schon gesehen hat. Eine schon angelegte
-- Tabelle aendert CREATE TABLE IF NOT EXISTS nicht; das betrifft nur
-- Entwicklungs-DBs dieser Karte (die Tabelle ist neu), und
-- repo.hoechste_web_post_id faellt dort auf MAX(id) zurueck.
CREATE TABLE IF NOT EXISTS web_post (
  id                INTEGER PRIMARY KEY AUTOINCREMENT, -- = message_id = update_id
  chat_id           INTEGER NOT NULL,
  richtung          TEXT NOT NULL,              -- 'ein' (Browser) | 'aus' (Bot)
  -- 'ein': text|sprache|knopf|befehl -- 'aus': text|datei
  -- 'befehl' ist ein Umschalter-Druck, der als Slash-Text in den Bot geht und
  -- in der Chatansicht verborgen bleibt: Slash-Befehle werden nicht beworben.
  typ               TEXT NOT NULL,
  text              TEXT,
  knoepfe           TEXT,                       -- JSON [[beschriftung, daten], ...]
  daten             TEXT,                       -- 'knopf': die callback_data
  bezug_message_id  INTEGER,                    -- 'knopf': unter welcher Nachricht
  antwort           TEXT,                       -- 'knopf': answerCallbackQuery-Text
  dauer             INTEGER,                    -- 'sprache': Sekunden vom Client
  datei             TEXT,                       -- 'sprache'/'datei': Pfad
  mime              TEXT,
  dateiname         TEXT,                       -- 'datei': Name fuer den Download
  geloescht_am      TEXT,                       -- loesche_nachrichten, weich
  erstellt_am       TEXT NOT NULL,
  -- Aenderungszaehler: jede Aenderung an einer schon geschriebenen Zeile
  -- (aendere_text, Leiste tauschen/entfernen, loeschen) setzt ihn auf
  -- MAX+1 ueber die ganze Tabelle. Ein Zaehler und keine Uhrzeit: SQLite
  -- serialisiert die Schreiber, der Wert steigt also in Commit-Reihenfolge,
  -- und der Poll der Chatansicht ("alles nach N") verpasst nichts. NULL =
  -- nie geaendert (neue Zeilen holt der Poll ueber die id).
  aenderung         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_web_post_eingang
  ON web_post(chat_id, richtung, id);

-- Was das Dashboard rot färbt
CREATE TABLE IF NOT EXISTS vorfall (
  id           INTEGER PRIMARY KEY,
  chat_id      INTEGER,                     -- NULL bei bot-weiten Vorfällen
  bot_name     TEXT,
  art          TEXT NOT NULL,               -- kontext_gekuerzt|fenster_verworfen|extraktor_fehler|
                                            -- zitat_ungeprueft|http_5xx|abgeschnitten|…
  stufe        INTEGER,
  detail       TEXT,
  erstellt_am  TEXT NOT NULL
);

-- Selbstkorrektur der Token-Schätzung
CREATE TABLE IF NOT EXISTS aufruf (
  id                     INTEGER PRIMARY KEY,
  chat_id                INTEGER,
  art                    TEXT NOT NULL,     -- gespraech|verdichter|extraktor|stt|dramaturgie_*
  modus                  TEXT,              -- A|B|C (C = Claude ueber den Proxy)
  geschaetzte_token      INTEGER,
  tatsaechliche_token    INTEGER,           -- usage.prompt_tokens
  antwort_token          INTEGER,
  finish_reason          TEXT,
  dauer_ms               INTEGER,
  erfolg                 INTEGER,
  -- Was wirklich lief. Aus ``art`` folgt das Modell nicht: LLM.schema
  -- waehlt es je Aufruf (Erkenner gemma, Gespraech Kimi, beide modus 'A').
  modell                 TEXT,
  -- Beim Buchen gerechnet, nicht beim Lesen (30.09.2026, Karte Padua S):
  -- eine Preisaenderung soll alte Zeilen nicht ruecktdatieren. NULL heisst
  -- "aus der Zeit davor" und zaehlt als 0.
  kosten_chf             REAL,
  erstellt_am            TEXT NOT NULL
);
"""

# Alle Tabellen mit chat_id -- Grundlage der Loeschzusage (§ 3, global-constraints.md).
TABELLEN_MIT_CHAT_ID = (
    "gruppe",
    "nachricht",
    "aufnahme",
    "verdichtung",
    "verdichtung_thema",
    "verdichtung_begriff",
    "kernzitat",
    "arbeitsstand",
    "figur",
    "szene",
    "szene_figur",
    "szenenfassung",
    "schaerfung",
    "stueckpruefung",
    "dramaturgie_befund",
    "dramaturgie_bewertung",
    "journal",
    "festlegung",
    "knopf",
    # Karte U (01.10.2026): die Ruecknahme eines Erkennerlaufs.
    "erkenner_lauf",
    "erkenner_lauf_schritt",
    "web_post",
    "vorfall",
    "aufruf",
)


def verbinde(pfad: str) -> sqlite3.Connection:
    """Baut eine Verbindung mit den projektweiten PRAGMAs auf (global-constraints.md § 3)."""
    conn = sqlite3.connect(pfad, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


#: Zeilenanfaenge, die keine Spalte sind, sondern eine Tabellen-Constraint
#: (z. B. ``PRIMARY KEY (chat_id, message_id)`` in ``nachricht``) -- die
#: Migration unten darf so eine Zeile nicht als fehlende Spalte missverstehen
#: und per ALTER TABLE anzulegen versuchen.
_KEINE_SPALTE_PRAEFIXE = ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT")


def _tabellenspalten_aus_schema() -> dict[str, list[tuple[str, str]]]:
    """Liest Tabellen- und Sollspalten direkt aus SCHEMA statt aus einem
    zweiten, von Hand gepflegten Katalog -- der koennte sonst aus dem Tritt
    geraten, sobald jemand nur SCHEMA aendert. Liefert je Tabelle eine Liste
    aus (Spaltenname, Rest-Definition-fuer-ALTER-TABLE)."""
    ergebnis: dict[str, list[tuple[str, str]]] = {}
    for tabelle, koerper in re.findall(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", SCHEMA, re.DOTALL
    ):
        spalten = []
        for zeile in koerper.splitlines():
            zeile = zeile.split("--", 1)[0].strip().rstrip(",")
            if not zeile or zeile.upper().startswith(_KEINE_SPALTE_PRAEFIXE):
                continue
            name, _, definition = zeile.partition(" ")
            spalten.append((name, definition.strip()))
        ergebnis[tabelle] = spalten
    return ergebnis


def _migriere_fehlende_spalten(conn: sqlite3.Connection) -> None:
    """Ergaenzt in einer schon bestehenden Datenbank Spalten, die im SCHEMA
    seither hinzugekommen sind (z. B. gruppe.interviewmodus_seit, teil-b.md
    Aufgabe 5) -- per ``ALTER TABLE ... ADD COLUMN``, allgemein anhand eines
    Vergleichs Soll- (SCHEMA) gegen Ist-Spalten (``PRAGMA table_info``), nicht
    als Einzelfall fuer genau eine Spalte. Ohne das braeche jede Datenbank,
    die vor einer Schemaerweiterung angelegt wurde -- schon vorhandene Spalten
    werden stillschweigend uebersprungen."""
    for tabelle, spalten in _tabellenspalten_aus_schema().items():
        vorhandene = {zeile[1] for zeile in conn.execute(f"PRAGMA table_info({tabelle})")}
        for name, definition in spalten:
            if name in vorhandene:
                continue
            conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {name} {definition}")
    conn.commit()


#: Schemastand dieser Codefassung, gespeichert in ``PRAGMA user_version``.
#: ``0`` ist eine Datenbank aus der Zeit vor der Umnummerierung der
#: Arbeitsphasen (05.09.2026), ``1`` das siebenstufige Modell desselben Tages,
#: ``2`` das achtstufige nach dem Umbau \"erst erfinden, dann schaerfen\"
#: (05.09.2026 nachts). Bewusst SQLites eingebauter Zaehler und keine eigene
#: Tabelle: er kostet keine Zeile, keine Migration und kein Schema.
#: ``3`` ist das siebenstufige Modell vom 06.09.2026 (Setting, Figuren und
#: Geschichte wurden EINE Phase, aus dem Durchlauf wurde die Schaerfung des
#: Stuecks).
SCHEMA_VERSION = 3

#: Acht Phasen wurden sieben (Birk, 05.09.2026): Kernthema und Figuren sind
#: EINE Phase geworden, alles darueber rutscht um eins nach unten. 1-4 bleiben,
#: wo sie sind -- aus alt 4 (Kernthema) wird das neue 4 (Kernthema & Figuren),
#: aus alt 5 (Figuren) ebenfalls. Alt -> neu, siehe
#: interview_theater/phasen.py.
PHASEN_UMNUMMERIERUNG = {5: 4, 6: 5, 7: 6, 8: 7}

#: Sieben Phasen wurden acht (Birk, 05.09.2026 nachts): aus \"4 Kernthema &
#: Figuren · 5 Rahmen · 6 Szenen · 7 Durchlauf\" wird \"4 Setting & Figuren ·
#: 5 Geschichte · 6 Schaerfung · 7 Szenentexte · 8 Durchlauf\".
#:
#: 4 bleibt 4 (dort wird weiter Setting und Figurenarbeit gemacht), **5 bleibt
#: 5**: die alte 5 war der Rahmen -- der ist jetzt Teil von 4, aber eine
#: Gruppe, die dort steht, hat den Rahmen gerade in der Hand und ist damit
#: naeher an der neuen 5 (Geschichte) als an irgendetwas anderem. Aus 6
#: (Szenen) wird 7 (Szenentexte), aus 7 (Durchlauf) wird 8. Die Schaerfung (6)
#: ist neu und wird niemandem zugewiesen: sie ist ein Angebot, keine Station,
#: die jemand uebersprungen haette.
PHASEN_UMNUMMERIERUNG_2 = {6: 7, 7: 8}

#: Acht Phasen wurden wieder sieben (Birk, 06.09.2026, 09:20): **Setting &
#: Figuren (4) und Geschichte (5) sind EINE Station**, alles darueber rutscht
#: um eins nach unten. 4 bleibt 4, aus 5 wird ebenfalls 4 (dieselbe Arbeit,
#: nur ohne Zaesur dazwischen), aus 6 (Schaerfung) wird 5, aus 7
#: (Szenentexte) 6, aus 8 (Durchlauf) 7 -- das jetzt "Schaerfung des
#: Stuecks" heisst und den Stueck-Judge traegt.
PHASEN_UMNUMMERIERUNG_3 = {5: 4, 6: 5, 7: 6, 8: 7}


def _rechne_phasen_um(conn: sqlite3.Connection, umnummerierung: dict[int, int]) -> None:
    """Rechnet ``arbeitsstand.phase`` und ``phase_angeboten`` nach einer
    Tabelle alt -> neu um -- ein einziges UPDATE je Spalte mit CASE, damit
    die Umrechnung nicht kaskadiert (6 -> 7, danach 7 -> 8 wuerde sonst die
    gerade geschriebenen Zeilen wieder anfassen)."""
    faelle = " ".join(f"WHEN {alt} THEN {neu}" for alt, neu in umnummerierung.items())
    betroffen = ", ".join(str(alt) for alt in umnummerierung)
    for spalte in ("phase", "phase_angeboten"):
        conn.execute(
            f"UPDATE arbeitsstand SET {spalte} = CASE {spalte} {faelle} END "
            f"WHERE {spalte} IN ({betroffen})"
        )


def _migriere_phasennummern(conn: sqlite3.Connection) -> None:
    """Rechnet gespeicherte Phasennummern einmalig auf das siebenstufige
    Modell (04.09.), danach auf das achtstufige (05.09. nachts) und danach
    auf das siebenstufige von heute um (PHASEN_UMNUMMERIERUNG,
    PHASEN_UMNUMMERIERUNG_2, PHASEN_UMNUMMERIERUNG_3).

    Betrifft ``arbeitsstand.phase`` und ``arbeitsstand.phase_angeboten``:
    ohne diesen Schritt saehe eine Gruppe, die abends bei "8 · Durchlauf"
    aufgehoert hat, am naechsten Morgen eine Phasennummer, die es nicht mehr
    gibt -- und der Prompt-Zusatz dazu fehlte ersatzlos.

    **Stufenweise und je Stufe genau einmal**: eine Datenbank aus der Zeit vor
    allen Umbauten (``user_version = 0``) laeuft durch alle drei Tabellen,
    eine vom 04.09. (``1``) noch durch zwei, eine von heute Nacht (``2``) nur
    noch durch die dritte, und eine aktuelle (``3``) durch keine. Der
    Merkposten ist ``PRAGMA user_version``.

    Das Journal bleibt unberuehrt: dort steht, was die Gruppe damals
    entschieden hat ("Phase 5 · Figuren"), und das ist auch nach der
    Umnummerierung wahr -- ein Journal wird nur angehaengt, nie umgeschrieben
    (AGENTS.md)."""
    stand = conn.execute("PRAGMA user_version").fetchone()[0]
    if stand >= SCHEMA_VERSION:
        return
    if stand < 1:
        _rechne_phasen_um(conn, PHASEN_UMNUMMERIERUNG)
    if stand < 2:
        _rechne_phasen_um(conn, PHASEN_UMNUMMERIERUNG_2)
    if stand < 3:
        _rechne_phasen_um(conn, PHASEN_UMNUMMERIERUNG_3)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def _migriere_erste_szenenfassung(conn: sqlite3.Connection) -> int:
    """Gibt jeder bestehenden Szene mit Volltext **eine** Fassung Nummer 1
    mit dem vorhandenen Text (06.09.2026). Liefert, wie viele angelegt wurden.

    Der Grund ist die Ansicht: „Fruehere Fassungen" darf nicht leer aussehen,
    wo es einen Text gibt, nur weil er vor dieser Aenderung entstanden ist.

    **Idempotent** ueber das ``NOT EXISTS`` -- eine Szene, die schon eine
    Fassung hat, bekommt keine zweite. Kein ``user_version``-Schritt und kein
    eigener Merkposten: die Bedingung ist die Datenlage selbst, und damit
    laeuft die Migration auch fuer eine Szene richtig, die erst spaeter aus
    einem Import dazukommt.

    Kein Zeitstempel geraten: ``erstellt_am`` ist ``szene.geaendert_am`` --
    der Moment, in dem dieser Text entstanden ist. Anbieter und Modell
    bleiben NULL: sie sind fuer die alten Fassungen nicht mehr feststellbar,
    und eine Vermutung im Feld waere schlechter als eine Leerstelle."""
    cur = conn.execute(
        """
        INSERT INTO szenenfassung
            (chat_id, szene_id, nummer, volltext, zusammenfassung, erstellt_am)
        SELECT s.chat_id, s.id, 1, s.volltext, s.zusammenfassung, s.geaendert_am
        FROM szene s
        WHERE trim(coalesce(s.volltext, '')) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM szenenfassung f WHERE f.szene_id = s.id
          )
        """
    )
    conn.commit()
    return cur.rowcount


def initialisiere(conn: sqlite3.Connection) -> None:
    """Legt das Schema an, falls noch nicht vorhanden, ergaenzt in einer schon
    vorhandenen Datenbank fehlende Spalten (siehe _migriere_fehlende_spalten)
    rechnet einmalig die Phasennummern um (_migriere_phasennummern) und legt
    fuer bestehende Szenentexte die erste Fassung an
    (_migriere_erste_szenenfassung).

    Reihenfolge: erst die Spalten, dann ihr Inhalt -- ``phase_angeboten``
    koennte in einer sehr alten Datenbank noch gar nicht existieren, und
    ``szene.zusammenfassung`` ebenfalls."""
    conn.executescript(SCHEMA)
    conn.commit()
    _migriere_fehlende_spalten(conn)
    _migriere_phasennummern(conn)
    _migriere_erste_szenenfassung(conn)


def loesche_gruppe(conn: sqlite3.Connection, chat_id: int) -> None:
    """Loescht alle Datensaetze einer Gruppe (Loeschzusage). Das Audioverzeichnis
    liegt ausserhalb der Datenbank und wird von scripts/loeschen.py entfernt."""
    for tabelle in TABELLEN_MIT_CHAT_ID:
        conn.execute(f"DELETE FROM {tabelle} WHERE chat_id = ?", (chat_id,))
    conn.commit()

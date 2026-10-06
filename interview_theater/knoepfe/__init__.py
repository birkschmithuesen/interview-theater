"""Inline-Knoepfe fuer die Auswahl-Momente (05.09.2026).

**Warum es das gibt.** Die Sprachnavigation ist an Auswahl-Momenten
unzuverlaessig -- gemessen am 05.09.2026: der Absichtserkenner
(``erkenner.py``) erkennt eine Kernthema-Festlegung zuverlaessig, wenn er das
ganze Gespraech sieht (3/3), aber live sieht er nur ein Fenster von ein bis
drei Nachrichten. Im Fenster mit der Zustimmung schrieb er ``entschieden``
(eine Journalnotiz) statt ``kernthema_setzen`` (ein Arbeitsstand-Feld). Die
Festlegung landete deshalb nicht in der Datenbank und erschien nicht auf der
Weboberflaeche.

Ein Knopf traegt die Auswahl selbst -- es ist nichts zu erraten. Genau dafuer,
und nur dafuer, sind Knoepfe hier gedacht: **Stellen, an denen die Gruppe aus
wenigen benannten Moeglichkeiten waehlt** (Kernthema, Aufnahme an/aus,
naechste Phase, Form und Stil je Szene, USA-Einwilligung). Alles andere --
Begriffe, Fragen, Figurenbeschreibungen -- bleibt bewusst Sprache: dort gibt
es keine Liste, aus der sich waehlen liesse.

**Drei Zusagen, an denen sich dieser Code messen laesst:**

1. ``callback_data`` bleibt unter 64 Bytes (Telegram-Grenze). Ein Knopf traegt
   nur ``k:<id>`` -- der eigentliche Wert (ein Kernthema kann laenger sein als
   die ganze Grenze) steht in der Tabelle ``knopf``. Geprueft wird die Grenze
   in ``telegram.Telegram.sende_mit_knoepfen``, nicht hier.
2. **Kein Modellaufruf.** Wie bei den Slash-Befehlen (``befehle.py``) greift
   ein Knopf frueh und deterministisch: ``bot.schleife`` gibt ihn ab, bevor
   irgendein Kontext gebaut wird. Was ein Modell braucht, geht wie ueberall an
   einen eigenen Thread (``basis._starte_auftrag``).
3. **Idempotent.** Jeder Druck wird ueber ``repo.beanspruche_knopf``
   beansprucht -- ein bedingtes UPDATE, das nur einmal gewinnt. Der zweite
   Druck bekommt eine freundliche Rueckmeldung und loest nichts aus.

``tests/test_knoepfe_struktur.py`` haelt alle drei am Quelltext fest.

**Der Aufbau** (06.09.2026: die Datei war auf 5.500 Zeilen gewachsen und
zerfiel entlang dieser Schichten von selbst). Jede Schicht liest nur nach
unten; die fuenf Aufrufe nach oben stehen als lokaler Import in der Funktion,
die sie braucht:

* ``texte.py`` -- Arten, Wortlaute, Phasennummern, Auftragsvorlagen
* ``basis.py`` -- callback_data, Grundleiste, Speicherweg, Auftragsabgabe
* ``fragen.py`` -- Phase 2
* ``figuren.py`` -- Phase 4
* ``szenen.py`` -- Phasen 5 bis 8
* ``interviews.py`` -- Phase 3
* ``stationen.py`` -- der Phasenrahmen im Chat
* ``wirkung.py`` -- die Dispatch-Tabelle und ihre Handler

Dieses ``__init__`` re-exportiert die vollstaendige bisherige Modulflaeche,
damit kein Aufrufer angepasst werden muss: ``knoepfe.behandle``,
``knoepfe.biete_phase_proaktiv``, ``knoepfe.ART_SPEICHERN`` und alles Weitere
sind unveraendert erreichbar.
"""

#: Arten, Wortlaute, Phasennummern, Auftragsvorlagen
from interview_theater.knoepfe.texte import (  # noqa: F401
    ANWEISUNGEN, ANWEISUNG_DUKTUS,
    ANWEISUNG_EROEFFNUNG, ANWEISUNG_FIGURENZAHL, ANWEISUNG_FRAGEN_ANDERE,
    ANWEISUNG_FRAGEN_EIGENE, ANWEISUNG_FRAGE_SCHAERFEN,
    ANWEISUNG_KERNFRAGE, ANWEISUNG_KERNTHEMA,
    ANWEISUNG_NAMEN, ART_ANDERS, ART_AUFNAHME, ART_AUSWERTEN,
    ART_AUSWERTEN_ALLE, ART_DURCHLAUF_SZENE, ART_EIGENE, ART_FIGUREN_ANZAHL,
    ART_FIGUREN_ANZAHL_FREI, ART_FIGUREN_ANZAHL_MENU, ART_FIGUREN_NAMEN_MENU,
    ART_DRAMATURGIE, ART_DRAMATURGIE_LASSEN, ART_DRAMATURGIE_SZENE,
    ART_FASSUNGEN, ART_SPRECHANTEILE,
    ART_FIGUREN_ZUFALL, ART_FIGUR_DUKTUS, ART_FIGUR_DUKTUS_MENU,
    ART_FIGUR_ENTFERNEN, ART_FIGUR_INTERVIEW, ART_FIGUR_INTERVIEW_MENU,
    ART_FIGUR_NAME, ART_FIGUR_NAME_MENU, ART_FIGUR_PASST, ART_FIGUR_STIL,
    ART_FIGUR_STIL_FREI, ART_FRAGEN_ANDERE, ART_FRAGEN_EIGENE,
    ART_FRAGEN_EINZELN, ART_FRAGE_ANNEHMEN, ART_FRAGE_SCHAERFEN,
    ART_FRAGE_VERWERFEN, ART_FRAGEN_WEICH_LASSEN, ART_FRAGEN_WEICH_UEBERNEHMEN,
    ART_FRAGEN_UEBERNEHMEN, ART_FRAGE_WAHL, ART_GESCHICHTE_ANDERS,
    ART_GESCHICHTE_KUERZEN,
    ART_GESCHICHTE_NEU, ART_GESCHICHTE_PASST, ART_GESCHICHTE_SCHREIBEN,
    ART_GESCHICHTE_SPEICHERN, ART_HILFE, ART_INTERVIEWS_FERTIG, ART_KERNTHEMA,
    ART_LEITFADEN,
    ART_NOCH_NICHT, ART_OHNE_KNOPF_FERTIG, ART_OHNE_KNOPF_JA,
    ART_OHNE_KNOPF_NEIN, ART_OHNE_KNOPF_WEITER, ART_PHASE, ART_PRUEFUNG_LASSEN,
    ART_PRUEFUNG_RUNDE, ART_PRUEFUNG_SZENE, ART_RAHMEN, ART_REDO, ART_RICHTUNG,
    ART_SCHAERFUNG_FIGUR, ART_SCHAERFUNG_KEINE, ART_SCHAERFUNG_RUNDE,
    ART_SCHAERFUNG_STELLE, ART_SCHAERFUNG_SZENE, ART_SCHLAG_VOR, ART_SPEICHERN,
    ART_STAND, ART_SZENENFELDER_SPEICHERN, ART_SZENENFOLGE_ANZAHL,
    ART_SZENENFOLGE_ANZAHL_WERT, ART_SZENENFOLGE_REIHENFOLGE,
    ART_SZENENFOLGE_SPEICHERN, ART_SZENENFORM, ART_SZENENSTIL,
    ART_SZENE_ANDERS, ART_SZENE_FORM, ART_SZENE_KUERZEN, ART_SZENE_NAECHSTE,
    ART_SZENE_NEU,
    ART_SZENE_PASST, ART_SZENE_PLANEN, ART_SZENE_SCHREIBEN,
    ART_SZENE_SO_LASSEN, ART_SZENE_UEBERSPRINGEN, ART_SZENE_USA,
    ART_SZENE_ZEIGEN, ART_TEIL_FERTIG, ART_TEIL_WEITER, ART_TEXTBUCH,
    ART_TRANSKRIPT, ART_UEBERSICHT_ANDERS, ART_UEBERSICHT_PASST, ART_UNDO,
    ART_WIR_ZUERST, ART_ZUSAMMENFASSUNG, FIGURENZAHLEN,
    FIGURENZAHL_MAX, FIGURENZAHL_MIN, FRAGEN_JE_BEGRIFF,
    MAX_AUSWAHL, MAX_VORSCHLAEGE,
    MENUE_KNOPF_LAENGE, PHASE_DURCHLAUF, PHASE_GESCHICHTE, PHASE_INTERVIEWS,
    PHASE_RAHMEN, PHASE_SCHAERFUNG, PHASE_SETTING, PHASE_STUECKPRUEFUNG,
    PHASE_SZENEN, PRAEFIX, TEXT_ABLAUF, TEXT_ANDERS_KNOPF, TEXT_ANZAHL_KNOPF,
    TEXT_ARBEIT_EROEFFNUNG,
    TEXT_DURCHLAUF_SZENE_KNOPF, TEXT_EIGENE_IDEE_KNOPF,
    TEXT_FORM_VORSCHLAG_ZUSATZ, TEXT_GESCHICHTE_SCHREIBEN_KNOPF,
    TEXT_KUERZEN_KNOPF,
    TEXT_NAECHSTE_KNOPF, TEXT_NEU_KNOPF, TEXT_PASST_KNOPF,
    TEXT_REIHENFOLGE_KNOPF, TEXT_SCHAERFUNG_RUNDE_KNOPF,
    TEXT_SZENE_FORM_KNOPF, TEXT_SZENE_PLANEN_KNOPF, TEXT_SZENE_SCHREIBEN_KNOPF,
    TEXT_SZENE_SO_LASSEN_KNOPF, TEXT_SZENE_UEBERSPRINGEN_KNOPF,
    TEXT_DRAMATURGIE_KNOPF, TEXT_FASSUNGEN_KNOPF, TEXT_SPRECHANTEILE_KNOPF,
    TEXT_TEXTBUCH_KNOPF, TEXT_WEITER_KNOPF, TRENNER, _ANWEISUNG_ALLGEMEIN,
    _AUSWAHLMARKER, _ERSTER_ALS_WERT, _FELD_FUER, _KETTE, _NOTIERT,
    _TEXT_ANDERS, _TEXT_ANDERS_KNOPF, _TEXT_ANZAHL_FRAGE,
    _TEXT_ARBEITSSTAND_HINWEIS,
    _TEXT_AUFNAHME_BEENDEN, _TEXT_AUFNAHME_STARTEN, _TEXT_AUSWERTEN_ALLE_KNOPF,
    _TEXT_AUSWERTEN_ALLE_LAEUFT, _TEXT_AUSWERTEN_ALLE_NICHTS,
    _TEXT_AUSWERTEN_KNOPF, _TEXT_AUSWERTEN_UNBEKANNT,
    _TEXT_AUSWERTEN_UNMOEGLICH, _TEXT_DUKTUS_FEHLT, _TEXT_DUKTUS_LAEUFT,
    _TEXT_DUKTUS_OHNE_QUELLE, _TEXT_EIGENE, _TEXT_EIGENE_IDEE,
    _TEXT_EIGENE_KNOPF, _TEXT_FIGURENZAHL_UNKLAR,
    _TEXT_FIGUREN_ANZAHL_ERSTFRAGE, _TEXT_FIGUREN_ANZAHL_FRAGE,
    _TEXT_FIGUREN_ANZAHL_FREI_FRAGE, _TEXT_FIGUREN_ANZAHL_FREI_KNOPF,
    _TEXT_FIGUREN_ANZAHL_KNOPF, _TEXT_FIGUREN_FIXIERT, _TEXT_FIGUREN_KEINE,
    _TEXT_FIGUREN_NAMEN_FRAGE, _TEXT_FIGUREN_NAMEN_KNOPF,
    _TEXT_FIGUREN_ZUFALL_FERTIG, _TEXT_FIGUREN_ZUFALL_KNOPF,
    _TEXT_FIGUREN_ZUFALL_NICHTS_OFFEN, _TEXT_FIGUREN_ZUFALL_OHNE_INTERVIEW,
    _TEXT_FIGUR_DUKTUS_KNOPF, _TEXT_FIGUR_ENTFERNEN_KNOPF,
    _TEXT_FIGUR_INTERVIEW_FRAGE, _TEXT_FIGUR_INTERVIEW_KNOPF,
    _TEXT_FIGUR_PASST_KNOPF, _TEXT_FOLGE_GESPEICHERT, _TEXT_FOLGE_LEER,
    _TEXT_FRAGEN_ANDERE_KNOPF, _TEXT_FRAGEN_EIGENE, _TEXT_FRAGEN_EIGENE_KNOPF,
    _TEXT_FRAGEN_EINZELN_KNOPF, _TEXT_FRAGEN_KEINE_ANGENOMMEN,
    _TEXT_FRAGEN_KEINE_AUSWAHL, _TEXT_FRAGEN_ABGESCHLOSSEN,
    _TEXT_FRAGEN_RICHTUNG_FRAGE, _TEXT_FRAGEN_RICHTUNG_GEFRAGT,
    _TEXT_FRAGE_ANNEHMEN_KNOPF, _TEXT_FRAGE_ENTSCHIEDEN,
    _TEXT_FRAGE_GESCHAERFT, _TEXT_FRAGE_KOPF, _TEXT_FRAGE_KOPF_OHNE_BEGRIFF,
    _TEXT_FRAGE_SCHAERFEN_KNOPF, _TEXT_FRAGE_VERWERFEN_KNOPF,
    _TEXT_FRAGE_WAS_AENDERN, _TEXT_FRAGE_WEICH_HINWEIS,
    _TEXT_FRAGEN_WAHL, _TEXT_GESCHICHTE_ANDERS,
    _TEXT_GESCHICHTE_ANDERS_KNOPF, _TEXT_GESCHICHTE_GESPEICHERT,
    _TEXT_GESCHICHTE_LEER, _TEXT_GESCHICHTE_NEU_KNOPF, _TEXT_GESCHICHTE_PASST,
    _TEXT_DRAMATURGIE_LAEUFT, _TEXT_DRAMATURGIE_LASSEN,
    _TEXT_DRAMATURGIE_LASSEN_KNOPF, _TEXT_DRAMATURGIE_UEBERHOLT,
    _TEXT_DRAMATURGIE_UNBEKANNT,
    _TEXT_FASSUNGEN_KOPF, _TEXT_FASSUNG_KOPF,
    _TEXT_GESCHICHTE_PASST_KNOPF, _TEXT_HILFE_KNOPF,
    _TEXT_INTERVIEWS_FERTIG_KNOPF, _TEXT_INTERVIEWS_NOCH_OFFEN,
    _TEXT_KEINE_FASSUNGEN,
    _TEXT_KEINE_NAECHSTE, _TEXT_NUR_FORMWAHL,
    _TEXT_KEIN_INTERVIEW, _TEXT_KEIN_TRANSKRIPT, _TEXT_KERNTHEMA_FRAGE,
    _TEXT_KERNTHEMA_KEINE, _TEXT_KURZGESCHICHTE_BEREIT, _TEXT_LEITFADEN_KNOPF,
    _TEXT_MENUE_ANDERS_KNOPF, _TEXT_NACH_SPEICHERN_FRAGE,
    _TEXT_NAECHSTE_AUFNAHME_KNOPF, _TEXT_NOCH_NICHT,
    _TEXT_OHNE_KNOPF_FERTIG_KNOPF, _TEXT_OHNE_KNOPF_JA_KNOPF,
    _TEXT_OHNE_KNOPF_NEIN_KNOPF, _TEXT_OHNE_KNOPF_UNBEKANNT,
    _TEXT_OHNE_KNOPF_WEITER, _TEXT_OHNE_KNOPF_WEITER_KNOPF, _TEXT_PASST,
    _TEXT_AENDERN_KNOPF_FUER, _TEXT_PHASE_ANGEBOT, _TEXT_PHASE_NOCH_NICHT_KNOPF,
    _TEXT_PHASE_WEITER,
    _TEXT_PROAKTIV, _TEXT_PROBENANSICHT, _TEXT_PRUEFUNG_LAEUFT,
    _TEXT_PRUEFUNG_LASSEN, _TEXT_PRUEFUNG_LASSEN_KNOPF,
    _TEXT_PRUEFUNG_RUNDE_KNOPF, _TEXT_PRUEFUNG_SZENE_KNOPF,
    _TEXT_PRUEFUNG_UEBERHOLT, _TEXT_PRUEFUNG_UNBEKANNT,
    _TEXT_REIHENFOLGE_FRAGE, _TEXT_RICHTUNG_GESPEICHERT,
    _TEXT_SCHAERFUNG_ALLE_KNOPF, _TEXT_SCHAERFUNG_DURCH,
    _TEXT_SCHAERFUNG_KEINE_KNOPF, _TEXT_SCHAERFUNG_LAEUFT,
    _TEXT_SCHAERFUNG_NICHTS, _TEXT_SCHAERFUNG_STELLE_UEBERNOMMEN,
    _TEXT_SCHAERFUNG_STELLE_UNBEKANNT, _TEXT_SCHAERFUNG_UEBERNOMMEN,
    _TEXT_SCHAERFUNG_VERWORFEN, _TEXT_SCHLAG_VOR_KNOPF, _TEXT_SCHON_BENUTZT,
    _TEXT_SCHON_GESETZT, _TEXT_SPAETERE_GEPRUEFT, _TEXT_SPEICHERN_KNOPF,
    _TEXT_STAND_KNOPF, _TEXT_STIL_EIGENER, _TEXT_STIL_EIGENER_KNOPF,
    _TEXT_STIL_FRAGE, _TEXT_STIL_GESPEICHERT, _TEXT_SZENENFORM_FRAGE,
    _TEXT_SZENE_ANDERS_FRAGE, _TEXT_SZENE_OHNE_TEXT, _TEXT_SZENE_PLANEN_FRAGE,
    _TEXT_SZENE_SO_GELASSEN, _TEXT_SZENE_UEBERSPRUNGEN, _TEXT_SZENE_UNBEKANNT,
    _TEXT_TEIL_FERTIG_KNOPF, _TEXT_TEIL_SCHON_AUS, _TEXT_TEIL_WEITER,
    _TEXT_TEIL_WEITER_KNOPF, _TEXT_TEXTBUCH_BESCHREIBUNG,
    _TEXT_TEXTBUCH_FEHLER, _TEXT_TRANSKRIPT_KNOPF,
    _TEXT_TROTZDEM_AUSWERTEN_KNOPF, _TEXT_UEBERSICHT_FIXIERT,
    _TEXT_UEBERSICHT_WIRD_NEU_ERZEUGT, _TEXT_UNBEKANNT, _TEXT_USA_FRAGE_KNOEPFE,
    _TEXT_USA_JA, _TEXT_USA_JA_KNOPF, _TEXT_USA_NEIN, _TEXT_USA_NEIN_KNOPF,
    _TEXT_WEITER_FRAGE, _TEXT_WIR_ZUERST, _TEXT_WIR_ZUERST_KNOPF,
    _TEXT_ZITATE_VORSPANN, _TEXT_ZUR_GESCHICHTE, _TEXT_ZUSAMMENFASSUNG_KNOPF,
    log,
    ART_STT_SPRACHE, STT_KNOEPFE, T, _JOURNAL_STT_SPRACHE,
    _TEXT_STT_SPRACHE_AUTO, _TEXT_STT_SPRACHE_FRAGE,
    _TEXT_STT_SPRACHE_GESETZT, _TEXT_STT_SPRACHE_KURZ,
    # Karte A1, Aufgabe 10: aus stationen hierher gewandert (K1)
    _ERLEDIGT_FUER,
    # Padua Phasen TEIL 2: die Anzeige nach dem Prueflauf
    ART_ERSTENTWURF, HINWEIS_ZUSAMMENFASSUNG_MAX, _TEXT_ERSTENTWURF,
    _TEXT_ERSTENTWURF_KNOPF, _TEXT_GESCHICHTE_BEREIT, _TEXT_KEIN_ERSTENTWURF,
    _TEXT_SKRIPT_LINK, _TEXT_SKRIPT_TAB, _TEXT_SZENE_BEREIT,
    # Padua Phasen TEIL 2, Task 9: die Sprechweisen in Phase 7
    ART_SPRECHWEISEN_ANDERS, ART_SPRECHWEISEN_PASST,
    _TEXT_SPRECHWEISE_OFFEN, _TEXT_SPRECHWEISEN_AENDERN,
    _TEXT_SPRECHWEISEN_KOPF, _ZEILE_SPRECHWEISE,
)

#: callback_data, Grundleiste, Speicherweg, Auftragsabgabe
from interview_theater.knoepfe.basis import (  # noqa: F401
    _auswahlleiste, _daten, _ein_feld_je_nachricht, _entferne_tastatur,
    _erster_block, _feld_ist_frei, _id_aus_daten, _ist_bestaetigung,
    _kollabiere_letzten_einsamen_undo,
    _leistenwert, _merke_botnachricht, _mit_leiste, _nimm_alte_leiste_ab,
    _phasenknopf, _reduziere_auf_undo, _sende_knoepfe, _sende_menue,
    _sende_mit_grundleiste, _sende_rueckspiegelung,
    _speichere, _starte_auftrag, biete_kernthema, biete_phase, grundleiste,
    kernthema_vorschlaege, offene_art, redo_leiste, sende_mit_speicherleiste,
    sende_notiert_mit_leiste, sende_notiert_nur_undo, speicherleiste,
    undo_leiste,
)

#: Phase 2
from interview_theater.knoepfe.fragen import (  # noqa: F401
    _auswahlfragen, _leitfaden_knopf, _schliesse_fragen_ab,
    _speichere_eroeffnung, _starte_schaerfung, _zeige_frage,
    biete_fragenauswahl, biete_umformulierung, einzeln_aktiv, entscheide,
    fragen_umformulierung_alle_annehmen, fragen_umformulierung_alle_verwerfen,
    frage_fuer_andere_richtung, frage_nach_umformulierung,
    frage_waehlt_schaerfen, frage_warten_auf_richtung,
    frage_weich_lassen, frage_weich_uebernehmen, fragenliste,
    nimm_offene_frage_text, starte_durchgehen, starte_eroeffnung,
    starte_umformulierung, uebernimm_eigene, uebernimm_schaerfung,
    versuche_gegenueberstellung,
)

#: Phase 4
from interview_theater.knoepfe.figuren import (  # noqa: F401
    _INTERVIEWNUMMER, _anzahl_erwartet, _biete_interviews, _entwurfszeilen,
    _ersetze_namen, _figuren_ohne_quelle, _figurenvorstellung, _figurenzeile,
    _interview_aus_zeile, _interviewkoepfe, _kette_weiter,
    _schliesse_figuren_ab, _sende_figurenvorstellung, _uebernimm_figurenliste,
    _zahl_aus, _zitat_belegt, _zufallsknopf, biete_figurenanzahl,
    biete_figurenliste, ebene2_erlaubt, erwarte_figurenanzahl,
    naechste_offene_figur, nimm_figurenanzahl_erwartung,
    ordne_figuren_zufaellig_zu, sende_stil, stelle_figur_vor, stelle_stil_vor,
    uebernimm_figurenanzahl,
)

#: Phasen 5 bis 8
from interview_theater.knoepfe.szenen import (  # noqa: F401
    _biete_weiter_nach_szene, _geschichte_notiz_erwartet, _melde_spaetere,
    _naechste_offene, _pruefbefund, _schreibe_szene, _sende_schaerfungsmenue,
    _speichere_geschichte, _speichere_szenenfelder, _speichere_szenenfolge,
    _szene_mit_nummer, _uebernimm_formwahl, _zeige_fassungen,
    biete_durchlauf,
    biete_kurzgeschichte,
    biete_nach_pruefung, biete_nach_szenentext, biete_schaerfung, biete_szene,
    biete_szene_usa, biete_szenenform, biete_szenenstil, biete_uebersicht,
    erwarte_geschichte_notiz, nimm_geschichte_notiz, probenansicht_zeile,
    sende_geschichte, sende_szenenfelder, sende_szenenfolge, starte_schaerfung,
    starte_dramaturgie,
    starte_stueckpruefung, zeige_dramaturgie, zeige_kurzgeschichte,
    zeige_stueckpruefung,
    zeige_szenentext,
    _leiste_nach_szenentext, skript_verweis, zeige_geprueft_geschichte,
    zeige_geprueft_szene, biete_sprechweisen,
    biete_recherche, starte_fragenvorschlag, starte_recherche_lauf,
)

#: Phase 3
from interview_theater.knoepfe.interviews import (  # noqa: F401
    _aufnahme_anbieten, _auswerten_alle_knopf, _interviewknoepfe,
    _werte_alle_aus, biete_aufnahme, biete_einstieg,
    biete_interview_ohne_knopf, biete_interview_ohne_knopf_weiter,
    biete_nach_aufnahme, biete_nach_teil, biete_stt_sprache,
)

#: der Phasenrahmen im Chat
from interview_theater.knoepfe.stationen import (  # noqa: F401
    _abschlusstext, _mit_vorspann, _sende_abschluss, biete_phase_proaktiv,
    biete_proaktiv, eintritt_in_phase, schliesse_interviews_ab,
    sende_abschluss_statt_meldung,
)

#: die Dispatch-Tabelle und ihre Handler
from interview_theater.knoepfe.wirkung import (  # noqa: F401
    Druck, _WIRKUNGEN, _beantworte, _ohne_knopf_kennung,
    _speichere_kettenglied, _wirke, _wirkung_anders,
    _wirkung_aufnahme, _wirkung_auswerten, _wirkung_auswerten_alle,
    _wirkung_durchlauf_szene, _wirkung_eigene, _wirkung_figur_duktus,
    _wirkung_figur_duktus_menu, _wirkung_figur_entfernen,
    _wirkung_figur_interview, _wirkung_figur_interview_menu,
    _wirkung_figur_name, _wirkung_figur_name_menu, _wirkung_figur_passt,
    _wirkung_figur_stil, _wirkung_figur_stil_frei, _wirkung_figuren_anzahl,
    _wirkung_figuren_anzahl_frei, _wirkung_figuren_anzahl_menu,
    _wirkung_figuren_namen_menu, _wirkung_figuren_zufall, _wirkung_frage_wahl,
    _wirkung_frage_annehmen, _wirkung_frage_schaerfen,
    _wirkung_frage_verwerfen, _wirkung_fragen_einzeln,
    _wirkung_fragen_andere, _wirkung_fragen_eigene, _wirkung_geschichte_anders,
    _wirkung_geschichte_neu, _wirkung_geschichte_passt,
    _wirkung_geschichte_schreiben, _wirkung_geschichte_speichern,
    _wirkung_hilfe, _wirkung_interviews_fertig, _wirkung_kernthema,
    _wirkung_leitfaden,
    _wirkung_noch_nicht, _wirkung_ohne_knopf_fertig, _wirkung_ohne_knopf_ja,
    _wirkung_ohne_knopf_nein, _wirkung_ohne_knopf_weiter, _wirkung_phase,
    _wirkung_pruefung_lassen, _wirkung_pruefung_runde, _wirkung_pruefung_szene,
    _wirkung_rahmen, _wirkung_richtung, _wirkung_schaerfung_figur,
    _wirkung_schaerfung_keine, _wirkung_schaerfung_runde,
    _wirkung_schaerfung_stelle, _wirkung_schaerfung_szene, _wirkung_schlag_vor,
    _wirkung_speichern, _wirkung_stand, _wirkung_szene_anders,
    _wirkung_szene_form, _wirkung_szene_naechste, _wirkung_szene_neu,
    _wirkung_szene_passt, _wirkung_szene_planen, _wirkung_szene_schreiben,
    _wirkung_szene_so_lassen, _wirkung_szene_ueberspringen, _wirkung_szene_usa,
    _wirkung_uebersicht_anders, _wirkung_uebersicht_passt, _wirkung_erstentwurf,
    _wirkung_szene_zeigen, _wirkung_szenenfelder_speichern,
    _wirkung_szenenfolge_anzahl, _wirkung_szenenfolge_anzahl_wert,
    _wirkung_szenenfolge_reihenfolge, _wirkung_szenenfolge_speichern,
    _wirkung_szenenform, _wirkung_szenenstil, _wirkung_teil_fertig,
    _wirkung_dramaturgie, _wirkung_dramaturgie_lassen,
    _wirkung_dramaturgie_szene,
    _wirkung_fassungen, _wirkung_sprechanteile,
    _wirkung_teil_weiter, _wirkung_textbuch, _wirkung_transkript,
    _wirkung_wir_zuerst, _wirkung_zusammenfassung, behandle,
    _wirkung_stt_sprache,
)

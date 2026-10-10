# Task 13 Report

Status: DONE (mit Anmerkungen)

Umgestellt auf stueck.* (Quelle): erkenner._wende_szene_planen_an (planung), erkenner._ziehe_figur_festlegung_nach
(karte_aendern, "erkenner"), befehle._setze_szenenfeld, knoepfe/szenen._speichere_szenenfelder, web_schreiben
(Ort/Besetzung, "web"), entwurf.uebernimm_szenenfelder, szene.uebernimm_rahmen, prueflauf._parameterkorrektur,
szenenfolge.lege_an (Besetzung). repo: NUR_UEBER_STUECK=("ort",); setze_szenenfeld und gleiche_szenenfolge_ab weisen "ort" ab.

Fehlerbehandlung: Gruppe-Quellen (befehle, knoepfe, web) zeigen bei not-ok die Warnung ("Gerade wird noch geschrieben ...")
sichtbar (tg.sende bzw. web Fehler); erkenner-Nachzug und interne Planungsquellen loggen log.warning und zaehlen nicht als geaendert.

Abweichungen vom Brief:
- szenenfolge/kurzgeschichte: kein Aufrufer von gleiche_szenenfolge_ab uebergibt "ort" (kommt nur ueber uebernimm_rahmen), daher kein Ort-Nachzug dort noetig.
- Besetzung bewahrt wer_zusatz (setze_besetzung(zusatz=...) aus der Szene) in erkenner/befehle/knoepfe/entwurf/szenenfolge.
- Tests: ~17 Testvorbereitungen mit setze_szenenfeld(..,"ort",..) auf repo.setze_szenenort bzw. neue Hilfe tests/stueck_hilfe.setze_feld;
  test_ruecknahme_rundreise ignoriert die Protokolltabelle stueck_aenderung (nur anhaengend, wie journal).
- Zusaetzlicher Test: Abgleich weist "ort" ab.

## Fix nach Review 13

- Important 1 (erkenner): `_ziehe_figur_festlegung_nach` gibt die Szenen zurueck, deren Karte `stueck` ablehnte (beschaeftigt); `_wende_festlegung_an` legt sie als `karte_nicht_gezogen` in die Aenderung, `_meldungszeilen` haengt "Karte Szene N noch nicht aktualisiert ..." an die Notiert-Meldung (neue Konstante `_ZEILE_KARTE_NICHT_GEZOGEN`, de/en/it; nicht in `undo_zeilen`). Kein Prompt geaendert.
- Important 2 (Undo): `veraltet` ist jetzt in `ruecknahme.VERFOLGT` (SCHLUESSEL id, AUSSEN id+angeboten_am, HART): eine im Lauf angelegte Marke wird beim Undo geloescht, eine ergaenzte bekommt den alten Grund zurueck, Redo bringt sie wieder. `angeboten_am` ist ausgenommen, sonst scheiterte jedes Undo nach dem Angebot. Wurde die Marke schon entschieden (erledigt_am), meldet der Undo "seitdem geaendert". Rundreise-Faelle mit Volltext + Undo/Redo-Test.
- Minor: `stueck.meldung(ergebnis)` + `_WARNUNG_UNBEKANNTE_SZENE`/`_WARNUNG_UNGUELTIG` (de/en/it) statt roher Codes in web_schreiben/befehle. `setze_ort`/`setze_besetzung` nehmen optional `szene_id` (Web adressiert per id, Szenen ohne Nummer gehen wieder).
- Minor: Waechter `test_stueck_einzige_schreibstelle.py` erkennt Alias-Import, `from interview_theater.repo import ...`, `getattr(repo, ...)` (AST), mit Selbsttest.
- Offen gelassen: Web-Figuren per id->Name->Index (zwei Figuren mit gleichem normalisiertem Namen); AUSNAHMEN-Eintrag szenenkarte.py dateiweit.

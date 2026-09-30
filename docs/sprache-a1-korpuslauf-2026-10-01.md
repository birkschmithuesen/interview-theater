# Erkenner-Korpuslauf Deutsch und Englisch (Karte A1, 2026-10-01)

Modell: `google/gemma-4-31B-it` (Erkenner-Vorgabe), sequenziell, je Fall ein
Aufruf, Wegwerf-Datenbank (`pruefe_prompts` verwirft `IT_DB`).
Stand vor dem Lauf: Commit `27e082f`. Reihenfolge auf Birks Anweisung:
zuerst Englisch (Padua haengt davon ab), dann Deutsch.

Vorher (Birk 30.09.) wurde der **englische** Erkenner-Prompt vereinfacht:
„Chat = nur Befehle/Fragen", kein Nachdenken im Chat (Commits `dbd23f7`,
`243c559`; Prompt 793 → 597 Zeilen, Few-Shots 21 → 18, englischer Korpus
69/29 → 72/31 Faelle/negativ). Der deutsche Prompt ist seit `d8deb6c`
unveraendert (`git diff d8deb6c -- interview_theater/prompts/erkenner.md`
leer).

## Hauptlauf (je ein voller Korpuslauf)

| | Deutsch (`korpus/erkenner.jsonl`) | Englisch (`korpus/en/erkenner.jsonl`), erster Lauf | Englisch, Schlusslauf nach Runde 1 |
|---|---:|---:|---:|
| Faelle (davon negativ) | 150 (53) | 72 (31) | 72 (31) |
| Treffer / erwartet | 110 / 120 | 44 / 44 | 42 / 44 |
| Falsch-Positive (Exit-Kriterium, Soll 0) | **10** | **3** | **2** |
| Falsch-Negative | 10 | 0 | 2 |
| FN in Zustimmungsfaellen (Soll 0) | 0 (von 20) | 0 (von 9) | 0 (von 9) |
| davon FP in Negativfaellen | 1 (n23) | 0 | 0 |
| Token ein / aus | 1 558 102 / 4 405 | 484 859 / 1 780 | 492 995 / 1 692 |
| Kosten CHF (Preise Stand 04.09.2026) | 0.3134 | 0.0977 | 0.0993 |

Zusatzlaeufe: deutsche Wiederholung der FP-Faelle (9 ids × 3) 0.0566 CHF;
englische Runde 1 (38 ids) 0.0522 CHF. **Gesamt rund 0.62 CHF.**

## Befunde

### Deutsch — kein A1-Befund, aber ein Befund fuer Birk

- FP-Faelle: `e20-entschieden-titel`, `e21-entschieden-interviews-auf-deutsch`,
  `e24-figur-und-entschieden`, `n23-phase-plan-fuer-morgen`,
  `s10-go-nach-einer-planung-ist-ein-auftrag`, `fl03-festlegung-gruppe-merkmale`,
  `fl04-festlegung-stil-laenge`, `fl05-festlegung-teilort-neben-dem-setting`,
  `fl09-festlegung-zuruecknehmen` (einer davon mit zwei FP-Eintraegen).
- FN-Faelle: dieselben ohne `n23`/`s10`, dazu `s01-szene-auftrag-mit-nummer`,
  `n26-entfernen-erzaehlte-loeschung`.
- **Keine Modellstreuung:** Schritt 4 verlangte eine Wiederholung
  (`--nur <FP-ids> --wiederholungen 3`). Ergebnis: alle 9 FP-Faelle schlagen
  **3 von 3** Mal wieder an (6/30 Treffer, 30 FP). Das ist systematisch.
- Deutung: fast alles sind **Art-Verwechslungen** zwischen `entschieden`
  und `festlegung_setzen` (in beide Richtungen) — genau die Faelle `fl01`–`fl09`
  und die `entschieden`-Faelle, deren Korpuslauf laut AGENTS.md seit dem
  06.09. „aussteht". Sie waren also nie gemessen. Der deutsche Prompt ist
  unveraendert, Dortmund bleibt bitgleich; A1 fasst ihn deshalb **nicht** an.
  Birk entscheidet, ob Prompt oder Sollwerte nachgezogen werden
  (Folgekarte, eigener Korpuslauf).

### Englisch

- Erster Lauf, 3 FP, alle in Positivfaellen (zusaetzlicher Eintrag neben
  dem richtigen), **kein** Negativfall hat angeschlagen:
  `en-e13-zwei-figuren` (zusaetzlich `phase_setzen`),
  `en-e22-szene-schreiben-nach-planung` (zusaetzlich `szene_planen`; das
  deutsche Gegenstueck `s10` zeigt dasselbe), `en-a06-aufnahme-interviewfrage-imperativ`
  (`an_den_bot` fuer eine Interviewfrage).
- **Runde 1** (Schritt 5; Regeln geschaerft, ein Few-Shot ersetzt, keiner
  hinzugefuegt — nach Birks Prinzip „Chat = nur Befehle/Fragen", keine
  Nachdenken-Ausnahmen): `phase_setzen` nur bei ausdruecklichem
  Phasenwechsel; nach einer Planung ist „write it" nur `szene_schreiben`;
  in einer Aufnahme ist `an_den_bot` nur, was den Bot ruft oder einen
  Bot-Befehl verlangt. Few-Shots 18 → 18, Prompt 597 → 604 Zeilen.
  Nachlauf (2 FP-ids, alle 31 Negativfaelle, 5 beruehrte Positivfaelle):
  10/10, **0 FP**, 0 FN.
- **Schlusslauf** ueber alle 72 Faelle: 42/44, **2 FP**, 2 FN, wieder kein
  Negativfall:
  - `en-e19-verworfen-video`: Art richtig (`verworfen`), aber der Wert ist
    ausfuehrlicher formuliert und enthaelt den Kern des Sollwerts nicht
    woertlich — im ersten Lauf bestand der Fall. Streuung im Wortlaut,
    der Sollwert-Kern ist eng gewaehlt.
  - `en-e20-entschieden-titel`: `festlegung_setzen` statt `entschieden` —
    **dieselbe Verwechslung wie im deutschen `e20`**, also keine
    englische Besonderheit.
- Eine zweite Runde wurde **nicht** gefahren: beide Restfaelle sind keine
  Nachdenken-/Spekulationsfaelle, sondern haengen an derselben offenen
  Frage wie im Deutschen (`entschieden` gegen `festlegung_setzen`) bzw. an
  einem engen Sollwert-Kern. Sie stehen als Befund; **Birk entscheidet vor
  Padua**, ob der Titel einer Szene/eines Stuecks `entschieden` oder
  `festlegung_setzen` ist — die Antwort gilt dann fuer beide Sprachen.
- Die Kennzahl, fuer die der Exit-Code steht (FP = 0), ist auf Englisch
  damit **nicht** erreicht; die Negativfaelle (31, darunter alle Frage-,
  Kritik- und Lobfaelle der Vereinfachung) sind in allen Laeufen sauber.

## Whisper-Rauchtest (Aufgabe 9)

**Offen.** Die Testaufnahmen (Annahme A3) lagen nicht vor; nur der
Skriptteil (`scripts/rauchtest.py --whisper auto|it|en`, Commit `9935d74`)
ist umgesetzt. Annahmen A1/A2 (Autoerkennung ohne `language`-Feld) sind
unbestaetigt. Padua steht auf `whisper = "auto"`; Fallback: Knopfleiste in
Phase 3 bzw. `/sprache` je Gruppe.

## Offen

- Journal-, Verdichter-, Sprachprofil-Prompts auf Englisch sind **ungemessen**
  (A9) — Folgearbeit: englische Korpora `korpus/en/{journal,verdichter,sprachprofil}.jsonl`.
- `entschieden` gegen `festlegung_setzen` (beide Sprachen, siehe oben).
- Jeder Fall lief ausser in der deutschen Wiederholung nur einmal;
  Streuung im Wortlaut (vgl. `en-e19`) ist nicht ausgeschlossen.

# Begriffsboard: Resonanz-Schicht und fokussierte Analyse — Messbericht (Karte t_9258d2e9)

Stand: 2026-10-04, Commit 8240ec8, Modelle: gespraech (IT_LLM_MODELL), erkenner (IT_MODELL_ERKENNER).
Rohdaten: korpus/berichte/begriffsboard_resonanz_roh.jsonl (gitignored, 0 Zeilen — kein Lauf). Tabellen: rauchtest-tabellen.md (noch nicht erzeugt).

## Gate Ranking (D6)
Arm A (nur Modell, heutiges sortiert): (b) –/5, (c) –/5, Regression (a) –/5.
Ergebnis: ausstehend.
Folge: ausstehend — Aufgaben 5–7 dieses Plans entfallen für diesen Ausführungslauf (Karte t_9258d2e9), bis der bezahlte Lauf nachgeholt wurde.

## Gate Verhörer (D7)
Arm A (e) –/5 → ausstehend.
Arm D (Prompt 'Sinn zuerst'): (e) –/5, (f) –/5, (g) –/5.
Arm C (Analyse kombiniert) je Modell: ausstehend; Arm E (nur Verhörer) je Modell: ausstehend.
Kombiniert gegen getrennt: ausstehend.

## Kosten und Latenz (gemessen)
Ausstehend — keine Messwerte, da kein Aufruf stattgefunden hat. Die A-priori-Schätzung steht im Plan, Abschnitt „Kosten und Latenz": ein Zweitaufruf je Boardlauf kostete nach dieser Schätzung auf gemma ≈ 0,04 CHF je Diskussion, auf Kimi ≈ 0,12 CHF (Stand kosten.py 04.09.2026).

## Ausstehend
Bezahlter Lauf ausstehend (Zugangsdaten nicht in der Umgebung). Befehle: Aufgabe 4, Steps 2–4 des Plans
(docs/superpowers/plans/2026-10-04-padua-begriffsboard-resonanz.md).

Geprüft wurde dies in Aufgabe 0, Schritt 3 (`python3.11 -c "from interview_theater import einstellungen as e; ..."`)
mit dem Ergebnis `RuntimeError: Fehlende Umgebungsvariable(n): IT_BOT_TOKEN, IT_BOT_NAME, IT_DB, IT_LLM_URL, IT_LLM_KEY,
IT_LLM_MODELL, IT_STT_PRODUKT` — die Ausführungsumgebung dieses Laufs trägt die `IT_*`-Variablen nicht. `betrieb/`
und `.env` wurden dafür bewusst nicht gelesen (Vorgabe der Karte).

Gemäß Aufgabe 0, Schritt 3 des Plans entfallen damit für diesen Lauf die Aufgaben 5–7 (Resonanz-Einbau): ohne
Messung kein Einbau. Sobald Birk den bezahlten Lauf nachholt (Umgebung mit Zugangsdaten, Aufgabe 4 Steps 2–4
des Plans), kann dieser Bericht ergänzt und die Aufgaben 5–7 bei bestätigtem Gate „Praemisse bestaetigt"
nachgezogen werden.

## Entscheidung für Birk

1. **Ranking:** Messung ausstehend (keine Zugangsdaten in der Ausführungsumgebung dieses Laufs). Der Code
   dafür ist fertig und getestet (`scripts/rauchtest_begriffsboard_resonanz.py`, Aufgabe 3, Commit 8240ec8) —
   es fehlt nur der bezahlte Lauf selbst (Aufgabe 4, Steps 2–4). Reicht das, oder soll zusätzlich `wunsch` aus
   dem Zweitaufruf (Arm C) in die Sortierung? — ohne Messung nicht zu beantworten.
2. **Verhörer:** Messung ausstehend. Optionen, billigste zuerst (unverändert aus dem Plan, Abwägung):
   - Prompt „Sinn zuerst" statt Mehrheitsregel (Arm D) — kein Zusatzaufruf, aber Prompt-Änderung (Korpus-/
     Rauchtestlauf danach).
   - Zweitaufruf kombiniert (Arm C) — Kosten/Latenz je 45-min-Diskussion: ausstehend.
   - Zweitaufruf nur Verhörer (Arm E) — Kosten/Latenz: ausstehend.
3. **Empfehlung aus den Zahlen:** Keine Empfehlung möglich — der bezahlte Messlauf hat noch nicht
   stattgefunden. Vorschlag: `python3.11 -m scripts.rauchtest_begriffsboard_resonanz --arme
   board,prompt_nur,analyse,verhoerer --modell gespraech` und `--arme analyse,verhoerer --modell erkenner`
   aus einer Umgebung mit gesetzten `IT_*`-Zugangsdaten nachholen (siehe `docs/betrieb-env.beispiel`),
   dann `--auswerten --bericht docs/begriffsboard-resonanz/rauchtest-tabellen.md`, danach diesen Bericht
   mit den echten Zahlen ergänzen.
4. **Nicht gemessen:** Claude-Weg; weitere Infomaniak-Modelle (Mistral-Small, Ministral, Qwen) —
   `--modell <name>`, erst nach Freigabe im Konto. Zusätzlich in diesem Lauf: alle Arme und Fälle
   überhaupt (siehe Punkt 1–3).

| Arm | Modell | (a) | (b) | (c) | (d) | (e) | (f) | (g) | Eingabe-Token Ø | Latenz ms Ø | CHF je 45-min-Diskussion |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | – | Messung ausstehend | | | – | | | | | | |
| B | – | – | – | – | – | – | – | – | – | – | 0 |
| C | – | Messung ausstehend | | | – | | | | | | |
| D | – | – | – | – | – | Messung ausstehend | | | | | |
| E | – | – | – | – | – | Messung ausstehend | | | | | |

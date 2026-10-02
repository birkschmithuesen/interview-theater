# Entscheidung: Welches Modell wann (Birk, 02.10.2026)

Status: **verbindlich** (Betreiber-Entscheidung). Umsetzung: offen, siehe unten.
Ersetzt für Phase 4–7 die Regel aus `szene_claude.py` („Claude NUR für die Szene“).

## Regel

| Daten / Aufgabe | Modell | Warum |
|---|---|---|
| **Sensible Daten** — Interview-Audio, Transkripte, Verdichtung der Interviews | **Kimi (Infomaniak, Schweiz)** — unbedingt | Hier stecken die persönlichen Geschichten Dritter. Keine US-Cloud für Rohdaten. |
| **Viel Leistung gefragt** — Brainstorming-Sparring, Dramaturgie, Szenen | **Claude Opus (Abo, lokaler Proxy, USA)** | Ergebnis messbar besser (Szenenvergleich 05.09./30.09.), über das Abo günstiger, 1 Mio Token Kontext, wiederholt gesendeter Systemprompt fällt über den Cache kaum ins Gewicht. |

**Annahme (Birk):** Im Brainstorming entstehen keine sensiblen Daten. Sensibel
sind nur die Interviews. Daraus folgt:

- **Phase 1–3** (Begriffe, Fragen, Interviews) und **jede Interview-Verdichtung**
  → Kimi. Auch eine Verdichtung, die erst in Phase 4+ fertig wird oder nachgeholt
  wird, bleibt bei Kimi.
- **Ab Phase 4** (Setting/Figuren/Geschichte, Schärfung, Szenen, Feinschliff)
  → Opus.

## Verhalten

1. **Die Modellwahl-Abfrage kommt VOR Phase 4**, nicht erst vor der ersten
   Szene: beim Übergang 3 → 4 („Interviews fertig“). Eine Zeile Warnung, was ab
   jetzt in die USA geht (Arbeitsstand, Gespräch ab Phase 4, Festlegungen —
   keine Audios, keine Transkripte, keine Chat-Namen), Ja/Nein.
   - Ja → ab Phase 4 Opus.
   - Nein → alles bleibt bei Kimi (Rückfall, kein Abbruch).
2. Die bestehende Szenen-Einwilligung (`szene_usa_bestaetigt_am`) wird durch
   diese eine Einwilligung abgedeckt — keine zweite Frage in Phase 6.
3. Was trotzdem in die USA geht und benannt werden muss: **Belegzitate** aus den
   Interviews, wo Phase 5 (Schärfung) oder die Szene sie verwendet. Das ist
   abgeleitetes Material — die Warnung muss es nennen.
4. Zurückspringen in Phase 1–3 schaltet wieder auf Kimi.

## Offen / zu prüfen

- **Annahme (ungeprüft):** dass Cache-Lesezugriffe das Abo-Kontingent kaum
  belasten. Belegt ist es für die API-Preise (Cache-Read ≈ 10 % des
  Eingabepreises); wie das Abo-Kontingent es zählt, ist nicht gemessen.
- Erkenner (heute gemma, Infomaniak, gemessen 0 Falsch-Positive bei 25): bleibt
  bis zu einer eigenen Messung bei gemma.
- Kosten-Deckel (`IT_KOSTEN_DECKEL_CHF`) rechnet Abo-Aufrufe heute mit
  API-Preisen — für Opus-über-Abo eigene Regel nötig.

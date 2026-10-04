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

## Umsetzung (02.10.2026, Branch `feat/modellwahl-phase`)

**Neues Modul `interview_theater/modellwahl.py`** trifft die Entscheidung an
einer Stelle: `konversation_ueber_claude(e, conn, chat_id)` prüft Schalter
(`IT_SZENE_ANBIETER=claude`, wiederverwendet aus `szene_claude.ist_aktiv`),
Einwilligung (`gruppe.szene_usa_bestaetigt_am`) und Phase (`phasen.aktuelle
>= 4`). `aufruf_schema(...)` ist der Schema-Aufruf, der bei `ueber_claude`
zuerst den Claude-Proxy versucht (`szene_claude.schema`, neu — JSON-Schema
per Prompt + `llm.lies_json`, da Anthropic kein natives `response_format`
kennt) und bei einem Fehler (`ClaudeFehler`/`LLMFehler`) auf Kimi zurückfällt
(Vorfall `opus_fallback`, dieser eine Zug). Eingebaut in `ablauf.py` (alle
vier `"gespraech"`-Stellen inkl. der beiden Nachfass-Aufrufe nach Denkspur/
Echo) und `schaerfung.py` (dort ohne Phasenschwelle — die Schärfung ist
ohnehin erst ab Phase 5 erreichbar).

Szene, Kurzgeschichte, Szenenfolge, Stückprüfung und die Brainstorming-
Karten (`buehnenkarte.py`) routeten vor dieser Karte bereits über
`szene_claude.ist_aktiv` — **unverändert**, profitieren aber automatisch vom
`cache_control`-Zusatz auf dem System-Block in `szene_claude.prosa()` und
tragen seitdem Cache-Token in `aufruf` (additive Spalten
`cache_read_token`/`cache_creation_token`). Diese fünf Pfade bekommen
**keinen** Kimi-Fallback bei einem Proxy-Fehler (unverändert gegenüber vor
der Karte) — ihr bestehendes Fehlerverhalten (eine Chat-Zeile, kein
Hängenbleiben) erfüllt "die Gruppe wartet nicht ewig" bereits, ein echter
Rückfall auf Kimi hätte dort eigene Budget-/Stil-Anpassungen gebraucht, die
außerhalb dieser Karte liegen. Siehe `.modellwahl-report.md` für die
vollständige Modul-Tabelle.

**Einwilligung beim Übergang 3→4**: `knoepfe/stationen.py::eintritt_in_phase`
fragt beim Eintritt in Phase 4 (`_TEXT_ANGEBOT_MODELLWAHL`, DE + EN), über
denselben Knopfweg wie die bisherige Szenen-Frage (`ART_SZENE_USA`,
`biete_szene_usa`) und dieselbe Spalte — eine alte Antwort gilt unverändert
weiter, ein "nein" wird nie wieder gefragt, und der Phaseneintritt selbst
wartet nicht auf die Antwort. Das bestehende Angebot vor der ersten Szene
bleibt als wirkungsloses Sicherheitsnetz stehen.

**Kontextbudget**: `kontext.zeichengrenze`/`gesamtgrenze` nehmen einen
`ueber_claude`-Schalter; mit Einwilligung+Phase≥4 gilt `IT_OPUS_PROMPT_ZEICHEN`
(Vorgabe 400 000, für Körper **und** Gesamtsumme), sonst unverändert die
Kimi-Werte.

**Kostendeckel**: `kosten.ist_abo_modus("C")` macht explizit, was vorher nur
aus zwei Konstanten folgte — ein Claude-Aufruf bucht `kosten_chf = 0`
(`CLAUDE_CHF_JE_AUFRUF`) und zählt deshalb nicht gegen
`IT_KOSTEN_DECKEL_CHF`, obwohl er mit vollen Token-Zahlen in `aufruf` steht.

**Nicht umgesetzt / ausgelagert**: das Nutzertext-Caching des append-only
Brainstorming-Protokolls (eigener `cache_control`-Block *innerhalb* der
Nutzernachricht) — nur der System-Block cached; der Proxy-`/_health`-Check
vor dem ersten Versuch (die bestehende Retry-/Fallback-Kette fängt einen
Ausfall ohnehin ab, nur eine Zug-Runde später); ein echter Lauf gegen den
produktiven Proxy zur Messung der Cache-Wirkung (siehe offene Annahme oben).

## Nachtrag 2026-10-03 (Padua Phase 1+2 Karte)

Zwei Änderungen, beide **ungated** (gelten für jedes Workshop-Profil, nicht
nur Padua) — siehe „Key design decision" in
`docs/superpowers/plans/2026-10-03-padua-phase1-2-ab.md` für die Begründung:
das *Wann* der Einwilligungsfrage zeitlich vorzuziehen kann eine Gruppe, die
Phase 1 schon durchlaufen hat, nicht rückwirkend betreffen, und die
Modellwahl-Regel selbst ist eine allgemeine, phasenbezogene
Birk-Entscheidung ohne Workshop-Vorbehalt.

**Die Einwilligungsfrage feuert jetzt beim Eintritt in Phase 1**, nicht mehr
erst beim Übergang 3 → 4. Dieselbe Spalte
(`gruppe.szene_usa_bestaetigt_am`), derselbe Knopfweg (`ART_SZENE_USA`,
`biete_szene_usa`) — keine zweite Frage. `knoepfe/stationen.py::eintritt_in_phase`
ruft denselben Check-und-Frage-Schritt (`_biete_modellwahl_wenn_faellig`) aus
PHASE_BEGRIFFE **und** PHASE_SETTING; der PHASE_SETTING-Aufruf ist seitdem
ein Sicherheitsnetz für Gruppen, die Phase 1 schon vor diesem Umbau
durchlaufen haben (`angebot_faellig` liefert dort dann noch `True`) — genau
wie der ältere PHASE_SZENEN-Zweig bereits eines ist. Eine alte Zustimmung
(über den bisherigen Weg) gilt unverändert weiter, ein „nein" wird nie wieder
gefragt, und der Phaseneintritt wartet dabei nach wie vor nicht auf die
Antwort.

**`konversation_ueber_claude` schließt jetzt nur noch Phase 3 aus**, statt
eine Mindestphase zu verlangen: `phasen.aktuelle(conn, chat_id) !=
PHASE_INTERVIEWS` statt `>= PHASE_SETTING`. Damit sind Phase 1
(Diskussionsverdichtung) und Phase 2 (Fragenformulierung/KI-Vorschläge) nach
Einwilligung ebenfalls Opus-fähig, zusätzlich zu Phase 4, 5, 6 und 7, die es
schon vorher waren. **Phase 3 (Interviews) und jede Interview-Verdichtung
bleiben unverändert unbedingt bei Kimi** — der Mechanismus ist derselbe wie
zuvor: `verdichter.py` ruft `modellwahl` nie an, und das ist die ganze
Durchsetzung.

## Nachtrag 2026-10-04

Birk, live: „nur die Interviews auf Kimi, aller Rest auf Opus" — für Padua
soll die US-Provider-Einwilligungsfrage ganz entfallen, nicht nur früher
kommen.

**Umsetzung (dieser Task, nur die Profil-Infrastruktur):** ein neuer
Profilschalter `[modellwahl] einwilligung` (Vorgabe `true`, Getter
`workshop.modellwahl_einwilligung_aktiv()`) steht in
`workshop/padua-2026/profil.toml` auf `false`. Dortmund und das eingebaute
Vorgabeprofil setzen die Zeile nicht und bleiben dadurch unverändert — die
Einwilligungsfrage bleibt dort bestehen.

**Was sich bei ausgeschaltetem Schalter ändert — angekündigt, noch nicht
gebaut (späterer Task in diesem Plan):**

- `szene_claude.ist_aktiv` prüft dann nur noch den Betreiber-Schalter
  (`IT_SZENE_ANBIETER=claude`), nicht mehr zusätzlich die Einwilligung.
- `angebot_faellig`/`wartet_auf_antwort` liefern immer `False` — es gibt
  nichts mehr anzubieten oder abzuwarten.
- Die Erkenner-Art `szene_usa` verschwindet aus dem Schema.
- Die US-Warnung vor einem Szenenlauf wird nicht mehr gesendet.

**Phase 3 (Interviews) bleibt davon unberührt und UNBEDINGT Kimi** — dieser
Schalter ändert nichts an der Durchsetzung über `verdichter.py`, das
`modellwahl` nie anruft.

**Zweiter, unabhängiger Schalter `[modellwahl] zitate_an_claude`** (Vorgabe
`true`, Getter `workshop.modellwahl_zitate_an_claude_aktiv()`): mit `false`
entfernt `szene._kernpaket_text` den wörtlichen Interview-Zitattext aus dem
Claude-Szenen-Prompt — Thema und Zuordnung bleiben stehen, nur das
Belegzitat selbst nicht.

**Birk, live 04.10.2026 18:20 (bestätigt):** belegte wörtliche
Interviewzitate dürfen ab Phase 5 an Opus gehen — er weist die
interviewten Personen vor der Aufnahme darauf hin. Padua setzt
`zitate_an_claude = true` deshalb **explizit** (entspricht dem Vorgabewert,
steht aber als bewusste, dokumentierte Entscheidung im Profil statt nur
implizit vom Code-Default zu kommen). Der Unterschalter bleibt vollständig
gebaut und mit einer Zeile (`false`) umkehrbar, falls sich das ändert.

# InScribe Messung 1: Erkenner-Baseline (Opus-Pfad)

Karte `t_dd94e894`, Lauf 11.10.2026. Misst den HEUTIGEN Absichtserkenner,
der seit dem 08.10.2026 unter Padua über `claude-opus-5-5`
(`erkenner.ueber_claude` → `modellwahl.konversation_ueber_claude` →
`szene_claude.schema`) läuft — nicht mehr über `google/gemma-4-31B-it`.
Zwei Quellen: der englische Regressionskorpus (`korpus/en/erkenner.jsonl`,
103 Fälle) und ein neuer Testsatz aus echten Padua-Chats
(`betrieb/korpus/en/padua_testsatz.jsonl`, 37 Fälle, außerhalb des
öffentlichen Repos — E8). Kein Eingriff am Live-Verhalten, kein
Bot-Neustart — nur Lesezugriffe (`betrieb/padua.db` read-only, `VACUUM
INTO`-Kopie außerhalb des Repos, danach gelöscht) und reguläre Aufrufe über
den bestehenden `szene_claude`-Proxy (`hermes-anthropic-proxy.service`,
Abo, 0 CHF je Aufruf).

## Schätzung vor dem Lauf

Vor dem echten Lauf geschätzt (siehe Konversationsverlauf dieser Karte):
EN-Korpus 103 Fälle, davon 7 Aufnahmefälle (bleiben immer bei Kimi/gemma,
`erkenner.erkenne_in_aufnahme` ruft `modellwahl` nie an) → **96 erwartete
Opus-Aufrufe**. Padua-Testsatz 37 Fälle, keine Aufnahmefälle → **37
erwartete Opus-Aufrufe**. Summe: **133 erwartete Opus-Aufrufe**, dazu 7
Kimi-Aufrufe (Aufnahmepfad). Kosten: 0 CHF (Abo, `kosten.CLAUDE_CHF_JE_AUFRUF`).

**Tatsächlich:** 96 + 37 = **133 Opus-Aufrufe** — genau wie geschätzt. Dazu
7 Kimi-Aufrufe, die alle mit HTTP 400 scheiterten (siehe Nebenbefund unten,
kein Opus-Pfad betroffen). Laufzeit: EN-Korpus 182,9 s, Padua-Testsatz
~130 s (nicht separat gestoppt, aus Zeitstempeln der Berichtsdatei
überschlagen). Kosten: 0 CHF (Abo) für alle 133 Opus-Aufrufe; die 7
gescheiterten Kimi-Aufrufe kosten nichts (kein Erfolg, keine Antwort-Token).

## Tabelle: Treffer / still falsch / verpasst / Latenz / Kosten je Quelle

| Quelle | Modell | Läufe | Treffer | Still falsch (FP) | Verpasst (FN) | Median-Latenz | Kosten |
|---|---|---|---|---|---|---|---|
| `korpus/en/erkenner.jsonl` (heute, Opus) | `claude-opus-5-5` | 103 (7 Fehler) | 61/63 | **2** | 2 | 1711 ms | 0 CHF (Abo) |
| `betrieb/korpus/en/padua_testsatz.jsonl` (heute, Opus) | `claude-opus-5-5` | 37 | 3/27 | **29** | 24 | 3701 ms | 0 CHF (Abo) |
| `korpus/erkenner.jsonl`, 136 Fälle (gemma, 05.09.2026) | `google/gemma-4-31B-it` | 136 | 108/110 | **0** | 2 | 697 ms | 0,2517 CHF |
| Qualifikationsmessung (gemma, 04.09.2026, `docs/HANDOFF.md:264`) | `google/gemma-4-31B-it` | 25 Negativfälle + Positivfälle | 30/30 | **0** | — | 0,75 s | — |

Nachrechnen (`betrieb/korpus/en/padua_testsatz.jsonl` muss lokal vorhanden
sein, siehe `docs/agents/korpus-und-simulation.md`):

```
set -a; . ./betrieb/padua-gruppe1.env; set +a
python -m scripts.pruefe_prompts erkenner --ueber-claude --sprache en --bericht
python -m scripts.pruefe_prompts erkenner --ueber-claude --sprache en \
    --korpus-datei padua_testsatz --bericht
```

Volle Berichte (gitignored, lokal): `korpus/berichte/2026-10-11-erkenner-ueber-claude-en.md`,
`korpus/berichte/2026-10-11-padua-testsatz-ueber-claude.md`. Die
gemma-Vergleichszahlen: `korpus/berichte/2026-09-05-erkenner.md` (136
Fälle) bzw. `docs/HANDOFF.md:264` (Qualifikationsmessung).

## Befund 1: EN-Korpus (Opus) — nah an der gemma-Qualität, zwei neue FP

2 Falsch-Positive, 2 Falsch-Negative bei 103 Fällen (96 über Opus
gelaufen). Beide FP/FN-Paare sind dieselben zwei Fälle (Modell liefert
etwas Falsches UND verpasst damit das Erwartete):

- **`en-e35-overview-ending-sadder`**: erwartet `uebersicht_aendern`
  (Phase-5-Feedback zur generierten Übersicht), Opus lieferte
  `festlegung_setzen`. Beide Arten sind im Prompt beschrieben; die
  Abgrenzung ("gilt nur, solange die Übersicht nicht fixiert ist") scheint
  für Opus weniger scharf als für gemma.
- **`en-e38-durchlaufend-keine-neue-anzahl`**: erwartet eine leere Liste
  ("one continuous performance" ist eine Bauweise, keine neue
  Szenenanzahl — genau der Live-Fehler vom 07.10.2026, den dieser
  Korpusfall festhält), Opus lieferte `festlegung_setzen`. Kein Rückfall
  in den alten Fehler (`szenenanzahl_setzen:1`), aber auch keine leere
  Liste — `festlegung_setzen` ist hier vertretbar (eine Struktur-Festlegung
  passt in kein Feld), zählt aber nach der mechanischen Regel als FP.

**Falsch-Negative in Zustimmungsfällen (N7-Kennzahl): 0 von 12** — die
teuerste Fehlerrichtung (Zustimmung, die nirgends ankommt) tritt nicht auf.

## Befund 2: Padua-Testsatz — die Zahl allein ist irreführend

29 FP / 24 FN bei 37 Fällen sehen nach einem gescheiterten Lauf aus. Beim
Durchsehen der Einzelfälle (vollständig im lokalen Bericht) zeigt sich:
**in praktisch jedem Fall mit FP/FN hat Opus tatsächlich etwas
geschrieben** — nur unter einem anderen `art`-Namen als dem, den ich beim
Bau des Testsatzes als Sollwert eingetragen hatte. Zwei Muster erklären
den größten Teil:

**Muster A — `text_ueberarbeiten` statt `stagescript_notiz` (mindestens
19 der 29 FP).** Beide Arten tragen laut `erkenner.py` denselben Zweck
("eine Szene soll sich ändern"), unterscheiden sich aber danach, ob die
Szene GERADE mit „Yes, save / No, change" gezeigt wird
(`text_ueberarbeiten`) oder nicht (`stagescript_notiz`) — „die beiden
Arten schließen sich gegenseitig aus" (Kommentar in `erkenner.py`,
Punkt 33 im Prompt). Mein nachgebauter `vorlauf` für die meisten
Script-Fälle war die Standard-Rückfrage des Bots nach einer neu gezeigten
Szene ("Szene N von M ist in der Script-Ansicht — passt das so? Sonst sag
mir, was sich ändern soll.") — das ist inhaltlich eine Review-Aufforderung,
auch ohne die wörtlichen Knopftexte „Yes, save / No, change". Opus liest
das offenbar als „Szene wird gerade gezeigt" und wählt `text_ueberarbeiten`.
**Das ist wahrscheinlich kein Fehler des Erkenners, sondern eine
Ungenauigkeit meines Testsatzes**: ohne den echten `prueflauf`/Review-
Zustand aus der Datenbank zum Zeitpunkt jeder Nachricht lässt sich die
Grenze zwischen den beiden Arten aus dem Chatverlauf allein nicht
zuverlässig nachbauen.

**Muster B — `festlegung_setzen`/`szene_planen` statt `rahmen_setzen`/
`stagescript_notiz` (`p02`, `p04`).** Für große, mehrere Szenen
betreffende Regieänderungen (Raumwechsel, Ritual-Choreografie) wählt Opus
die Auffangart oder plant gleich eine Szene neu, statt das einzelne
`rahmen`-Feld zu überschreiben oder eine einzelne `stagescript_notiz` zu
schreiben. Auch hier: eine Handlung wird ausgelöst, nur anders benannt.

**Die drei Fälle mit belegtem historischem Befund (`herkunft.erkenner_befund`)
reproduzieren sich heute NICHT:**

- `p01` (Frage als Änderungswunsch behandelt, 08.10.2026): heute 0 FP, 0
  FN — Opus beantwortete die Frage korrekt als Frage.
- `p15` (Listenwunsch als Entscheidung notiert): heute 0 FP, 0 FN.
- `p29` (Erkenner verlangte Wiederholung statt anzuwenden): heute wurde
  tatsächlich `text_ueberarbeiten` ausgelöst (Muster A) — die Änderung
  wäre heute sofort angewendet worden, nicht erst nach einer Wiederholung.

**Zwei echte neue Falsch-Positive, nicht durch Muster A/B erklärt:**

- `n04-g1-negativ-liste-ist-keine-absicht`: eine reine Zitatlisten-Bitte
  löste `fassung_abnehmen` aus (Freigabe einer gar nicht gezeigten
  Fassung).
- `n05-g1-negativ-liste-praezisiert`: eine Folgefrage, die eine zuvor
  gezeigte Zitatliste auf einzelne Zitatnummern einschränkte, löste
  `festlegung_setzen` aus — die Liste selbst wird fälschlich als
  Dauerentscheidung notiert.

**Einordnung:** Der Padua-Testsatz ist in dieser Fassung **kein
scharfes Pass/Fail-Gate**, weil die `erwartet`-Werte für
`stagescript_notiz`-Fälle den Review-Zustand der Originalkonversation
nicht sicher abbilden (siehe Muster A). Er taugt aber bereits jetzt gut
als **Regressions-/Drift-Detektor**: eine künftige Prompt- oder
Modelländerung, die stattdessen plötzlich GAR NICHTS mehr auslöst (statt
„falscher Art-Name"), wäre an genau diesem Testsatz sofort sichtbar. Als
Folgearbeit (nicht Teil dieser Karte): die 19 Muster-A-Fälle gegen die
`prueflauf`/Review-Zustände aus `betrieb/padua.db` zum jeweiligen
Zeitpunkt nachprüfen und die `erwartet`-Werte entsprechend korrigieren
oder beide Arten als gültige Alternative im Vergleich zulassen.

## Nebenbefund: 7× HTTP 400 im Aufnahme-Pfad (Kimi/gemma, nicht Opus)

Alle 7 Aufnahmefälle des EN-Korpus (`en-a01`…`en-a07`,
`erkenner.erkenne_in_aufnahme`, läuft **immer** über Kimi/gemma, nie über
Claude) scheiterten mit `HTTP 400`. Nicht näher diagnostiziert (außerhalb
des Zeitrahmens dieser Karte und außerhalb ihres Auftrags — `erkenner.py`
durfte nur gelesen werden); da dieser Pfad real im Betrieb läuft (jede
Sprachnachricht während eines Interviews), ist das ein eigenständiger
Befund, der eine eigene, kleine Untersuchung verdient — unabhängig vom
Opus-Thema dieser Karte. Betrifft nicht die Opus-Zahlen oben.

## Gate (Prozessregel, dokumentiert in `docs/agents/korpus-und-simulation.md`)

Ein Modellwechsel des Erkenners verlangt künftig einen Korpuslauf gegen
beide Testsätze, außer Birk sagt explizit „ohne Korpus" — reine
Prozessregel, kein technisches Gate.

## Prämissen, die sich als falsch erwiesen haben

1. **`betrieb/gruppe1.env` reicht nicht.** Die Karte nennt diese Datei als
   Zugangsweg; sie hat weder `IT_WORKSHOP=padua-2026` noch
   `IT_SZENE_MODELL=claude-opus-5-5` gesetzt — ohne beides bliebe
   `--ueber-claude` entweder durch die eigene Validierung blockiert oder
   würde (schlimmer) ein anderes Modell als das Live-Modell messen. Die
   richtige Datei für diese Messung ist `betrieb/padua-gruppe1.env`.
2. **Der deutsche Hauptkorpus ist gegen den Live-Opus-Pfad nicht fahrbar.**
   `--ueber-claude` braucht `IT_WORKSHOP=padua-2026` (Englisch); `main()`s
   eigene Sprachprüfung (D8) lehnt `korpus/erkenner.jsonl` unter diesem
   Profil konsequent ab. Gemessen wurde deshalb `korpus/en/erkenner.jsonl`
   (103 statt 157 Fälle) — eine andere Grundgesamtheit als die in der Karte
   benannte.
3. **Der Padua-Testsatz misst eher „tut der Erkenner etwas Sinnvolles"
   als „trifft er exakt meinen Sollwert".** Ohne Zugriff auf den echten
   Review-Zustand (`prueflauf`) zum Zeitpunkt jeder Nachricht ließ sich die
   Grenze zwischen `text_ueberarbeiten` und `stagescript_notiz` beim Bau
   des Testsatzes nicht zuverlässig nachbilden (Muster A oben) — das
   relativiert die rohe FP/FN-Zahl erheblich, ändert aber nichts am Wert
   des Testsatzes als Regressionsschutz.

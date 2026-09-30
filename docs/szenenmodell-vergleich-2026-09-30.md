# Szenenmodell-Vergleich: claude-opus-5 vs. claude-opus-5-5 (Padua M2)

**Frage:** Was bringt fuer Padua die Anhebung des Szenenmodells von `claude-opus-5`
(Referenz, bisheriges Modell) auf `claude-opus-5-5` (E9-Kandidat)?

**Kurzurteil:** siehe letzter Abschnitt.

---

## 1. Methodik

- **Weg:** Phase 7 (Feinschliff), Szene 1, Form "Dialog". Der Prompt entsteht ueber
  den echten Aufbau von `scripts/sprachstil_wirkung.baue_db(pfad, "B", phase=7)` +
  `sprachstil_wirkung.szene_prompt(conn)` — also `szene.systemanweisung()` und
  `szene.baue_nutzertext()`, genau der Weg aus `szene.schreibe`. Variante "B"
  heisst: **kein** `figur.sprachstil` gesetzt (M1 hat den Stil-Effekt separat
  gemessen; hier soll nur das Modell variieren, sonst nichts).
- **Arbeitsstand (identisch fuer beide Modelle, byte-gleicher Prompt, SHA-256
  `2841fcfe...c5070b`):** Gemeinschaftskueche eines Frauenwohnheims am Hauptbahnhof,
  Winter 1971, dritter Tag nach der Ankunft; drei Figuren (Meryem, Ferzan, Aynur,
  Namen aus `simulation/interviews/set1/`, erfunden); Szene 1 "Der Koffer", Form
  Dialog, feste Prosavorlage aus `sprachstil_wirkung.PROSA[1]`. **Keine Echtdaten** —
  weder `betrieb/soap.db` noch reale Interviews.
- **Workshop-Profil:** `workshop/padua-2026/profil.toml` trug zum Messzeitpunkt
  weiterhin `geruest = true` (noch nicht fertig). Gemessen wurde deshalb bewusst
  gegen das **eingebaute Vorgabeprofil** (Dortmund-Werte) — `IT_WORKSHOP` war nicht
  gesetzt, das Skript bricht sonst ab, statt zwei nicht vergleichbare Prompts zu bauen.
- **n = 3 je Modell**, seriell und verschraenkt (Lauf 1 opus-5, Lauf 1 opus-5-5, Lauf 2
  opus-5, ... — AGENTS.md Falle 8: keine Parallelitaet, damit eine Tageszeit/Proxylast
  nicht einem Modell allein anhaengt).
- **Anbieter:** lokaler Anthropic-Proxy `http://127.0.0.1:28764/v1/messages`, Abo, kein
  Authorization-Header, 0 CHF Zusatzkosten. Modellnamen `claude-opus-5` und
  `claude-opus-5-5`, beide vor dem Lauf per curl gegen `/v1/messages` verifiziert.
- **Werkzeug:** `scripts/szenenmodell_vergleich.py` (neu, Unterbefehle `pfad`/`lauf`/
  `tabelle`), `interview_theater/` bleibt unveraendert. Rohtexte und Prompt liegen unter
  `docs/szenenmodell-vergleich-2026-09-30/` (Prompt + `laeufe/*.json`, je Lauf Volltext,
  Zeichen, Dauer, `stop_reason`, Token).

Alle 6 Laeufe: `status: ok`, `stop_reason: end_turn` — keine Wiederholung, kein
abgeschnittener Text.

## 2. Zahlen

| Modell | Lauf | Zeichen | Sekunden | Ausgabe-Token | stop_reason | Status |
|---|---|---|---|---|---|---|
| claude-opus-5 | 1 | 5837 | 156,0 | 11165 | end_turn | ok |
| claude-opus-5 | 2 | 5813 | 132,1 | 9548 | end_turn | ok |
| claude-opus-5 | 3 | 4777 | 157,5 | 12059 | end_turn | ok |
| claude-opus-5-5 | 1 | 5418 | 85,1 | 8559 | end_turn | ok |
| claude-opus-5-5 | 2 | 6137 | 95,5 | 9267 | end_turn | ok |
| claude-opus-5-5 | 3 | 6612 | 113,1 | 11203 | end_turn | ok |

| Modell | n | Zeichen Mittel | Zeichen Min/Max | Sekunden Mittel | Sekunden Min/Max |
|---|---|---|---|---|---|
| claude-opus-5 | 3 | 5475,7 | 4777 / 5837 | 148,5 | 132,1 / 157,5 |
| claude-opus-5-5 | 3 | 6055,7 | 5418 / 6612 | 97,9 | 85,1 / 113,1 |

| Modell | Lauf | Sprecherzeilen | `Zusammenfassung:` | `Anders gemacht:` |
|---|---|---|---|---|
| claude-opus-5 | 1 | 76 | ja | nein |
| claude-opus-5 | 2 | 81 | ja | nein |
| claude-opus-5 | 3 | 65 | ja | nein |
| claude-opus-5-5 | 1 | 86 | ja | nein |
| claude-opus-5-5 | 2 | 105 | ja | nein |
| claude-opus-5-5 | 3 | 114 | ja | nein |

`claude-opus-5-5` ist im Mittel **~34 % schneller** (97,9 s vs. 148,5 s) und liefert
**~11 % mehr Zeichen** bei **deutlich mehr Sprecherzeilen** (Mittel 101,7 vs. 74,0 —
+37 %) — bei gleicher Pflichtzeilen-Disziplin (beide Modelle liefern in allen 6 Laeufen
`ZUSAMMENFASSUNG:`, keines `ANDERS GEMACHT:` mit Inhalt, weil die Prosavorlage
unveraendert vorgegeben war).

## 3. Zwei Textbeispiele nebeneinander

Beide Laeufe teilen sich denselben Prompt (Rahmen: Gemeinschaftskueche, dritter Abend,
Meryem kommt mit dem Koffer aus dem Keller, Ferzan liest den Fahrplan, Aynur steht am
Herd). Volltexte unter `docs/szenenmodell-vergleich-2026-09-30/laeufe/`.

### claude-opus-5, Lauf 1 (156,0 s, 5837 Zeichen, 76 Sprecherzeilen)

```
SZENE 1: DER KOFFER ca. 9 min

Gemeinschaftskueche im Frauenwohnheim am Hauptbahnhof. Abend, dritter Tag. Ein Tisch,
ein Gasherd. Es riecht nach Gas und nassem Mantel. FERZAN sitzt am Tisch, vor sich einen
aufgefalteten Fahrplan. AYNUR steht am Herd, die Haende ueber einer kleinen Flamme.
Neben dem Herd die Tuer zum Schlafraum.

FERZAN:Fuenf Uhr zweiundvierzig.
AYNUR:Hm.
FERZAN:Nein. Vierundvierzig. Fuenf Uhr vierundvierzig, dann Muenchen.
AYNUR:Muenchen.
FERZAN:In Muenchen steigt man um. Glaub ich. Hier steht was, und ich weiss nicht, was
hier steht.

(MERYEM kommt herein, mit einem braunen Koffer. Sie stellt ihn neben die Tuer.)

MERYEM:Der Keller ist offen. Da schliesst keiner ab, da steht alles einfach so rum,
Koffer, Taschen, alles.
FERZAN:Was war unten?
MERYEM:Meiner.
[...]
(MERYEM oeffnet den Koffer. Sie nimmt ein kleines Stoffbuendel heraus und legt es auf
den Tisch.)

FERZAN:Was ist das.
MERYEM:Biber. Getrocknet. Meine Mutter hat mir drei Stueck reingelegt, und ich hab
gesagt, anne, ich bin ein Jahr weg, ein Jahr braucht kein Mensch biber, und sie hat es
trotzdem reingelegt.
[...]
FERZAN:(sieht nicht auf)Du packst nicht aus.
(MERYEM zuckt die Schultern.)
FERZAN:Dritter Tag heute.
(Pause.)
[...]
(Draussen faehrt ein Zug ab. Alle drei hoeren hin.)
FERZAN:Das ist er.
AYNUR:Welcher?
FERZAN:Der von zehn nach neun. Der von halb.
(Der Zug ist weg.)
[...]
FERZAN:Morgen wieder.
```

### claude-opus-5-5, Lauf 2 (95,5 s, 6137 Zeichen, 105 Sprecherzeilen)

```
SZENE 1: DER KOFFER ca. 9 min

Die Gemeinschaftskueche eines Frauenwohnheims am Hauptbahnhof. Winter 1971, Abend, der
dritte Tag nach der Ankunft. Es riecht nach Gas und nassen Maenteln.

FERZAN sitzt, einen gefalteten Fahrplan vor sich. AYNUR steht am Herd, die Haende ueber
der Flamme. Sie traegt duenne Stoffschuhe.

(MERYEM kommt mit einem braunen Koffer, im Mantel. Sie geht durch in den Nebenraum. Man
hoert, wie sie ihn mit dem Fuss unter das Bett schiebt. Sie kommt zurueck.)

FERZAN: Du packst nicht aus.
(MERYEM zuckt die Schultern.)
FERZAN: Drei Tage. Warum packst du nicht aus?
MERYEM: Der Keller ist nass. Da unten ist alles, der Boden, die Wand, alles nass. Ich
lass den doch nicht da unten.
FERZAN: Ich hab nicht nach dem Keller gefragt.
MERYEM: Hast du gegessen?
[...]
FERZAN: Und das?
MERYEM: Was?
FERZAN: Das da. Beim Herd.
MERYEM: Tee.
FERZAN: Aus dem Koffer.
MERYEM: Aus der Tasche.
FERZAN: Und in die Tasche kommt er woher?
MERYEM: Man braucht doch Tee. Auch wenn man ... auch fuer eine Woche braucht man Tee.
[...]
(FERZAN steht auf und geht zur Tuer des Nebenraums. MERYEM ist vor ihr da und bleibt in
der Tuer stehen.)
FERZAN: Ich will nur sehen.
MERYEM: Da ist ein Koffer. Braun. Hast du gesehen.
FERZAN: Mach ihn auf.
MERYEM: Da ist nichts drin, was du brauchst.
[...]
FERZAN: Ich seh das doch. Der Koffer. Du willst auch.
MERYEM: Bos ver.
FERZAN: Erê. Bos ver.
[...]
(AYNUR bleibt stehen. Draussen faehrt ein Zug ab. Alle drei hoeren hin.)
```

## 4. Auffaellige Unterschiede

- **Formatfehler-Unterschied im Sprecherkopf:** `claude-opus-5` schreibt in Lauf 1
  `FERZAN:Fuenf...` ohne Leerzeichen nach dem Doppelpunkt (die enge Schreibweise aus
  `formen/dialog.md`); `claude-opus-5-5` schreibt in Lauf 2 durchgaengig `FERZAN: Du
  packst...` **mit** Leerzeichen. Beide Formen sind fuer `sprecher.py` erkennbar (siehe
  AGENTS.md, Sprecherzeilen-Parser), keine ist "falsch" — aber es ist eine sichtbare
  stilistische Verschiebung zwischen den Modellversionen.
- **Mehr, kuerzere Zeilen bei opus-5-5:** die hoehere Sprecherzeilenzahl (Mittel 101,7
  vs. 74,0) kommt nicht aus mehr Text, sondern aus kuerzeren Wortwechseln — mehr
  Schlagabtausch, weniger lange Einzelreplik. Sichtbar am Tee-Verhoer oben: sechs kurze
  Zeilen fuer eine einzige Verdachtsbewegung.
- **Konflikt bleibt zugespitzter bei opus-5-5:** in Lauf 2 verfolgt Ferzan das Motiv
  "Warum packst du nicht aus?" ueber die ganze Szene mit wachsendem Druck (Tee-Fund,
  Tuerblockade, direkte Frage "Kommst du mit?"), inklusive kurdischer Einsprengsel
  ("Bos ver", "Erê", "Xwedê") passend zum Sprachprofil. `claude-opus-5` (Lauf 1) loest
  denselben Konflikt frueher auf ("Du packst nicht aus" -> Schulterzucken -> Thema
  wechselt zu Gas/Kaelte) und bleibt insgesamt beobachtender, weniger konfrontativ.
- **Beide Modelle respektieren die Prosavorlage identisch eng** (Koffer, Fahrplan,
  Herd/Flamme, Zugabfahrt am Schluss kommen in allen 6 Laeufen vor) — die Vorlagenbindung
  aus `szene.baue_nutzertext(..., vorlage=True)` wirkt bei beiden Modellversionen gleich
  stark.
- **Keine Formatabbrueche, keine leeren Antworten, kein `finish_reason: length`** bei
  keinem der 6 Laeufe — beide Modelle liefern zuverlaessig `end_turn` innerhalb von
  `MAX_TOKENS = 32.000`.
- **Laufzeit:** `claude-opus-5-5` ist durchgaengig schneller (85–113 s gegen 132–158 s) —
  bei einem Reasoning-Aufruf im eigenen Thread (siehe AGENTS.md, Reasoning-Ausnahme
  `szene.py`) reduziert das die Wartezeit bis zur naechsten Gruppenaktion deutlich.

## 5. Urteil

Nach dieser Messung (n=3 je Modell, ein Prompt, byte-identisch) schreibt
`claude-opus-5-5` bei gleicher Formattreue (Pflichtzeilen, Vorlagenbindung, kein
Abschneiden) **schneller** (-34 % Laufzeit) und mit **mehr dramatischer Verdichtung**
(mehr Sprecherwechsel, zugespitzterer Konflikt, praesentere Sprachprofil-Einsprengsel)
als das bisherige `claude-opus-5`. Der einzige beobachtete Nebeneffekt ist eine
unterschiedliche Interpunktion im Sprecherkopf (mit/ohne Leerzeichen nach dem
Doppelpunkt), die beide Formen des Parsers gleich gut erkennt und daher nichts kostet.
Fuer Padua — kurze Probenfenster, Live-Wartezeit der Gruppe waehrend des Schreibens —
spricht diese Messung fuer das Upgrade; ein groesserer Lauf mit mehreren Szenenformen
(Lied, Chor) waere sinnvoll, bevor die Umstellung produktiv geht, aber diese Karte
misst nur, sie entscheidet nicht.

---

*Diese Karte misst nur. Kein Produktcode in `interview_theater/` wurde geaendert.*

# Analyse: Ablauffehler Textentwicklung Gruppe 1, 06.09.2026, 13:20–14:10 UTC

**Fall:** Gruppe 1 (`chat_id -5143986099`), `betrieb/soap.db`, Phasen 4→5→6.
**Quellen:** Code auf `main` (19dff75 / e4437c1+), Tabellen `nachricht`, `journal`,
`aufruf`, `vorfall`, `szene`, `arbeitsstand`, `schaerfung`, `knopf`, `figur`,
`gruppe` — read-only geöffnet (`file:betrieb/soap.db?mode=ro`).
**Methode:** je Befund Symptom → Codepfad → Ursache → minimaler Fix.

**PII:** Es werden ausschließlich Bot-Systemtexte zitiert. Kein Wortlaut von
Teilnehmenden, kein Interviewzitat, kein Klarname einer interviewten Person.
Die Namen im Text sind erfundene Bühnenfiguren der Gruppe, keine Personen.

---

## 0. Rekonstruktion des Ablaufs (Zeitstempel UTC)

| Zeit | Ereignis | Beleg |
|---|---|---|
| 13:38:47 | Figurenliste per Knopf gespeichert (10 Figuren) | `knopf` id 309, `journal` 28 |
| 13:39:40–13:53:29 | **12 Sprachstil-Läufe**, einer je Figur, seriell | `aufruf art=sprachstil`, n=12, Σ 718 s |
| 13:43:34 | `figuren_fixiert_am` gesetzt, Überleitung zur Geschichte | `arbeitsstand`, `journal` 33/34 |
| 13:48:55 | Erkenner legt aus einem Gruppenbeitrag **3 Szenen** an (`szene_planen`) | `szene` ids 1–3, Bot-Nachricht 511 |
| 13:50:01 | Bot bietet drei Geschichte-Richtungen als Menü an | `knopf` 353–356 |
| 13:52:20 | Richtung gewählt → `arbeitsstand.geschichte` = **113 Zeichen** (eine Menüzeile) | `journal` 52, `knopf` 355 |
| 13:52:20 | direkt danach: „Ich schlage euch eine Szenenfolge vor, einen Moment." | Nachricht 528 |
| 13:53:35 | Phase 5 gesetzt (Weg `quelle=befehl`) | `journal` 53 |
| 13:53:37 | Phasen-Abschlussmeldung + Knopf „Weiter zu 6" | `knopf` 369/370 |
| 13:53:42 | Schärfungslauf fertig, 7 Stellen zugeordnet; **sofort Szene-1-Vorschlag** | `aufruf art=schaerfung` 6,8 s; `schaerfung` 1–7 |
| 13:54:10 | Szenenfolge-Lauf fertig (110 s) — schlägt **6 Szenen** vor | `aufruf art=szenenfolge`, Nachricht 539 (2120 Zeichen) |
| 13:54:37 | Knopf „Ja, speichern" → **3 alte Szenen weich entfernt**, 6 neue angelegt | `szene` ids 1–3 `entfernt_am`, ids 4–9 neu; `journal` 59 |
| 13:54:37 | direkt danach Szene-1-Vorstellung mit „Soll ich Szene 1 jetzt schreiben?" | `knopf` 379–383 |
| 13:55:13 | „Passt, schreiben" gedrückt → USA-Angebot, Auftrag gemerkt | `knopf` 379 benutzt, `gruppe.szene_usa_angeboten_am` |
| 13:55:26 | USA-Knopf „ja" → gemerkter Auftrag läuft sofort los | `gruppe.szene_usa_bestaetigt_am = ja:13:55:26`, `journal` 60 |
| 13:56:44 | **Einzelszenen-Lauf** liefert 4543 Zeichen Prosa → `szene(4).prosa` | `aufruf art=szene` 78 s, `finish_reason=end_turn` |
| 14:06:07 | Rückmeldung von Birk (Kürzung) | Nachricht 556 |
| 14:06:17 | Gesprächsmodell antwortet mit **neuer Szenenliste im Text** | Nachricht 557 |
| 14:06:24 | Erkenner wendet `szene_planen` auf Szenen 1–4 an **und** setzt Phase 6 | Nachricht 558/562, `arbeitsstand.phase_gesetzt_am` |
| 14:06:24 | Phaseneintritt 6: Einleitung + Knopf „Geschichte schreiben" | Nachricht 559/560, `knopf` 394 |
| 14:07:04 | Knopf gedrückt | `knopf` 394 `benutzt_am` |
| 14:09:35 | Kurzgeschichten-Lauf (150 s) → **Szenen 4–9 entfernt, 10–15 neu** | `aufruf art=kurzgeschichte`, `journal` 64 |

Keine Vorfälle außer einem `http_5xx` (ReadTimeout, Wiederholung erfolgreich,
13:49:53). Technisch lief alles; der Fehler ist ein Ablauffehler.

**Modellzeit in dieser Stunde:** 718 s Sprachstil, 150 s Kurzgeschichte,
110 s Szenenfolge, 94 s Gespräch, 78 s Szene, 63 s Erkenner. Über die Hälfte
der Wartezeit im Raum entfiel auf die zwölf Sprachstil-Läufe.

---

## 1. Zuordnung Interviews → Figuren: wo, warum langsam, wie ein Knopf aussehen müsste

### Symptom
Die Zuordnung fehlte anfangs ganz und wurde dann Figur für Figur durchgegangen.
13:39:40 bis 13:53:29 — vierzehn Minuten, in denen die Gruppe im Wesentlichen
wartete. Fünf von 16 Figuren haben bis heute keine Zuordnung
(`figur.quelle_aufnahme_id IS NULL` bei ids 12–16).

### Codepfad
Das Feld ist `figur.quelle_aufnahme_id` (`db.py:309`). Es gibt heute **vier**
Schreibwege, keiner davon ist eine Massenzuordnung:

1. `knoepfe.stelle_stil_vor` (`knoepfe.py:3679`) → `sprachstil.starte` — genau
   **eine Figur je Lauf**, danach `knoepfe._wirke`, `ART_FIGUR_STIL`
   (`knoepfe.py:4614–4635`) schreibt `setze_figur_sprachstil` + `setze_figur_quelle`
   und ruft am Ende wieder `stelle_stil_vor` für die *nächste* Figur.
2. `knoepfe` `ART_FIGUR_INTERVIEW` (`knoepfe.py:4574–4580`) — Menü je Figur.
3. `erkenner._wende_figur_quelle_an` (`erkenner.py:561–592`) — ein Satz je Figur.
4. `schaerfung.uebernimm_figur` (`schaerfung.py:393–416`) — nur als Nebenwirkung
   einer übernommenen Schärfung.

### Ursache
Die Kette in `knoepfe.py:4634` (`if not stelle_stil_vor(...)`) ist **rekursiv
seriell und modellgebunden**: jede Figur kostet einen eigenen Modellaufruf, und
der Lauf ist kein Klassifikator, sondern ein Prosa-Lauf (Modus B). Gemessen:
`aufruf art=sprachstil`, 12 Läufe, 37 221 ms bis 77 364 ms je Lauf,
Σ **718 s** = 12 Minuten reine Modellzeit, dazu je Figur ein Knopfdruck. Die
Zuordnung ist dabei ein *Nebenprodukt* der Stilwahl — es gibt keinen Weg, der
nur zuordnet.

Verschärfend: `knoepfe.ebene2_erlaubt` (`knoepfe.py:3652`) sperrt die
Interview-Zuordnung bis Phase 5. In Phase 4 wird über den Stil-Weg trotzdem
zugeordnet — die beiden Regeln stehen quer zueinander.

### Minimaler Fix — Knopf „Zufällig zuordnen"
- **Modul:** `interview_theater/knoepfe.py`, neue Art `ART_FIGUREN_ZUFALL =
  "figuren_zufall"` (Konstantenblock um Zeile 3667, bei `ART_FIGUR_STIL`).
- **Knopf-Ort:** in der Leiste von `stelle_stil_vor` bzw. direkt in
  `_schliesse_figuren_ab` (`knoepfe.py:3877`) — also genau dort, wo heute die
  Figur-für-Figur-Schleife startet. Zweiter sinnvoller Ort: die Leiste unter
  `stelle_figur_vor`.
- **repo-Funktionen:** ausschließlich vorhandene — `repo.figuren`,
  `aufnahme.interviews` (über `knoepfe._interviewkoepfe`, `knoepfe.py:3769`),
  `repo.setze_figur_quelle` (`repo.py:1666`), `repo.schreibe_journal`.
- **Wirkung:** alle Figuren mit `quelle_aufnahme_id IS NULL` reihum
  (Round-Robin über die Interviewköpfe, `random.shuffle` auf der Figurenliste)
  belegen, eine Sammelmeldung „Zugeordnet: N Figuren auf M Interviews.
  Ändern könnt ihr jede einzeln." und Rücksprung in `_schliesse_figuren_ab`.

Die drei bindenden Zusagen aus AGENTS.md sind dabei einhaltbar:
- **`callback_data` < 64 Byte:** der Knopf trägt nur `k:<id>`
  (`knoepfe._daten`), `knopf.wert` bleibt `NULL` — es gibt nichts zu
  parametrisieren.
- **Kein Modellaufruf im Handler:** die Zuordnung ist eine reine
  DB-Operation. Sprachstile werden dabei **nicht** erzeugt; wer sie will,
  drückt weiter Figur für Figur (oder ein späterer Sammel-Lauf im Thread
  holt sie nach, wie `schaerfung.starte`).
- **Idempotent:** `knoepfe.behandle` (`knoepfe.py:4953`) klemmt jeden zweiten
  Druck über `repo.beanspruche_knopf` ab, bevor `_wirke` läuft — der Handler
  braucht keine eigene Sperre. Zusätzlich ist die Wirkung selbst idempotent,
  weil nur Figuren **ohne** Quelle angefasst werden.

Aufwand **S**, Datei `knoepfe.py` (+ ein Test), Code → Neustart nötig.

---

## 2. „Ich lege eure Geschichte neben die Interviews …" und die Wall of Text

### Symptom
13:53:42 Bot-Zeile, danach unmittelbar Szene-1-Vorschlag als Fließblock; die
Folgenachrichten wuchsen auf 712 und 1280 Zeichen (Nachrichten 538, 541, 545),
jeweils mit vollständigen Interviewzitaten und **einer** globalen Ja/Nein-Frage.

### Codepfad
- Der Satz ist `knoepfe._TEXT_SCHAERFUNG_LAEUFT` (`knoepfe.py:506–508`),
  gesendet aus `knoepfe.starte_schaerfung` (`knoepfe.py:2185`) — Systemtext,
  kein Modell.
- Der Block danach ist `schaerfung.szenenvorschlag` (`schaerfung.py`, Funktion
  `szenenvorschlag`, dort `zeilen.extend(f"- {_stelle(...)}")`) bzw.
  `figurvorschlag`; angezeigt über `knoepfe.biete_schaerfung`
  (`knoepfe.py:2132–2169`).
- Die Leiste darunter ist `knoepfe.grundleiste` (`knoepfe.py:1973`): **zwei**
  Knöpfe, „Ja, speichern" / „Nein, nochmal ändern", für den ganzen Block.

### Ursache
Der Schärfungsvorschlag ist der einzige Auswahl-Moment, der **nicht** über
`vorschlag.menuetext` (`vorschlag.py:316`) läuft. Alle anderen — Fragenauswahl,
Geschichte-Richtungen, Sprachstil, Form, Stil — bauen ein nummeriertes Menü mit
fettem Titel, einem Satz Beschreibung und **einem Knopf je Option**. Hier
dagegen: unstrukturierte Liste, jedes Element mit vollem Zitat und
`Vorschlag:`-Zeile, und eine einzige Sammelentscheidung. Formal steht das sogar
so im Phasenprompt (`prompts/phasen/5.md`, Zeile 61–66: „danach kommt je Szene
und je Figur eine Vorschlagsnachricht mit der Rückspiegelung") — der Fehler
sitzt im Code, nicht im Prompt.

Zweiter Verstärker: `starte_schaerfung` läuft im **Phaseneintritt**
(`knoepfe.eintritt_in_phase`, Zweig `PHASE_SCHAERFUNG`, `knoepfe.py:4097–4102`)
und legt seine Vorschläge damit **zeitgleich** über den noch laufenden
Szenenfolge-Lauf (13:53:42 Schärfung, 13:54:10 Szenenfolge, 13:54:20 nächste
Schärfung, 13:54:37 Szenenspeicherung). Zwei unabhängige Fragestränge im selben
Chatfenster — das ist die eigentliche Wall of Text.

### Minimaler Fix
1. `schaerfung.szenenvorschlag` liefert statt eines Textblocks eine
   Optionenliste; `knoepfe.biete_schaerfung` baut daraus ein Menü über
   `vorschlag.menuetext` — **Überschrift** („Szene 1: Am Steg — was aus den
   Interviews dazupasst"), dann nummerierte Kurzoptionen (Thema + max. 12
   Wörter Zitat), ein Knopf je Stelle (Mehrfachauswahl-Toggle wie bei der
   Fragenauswahl, `telegram.aktualisiere_knoepfe`) plus „Diese übernehmen" und
   „Keine davon". Sortiert: erst die Stellen mit Szenenbezug, dann die
   figurgebundenen.
2. Sortierung/Länge deckeln: höchstens drei Stellen je Nachricht.
3. Die Schärfung darf erst starten, wenn kein anderer Vorschlagslauf offen ist
   (Sperre wie `szenenfolge._sperre_fuer`).

Aufwand **M**, Dateien `schaerfung.py`, `knoepfe.py`; Code → Neustart.

---

## 3. Nach der USA-Einwilligung kam direkt Szene 1 statt der Prosafassung

### Symptom
13:55:26 USA-Knopf „ja" → 13:55:26 „Ich schreibe die Szene aus, das dauert eine
Minute." → 13:56:44 ein Text über **eine** Szene. Der Teil-4-Umbau sieht an
dieser Stelle die durchgehende Kurzgeschichte vor.

### Befund zu den drei Hypothesen
**(b) trifft zu — und (a) ist ihre Voraussetzung. (c) trifft nicht zu, sondern
das Gegenteil.**

- **(a) Pfad ohne Prosazwang — ja, als Voraussetzung.** Die Gruppe kam über
  `knoepfe._speichere_szenenfolge` (`knoepfe.py:2557–2568`) in die Szenen: nach
  `szenenfolge.lege_an` ruft die Funktion `biete_szene(...)` für Szene 1. Das
  ist der Phase-4-Weg. `biete_szene` (`knoepfe.py:2338`) überspringt in Phase ≤ 6
  nur die Formfrage und bietet danach „Passt, schreiben" an — also den
  **Einzelszenen**-Knopf `ART_SZENE_SCHREIBEN`. Ein Prosaschritt wird auf diesem
  Weg an keiner Stelle erzwungen.
- **(b) Der gemerkte Auftrag startet `szene.starte` — belegt.**
  `knoepfe._schreibe_szene` (`knoepfe.py:2709–2712`) baut den Auftragstext
  „Schreib Szene 1." und ruft `szene.starte`. Dort greift
  `szene_claude.angebot_faellig` (`szene.py:2155`), der Auftrag wird über
  `repo.merke_szene_usa_angeboten(conn, chat_id, auftrag)` (`szene.py:2156`)
  hinterlegt. Im USA-Handler `knoepfe.py:4898–4902` steht dann:
  `auftrag = repo.hole_und_loesche_offenen_szenenauftrag(...)`, und **wenn ein
  Auftrag da ist, läuft `szene.starte`** — der `elif`-Zweig darunter
  (`knoepfe.py:4903–4907`), der in Phase 6 stattdessen den Knopf
  „Geschichte schreiben" (`biete_kurzgeschichte`) anbieten würde, ist damit
  unerreichbar. Genau dieser Fall trat ein: `gruppe.szene_usa_offener_auftrag`
  ist heute `NULL` (verbraucht), der Szenenlauf steht um 13:56:44 im
  `aufruf`-Protokoll (`art=szene`, 78 s).
- **(c) Phasenübergang durch den Erkenner — nein, umgekehrt.** Zum Zeitpunkt
  des Szenenlaufs stand die Gruppe in **Phase 5** (`journal` 53, 13:53:35). Der
  Erkenner setzte Phase 6 erst um **14:06:24** (`journal` 62,
  `arbeitsstand.phase_gesetzt_am`) — und hat dabei sogar korrekt
  `knoepfe.eintritt_in_phase` durchlaufen (`erkenner._eintritt_nach_phasenwechsel`,
  `erkenner.py:1457–1473`): Einleitung, Checkliste und der Knopf
  „Geschichte schreiben" (Nachrichten 559/560, `knopf` 394) stehen im Protokoll.
  Der Eintrittsschritt wurde also **nicht übersprungen** — er kam zehn Minuten
  zu spät, weil die Szenen-Knöpfe schon in Phase 5 zur Verfügung standen.

Nebenbefund, der das Bild vervollständigt: der Lauf um 13:56:44 war
**inhaltlich schon Prosa** — `szene.schreibt_prosa` (`szene.py:238`) liefert bei
Phase 5 ≤ 6 `True`, deshalb landete der Text in `szene(4).prosa` (4525 Zeichen)
und `volltext` blieb leer. Es fehlte also nicht der Prosa-Modus, sondern die
**Ganzheit**: geschrieben wurde ein Abschnitt statt der Geschichte, weil der
Auftrag „Schreib Szene 1." lautete.

### Minimaler Fix
In `knoepfe._wirke`, Zweig `ART_SZENE_USA` (`knoepfe.py:4898`), die Reihenfolge
umdrehen: **erst** Phase prüfen, dann Auftrag.

```
if phasen.aktuelle(conn, chat_id) == PHASE_SZENEN:
    repo.hole_und_loesche_offenen_szenenauftrag(conn, chat_id)   # verwerfen
    biete_kurzgeschichte(conn, tg, chat_id, _TEXT_KURZGESCHICHTE_BEREIT)
else:
    <bisheriger Auftragsweg>
```

Zweitens: `knoepfe.biete_szene` darf den Knopf „Passt, schreiben" in Phase ≤ 6
gar nicht anbieten, solange keine Prosa der ganzen Geschichte existiert — an
dieser Stelle gehört „Geschichte schreiben". Aufwand **S**, Datei `knoepfe.py`,
Code → Neustart.

---

## 4. Warum aus 3 Szenen 6 wurden

### Symptom
Im Feld `geschichte` und im Journal (`journal` 52, 13:52:20) standen drei Szenen
**mit festgelegter Form**: Chor mit Dance / Dialog mit Monolog-Einschüben / Rap
eskaliert. Es entstanden 6 Szenen mit anderen Titeln und anderen Formen — und
später noch einmal 6.

### Was tatsächlich passierte (Reihenfolge korrigiert)
Der Neuaufbau geschah **zweimal**, und der erste lag **vor** der Kürzungs-Rückmeldung:

1. **13:54:37 — erster Neuaufbau.** Ausgelöst nicht durch eine Kürzungsbitte,
   sondern durch den regulären Weg der Richtungswahl: `_speichere_geschichte`
   (`knoepfe.py:2630–2631`) ruft am Ende **immer**
   `szenenfolge.starte_geschichte_szenen`. Der Lauf (13:52:20 angekündigt,
   13:54:10 fertig, 110 s) erzeugte eine frische Folge, der Knopf „Ja, speichern"
   übernahm sie, und `szenenfolge.lege_an` (`szenenfolge.py:267 ff.`) entfernte
   dabei **alle** bestehenden Szenen weich:
   `for alt in repo.hole_szenen(...): repo.entferne_szene(...)` — belegt durch
   `entfernt_am = 13:54:37` an den ids 1–3.
2. **14:06:24 — Reaktion auf die Kürzungsbitte.** Das Gesprächsmodell
   antwortete mit einer neuen, kompletten Szenenliste im Fließtext
   (Nachricht 557). Der Erkenner las daraus `szene_planen`
   (`erkenner._wende_szene_planen_an`, `erkenner.py:620 ff.`) und schrieb Felder
   der Szenen 1–4 um (`szene` ids 4–7, `geaendert_am = 14:06:24`); zugleich
   setzte er Phase 6.
3. **14:09:35 — zweiter Neuaufbau.** Der Prosa-Lauf aus dem Phaseneintritt
   ersetzte über `kurzgeschichte.lege_szenen_an` (`kurzgeschichte.py:143–155`)
   erneut alles: dieselbe Schleife `entferne_szene` über alle Bestandszenen,
   ids 4–9 raus, ids 10–15 neu.

### Ursache — zwei getrennte Wurzeln
**(i) Eine Kürzungsanweisung wird als Neuaufbau wirksam, weil der Bot keinen
Kürzungspfad kennt.** Es gibt keine Art `szene_kuerzen` und keinen Knopf
„kürzer". Der einzige Weg, auf dem eine Textkritik im System wirkt, ist der
Gesprächszug — und dessen Antwort wird vom Erkenner als Planung gelesen. Der
Bot sagte in Nachricht 557 selbst: „ich kann den Text nicht selbst kuerzen —
der liegt mir nicht vor" (er sieht `szene.volltext`, hier stand der Text aber
in `szene.prosa`; `kontext._baue_szene`, `kontext.py:586–589`, prüft nur
`volltext`). Er wich deshalb auf das aus, was er kann: einen neuen Vorschlag.
Der Weg über „Passt, aber anders" (`ART_SZENE_ANDERS`, Regie-Notiz) stand als
Knopf da (`knopf` 391, 13:56:44), wurde aber nicht gedrückt — die Kritik kam als
freier Text.

**(ii) Bestehende Szenen werden grundsätzlich ersetzt, nicht ergänzt.** Beide
Anlege-Funktionen sind ausdrücklich ersetzend gebaut. `szenenfolge.lege_an`
sagt es im Docstring: „**Ersetzend, nicht ergaenzend**: eine neue Folge ist eine
neue Folge". `kurzgeschichte.lege_szenen_an`: „**ersetzend**, wie
`szenenfolge.lege_an`". Die Formfestlegung ging dabei verloren, weil sie nie in
einem Feld stand, das jemand liest: `szene.form` bleibt in Phase 6 bewusst
`NULL`, `form_vorschlag` wird bei jedem Anlegen neu aus der Modellantwort
geschrieben (`szenenfolge.py`, `setze_szenenfeld(..., "form_vorschlag", form)`)
— und die Formen aus 13:52 standen ausschließlich als Fließtext in
`arbeitsstand.geschichte`. In den Prompt gingen sie zwar ein
(`szenenfolge._erfundenes` legt „Bisherige Geschichte" und „Bisherige
Szenenfolge" hinein, `szenenfolge.py:594 ff.`), aber als Anregung: die
Anweisung `ANWEISUNG_GESCHICHTE_SZENEN` (`szenenfolge.py:143 ff.`) enthält
keine Bindung an eine bestehende Folge, und `kurzgeschichte.ANWEISUNG`
(`kurzgeschichte.py:50–58`) sagt sogar ausdrücklich: „Du waehlst die Zahl der
Abschnitte selbst … Eine Szenenfolge aus der Planung ist eine Anregung, keine
Vorgabe".

Dazu kommt ein Datenschaden, der den ganzen Abschnitt schwächt:
`arbeitsstand.geschichte` ist **113 Zeichen** lang, weil
`knoepfe._speichere_geschichte` bei einer Menüwahl die gewählte *Zeile* als
ganze Geschichte speichert (`knoepfe.py:2601`:
`geschichte = wert.strip() if not zeilen else geschichte`). Bogen, Ende und
Konflikt der gewählten Richtung stehen damit als ein Einzeiler da — für jeden
folgenden Lauf ist das die einzige verbindliche Vorgabe.

### Minimaler Fix
1. **Kürzung als eigener Weg.** Unter jedem Prosa-/Szenentext einen Knopf
   „Kürzer (25 %)" neben „Passt, aber anders"; Wirkung = derselbe
   Überarbeitungspfad mit fester Regie-Notiz, **ohne** neue Szenenfolge.
2. **`kontext._baue_szene` auf `prosa` erweitern** (`kontext.py:586`), damit der
   Gesprächs-Bot nicht mehr sagen muss, der Text liege ihm nicht vor.
3. **Ersetzen nur noch auf ausdrückliche Ansage** — siehe Abschnitt B.

Aufwand **M**, Dateien `knoepfe.py`, `kontext.py`, `szene.py`; Code → Neustart.

---

## 5. Warum der Prosatext erst danach kam

Zwei Prosatexte, beide belegbar:

- **13:56:44** entstand die Prosa **einer** Szene (`szene(4).prosa`,
  4525 Zeichen, `volltext` leer). Sie kam sofort nach der USA-Einwilligung —
  aber als Einzelszene, weil der gemerkte Auftrag „Schreib Szene 1." lautete
  (Abschnitt 3).
- **14:09:35** entstand die Kurzgeschichte am Stück (Lauf `art=kurzgeschichte`,
  150 s, 6 Abschnitte, `szene` ids 10–15 mit je 1661–2518 Zeichen `prosa`).

Die Reihenfolge erklärt sich vollständig aus der Phase: `kurzgeschichte.starte`
ist ausschließlich über `ART_GESCHICHTE_SCHREIBEN` erreichbar
(`knoepfe.py:2694–2714`, Kommentar: „Der EINE Weg in den Prosa-Lauf"), und
dieser Knopf wird nur in `knoepfe.eintritt_in_phase` bei `PHASE_SZENEN = 6`
gelegt (`knoepfe.py:4108–4126`). Die Gruppe stand bis 14:06:24 in Phase 5 —
also gab es den Knopf schlicht nicht. Sichtbar wurde er in derselben Sekunde,
in der der Erkenner die Phase setzte (`knopf` 394, 14:06:24), gedrückt wurde er
40 Sekunden später.

Der Auslöser für den Phasenwechsel war die Kürzungs-Rückmeldung: der Erkenner
las aus dem Zug um 14:06 ein `phase_setzen`. Anders gesagt — **die Kritik am zu
langen Text war das Ereignis, das die Gruppe überhaupt erst in die Phase
brachte, in der die Kurzgeschichte vorgesehen ist.** Der Prosaschritt kam nicht
zu spät, weil etwas fehlschlug, sondern weil der Szenenweg schon eine Phase
früher offenstand.

---

## B. Das Grundproblem: frühe Festlegungen sind nicht verbindlich

Die fünf Befunde haben eine gemeinsame Wurzel. Eine Festlegung der Gruppe
existiert im System heute in **drei** unterschiedlichen Qualitäten:

1. **Als Feld** (`arbeitsstand.rahmen`, `figur.name`) — überlebt.
2. **Als Fließtext in einem Feld** (`arbeitsstand.geschichte`: „Szene 1: Chor …")
   — geht in Prompts ein, bindet aber nichts.
3. **Als Journalzeile** (`journal` 52, 59) — dokumentiert, wirkt nie.

Alles, was in Qualität 2 oder 3 liegt, wird beim nächsten Lauf neu erfunden.
Die Stellen, an denen das passiert, sind benennbar:

| Stelle | Was verloren geht |
|---|---|
| `szenenfolge.lege_an` (`szenenfolge.py:267`) | alle bestehenden Szenen inkl. `form`, `form_vorschlag`, `was_passiert`, `volltext`/`prosa`, Besetzung |
| `kurzgeschichte.lege_szenen_an` (`kurzgeschichte.py:143`) | dasselbe, zusätzlich fertige Prosafassungen |
| `knoepfe._speichere_geschichte` (`knoepfe.py:2601`) | Bogen/Ende/Konflikt werden auf eine Zeile reduziert |
| `erkenner._wende_szene_planen_an` (`erkenner.py:620`) | überschreibt Szenenfelder aus einem Gesprächssatz, feldweise, ohne Rückfrage |
| `knoepfe` `ART_FIGUR_INTERVIEW` (`knoepfe.py:4581`) | setzt `sprachprofil` zurück |

Die Ausnahmen zeigen, dass das Haus die Regel schon kennt: das Journal wird nur
angehängt, Verdichtungen werden nie geändert, `repo.setze_szenenfeld` rührt nie
mehr als ein Feld an, die Grundleiste speichert nie über ein gesetztes Feld
(`knoepfe._feld_ist_frei`). Nur die **Szenenfolge** ist davon ausgenommen.

### Vorgeschlagenes Prinzip

> **Bestehende Szenen werden nie ersetzt, nur ergänzt oder geändert — und jede
> Änderung an einer Szene, die die Gruppe schon bestätigt hat, braucht einen
> ausdrücklichen Druck.**

Konkret erzwingbar an vier Stellen:

1. **`repo`:** eine Funktion `gleiche_szenenfolge_ab(conn, chat_id, zeilen)`, die
   nach Nummer abgleicht statt zu löschen — vorhandene Szenen bekommen
   geänderte Felder, fehlende Nummern werden ergänzt, überzählige bleiben mit
   einem Vermerk stehen und werden **nur nach ausdrücklicher Bestätigung**
   entfernt. `szenenfolge.lege_an` und `kurzgeschichte.lege_szenen_an` rufen
   ausschließlich diese Funktion; `repo.entferne_szene` verschwindet aus beiden.
2. **Festlegungen als Felder, nicht als Fließtext:** die Formentscheidung je
   Szene gehört bei ihrer Entstehung in `szene.form_vorschlag` (bzw. `form`,
   sobald bestätigt) und nicht nur in `arbeitsstand.geschichte`. Der
   Richtungs-Knopf müsste die Szenenzeilen der gewählten Richtung mitspeichern,
   statt sie zu verwerfen.
3. **Der Prompt muss binden, nicht anregen:** wo Szenen bestehen, gehört in
   `kurzgeschichte.ANWEISUNG` und `ANWEISUNG_GESCHICHTE_SZENEN` der Satz
   „Anzahl, Reihenfolge und Form der bestehenden Szenen sind **verbindlich**;
   du schreibst sie aus, du erfindest sie nicht neu" — statt der heutigen
   Formulierung „Anregung, keine Vorgabe". Das ist eine Prompt-Änderung und
   wirkt heiß.
4. **Ein Test, der es festhält:** „ein zweiter Szenenfolge-Lauf über eine
   bestehende Folge ändert keine `szene.id` und keine `form`" — analog zu
   `test_teil4_kurzgeschichte`.

---

## C. Maßnahmen, priorisiert

| # | Maßnahme | Dateien | Art | Aufwand | Wann |
|---|---|---|---|---|---|
| 1 | **USA-Handler: Phase vor Auftrag prüfen** — in Phase 6 den gemerkten Einzelszenen-Auftrag verwerfen und `biete_kurzgeschichte` anbieten (`knoepfe.py:4898`) | `knoepfe.py` | Code (Neustart) | S | so früh wie möglich, in einer Pause |
| 2 | **Prompts auf „bestehende Folge ist verbindlich" umstellen** — `kurzgeschichte.ANWEISUNG`-Anteil in `prompts/formen/prosa.md`, `phasen/4.md`, `phasen/6.md` | `prompts/**` | Prompt-only (heiß) | S | **sofort möglich, ohne Neustart** |
| 3 | **Knopf „Zufällig zuordnen"** für Interview→Figur (Abschnitt 1) | `knoepfe.py`, Test | Code (Neustart) | S | nächste Pause — spart pro Gruppe ~12 min |
| 4 | **Kürzungs-Knopf** („Kürzer") unter Prosa- und Szenentexten, wirkt als Überarbeitung ohne neue Folge | `knoepfe.py`, `szene.py` | Code (Neustart) | M | nach dem Workshop-Tag, falls kein Fenster |
| 5 | **`kontext._baue_szene` liest auch `prosa`** — der Bot behauptet sonst weiter, der Text liege ihm nicht vor | `kontext.py` | Code (Neustart) | S | zusammen mit 1/3 |
| 6 | **Schärfungsvorschlag als Menü** (Überschrift + max. 3 sortierte Optionen + Knopf je Stelle) | `schaerfung.py`, `knoepfe.py` | Code (Neustart) | M | nach dem Workshop |
| 7 | **Schärfung und Szenenfolge nicht gleichzeitig** — gemeinsame Sperre je `chat_id` | `knoepfe.py`, `schaerfung.py` | Code (Neustart) | S | nach dem Workshop |
| 8 | **`gleiche_szenenfolge_ab` statt Ersetzen** (Abschnitt B.1), beide Aufrufer umstellen | `repo.py`, `szenenfolge.py`, `kurzgeschichte.py`, Tests | Code (Neustart) | L | **nach** dem Workshop — Schemaverhalten, nicht live |
| 9 | **Richtungswahl speichert die Szenenzeilen mit** statt sie zu verwerfen (`knoepfe.py:2601`) | `knoepfe.py` | Code (Neustart) | M | nach dem Workshop |
| 10 | **`szene_kuerzen` als Erkenner-Art** + zwei Korpusfälle (Kritik am Text ist keine Planung) | `prompts/erkenner.md`, `erkenner.py`, `korpus/` | Prompt + Code | M | nach dem Workshop, mit Korpuslauf |
| 11 | **`biete_szene` bietet in Phase ≤ 6 kein „Passt, schreiben"** an, solange keine Gesamtprosa existiert | `knoepfe.py` | Code (Neustart) | S | mit 1 zusammen |

**Während des laufenden Workshops vertretbar:** 2 (heiß, kein Neustart) und —
in einer Pause, als einzelner Neustart je Gruppe — das Bündel 1 + 5 + 11, weil
es dieselbe Datei betrifft und den heute beobachteten Ablauffehler direkt
abstellt. Alles Weitere, insbesondere 8, gehört hinter den Workshop: es ändert
das Verhalten beim Anlegen von Szenen und ist nicht in einer Pause zu
verifizieren.

---

## Anhang: was nachweislich **nicht** die Ursache war

- **Kein technischer Fehlschlag.** Ein einziger `vorfall` in der Stunde
  (`http_5xx`, ReadTimeout, Wiederholung erfolgreich, 13:49:53). Alle 42
  Modellaufrufe mit `erfolg = 1`, beide großen Läufe mit
  `finish_reason = end_turn`, kein `szene_abgeschnitten`, kein
  `kontext_gekuerzt`, kein `szene_prompt_gekuerzt`.
- **Kein Knopf-Doppeldruck.** Jede `knopf`-Zeile hat höchstens ein
  `benutzt_am`; die Idempotenz-Sperre hat gehalten.
- **Kein USA-Fehlschalter.** `gruppe.szene_usa_bestaetigt_am` = `ja:…`, der
  Bool-Vergleich in `knoepfe.py:4884` hat korrekt gegriffen.
- **Kein PII-Leck im Chat.** Die Schärfungs- und Stilvorschläge nennen
  durchgängig „Interview N", keine Namen — wie in `prompts/phasen/5.md`
  gefordert.

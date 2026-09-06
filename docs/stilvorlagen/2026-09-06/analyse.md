# Stilvorlagen aus Videomaterial — Messung und Befund (06.09.2026)

Zweck: Aus den von Birk benannten Videos je Gruppe eine **Meta-Anleitung**
(Stil-Overlay fuer den Feinschliff, Phase 7) ableiten. Analysiert wird
ausschliesslich der **gesprochene/gesungene Text**, nicht das Video.

## Urheberrechtsvermerk

Die untersuchten Texte sind urheberrechtlich geschuetzte Song- bzw.
Stuecktexte. Deshalb:

- **Keine Volltranskripte im Repository.** Die Arbeitskopien liegen nur lokal
  unter `/tmp/it-stil-transkripte/` (fluechtig, nicht committet, nicht
  gesichert).
- Im Repo stehen ausschliesslich **Kurzzitate als Beleg (max. 4 Zeilen)** im
  Rahmen des Zitatrechts (§ 51 UrhG), jeweils mit Quellenangabe.
- Die abgeleiteten Meta-Anleitungen enthalten **keine uebernommenen Textzeilen
  als Vorlage zum Nachbauen**, sondern nur Formregeln plus selbst
  geschriebene, inhaltlich neutrale Beispiele.
- Die Zitate dienen der Analyse und stehen nie im erzeugten Buehnentext.

## Quellenlage / Werkzeugweg

Anweisung: nur **mitgelieferte YouTube-Untertitel**, kein Whisper.

| Video | Titel | Kanal | Dauer | Sprache | Untertitel |
|---|---|---|---|---|---|
| `kIa3kjlwbSg` | MONET192 ueber Depressionen, Trennung von Ex, Bruch mit Bruder, Wutausbrueche, kein Vater \| Interview | Deutschrap ideal | 49:15 | de | **keine** |
| `yudmv-futDk` | SCHATTEN — Morpheuz x Monet192 (prod. by Perino & Angelo) | MORPHEUZ | 2:55 | de | ja (auto) |
| `47uzk6sUoUI` | Lovesong | Adele – Topic (Cover, Original: The Cure) | 5:32 | en | ja (auto) |

Weg (dokumentiert fuer Wiederholbarkeit): `youtube-transcript-api` und die
YouTube-eigenen Pfade laufen von diesem Server in die Bot-Wall bzw. die
Egress-Allowlist (uid `birk` erreicht `youtube.com` nicht; `playabilityStatus:
LOGIN_REQUIRED`). Genutzt wurde daher Stufe 4 der Fallback-Leiter aus
`media-to-transcript/references/youtube-transcript-fallbacks.md` ueber den
Browser-Broker (kome.ai). Fuer `kIa3kjlwbSg` melden **zwei unabhaengige
Dienste** uebereinstimmend „Transcript could not be fetched / keine Untertitel
vorhanden" — das Interviewvideo hat schlicht keine Untertitelspur. Da Whisper
ausgeschlossen ist, wurde dieses Video **nicht transkribiert**.

Einschraenkung: Die Auto-Captions liefern **keine verwertbaren Zeitstempel**
(kome.ai gibt reinen Fliesstext). Belegstellen werden deshalb strukturell
verortet (Strophe 1, Refrain, Bridge) statt per `mm:ss`. Auto-Captions
enthalten ausserdem Hoerfehler („Rust mich an", „verstein", „F?") — diese
Stellen sind fuer Wortanalyse unbrauchbar, fuer **Form**analyse (Zeilenlaenge,
Wiederholung, Anrede, Reimposition) aber belastbar.

## Messwerte

Gemessen auf dem bereinigten Text (Musikmarker entfernt).

| Kennzahl | `yudmv-futDk` (Gruppe 2) | `47uzk6sUoUI` (Gruppe 3) |
|---|---|---|
| Woerter gesamt | 273 | 187 |
| verschiedene Woerter | 126 | 32 |
| Type-Token-Ratio | 0,46 | **0,17** |
| Saetze / Sinneinheiten | 34 | ~8 (Captions ohne Interpunktion) |
| Median Woerter je Satz | **6,5** | **7** (Zeilenlaenge) |
| Mittel Woerter je Satz | 8,0 | 7 |
| laengste Einheit | 19 Woerter | 9 Woerter |
| 3-Gramm-Wiederholungsquote | 36,5 % | **81,6 %** |
| 4-Gramm-Wiederholungsquote | 30,7 % | 76,1 % |
| 5-Gramm-Wiederholungsquote | 25,7 % | 69,9 % |
| Anrede „ich" | 16 | 25 |
| Anrede „du/you" | 13 | 26 |
| Anrede „wir/we" | 4 | 0 |
| Instrumental-/Musikpausen | 26 | 13 |

Zum Vergleich das bestehende **Herkules-Mass** (ArtesMobiles-Produktion):
Szene 700–1500 Woerter, Repliken median 8 Woerter, Regie ≤ 20 %. Die
Replikenlaenge beider Vorlagen (6,5 bzw. 7) liegt **dicht am Herkules-Median**
— die Vorlagen widersprechen dem Mass also nicht, sie schaerfen es.

## Befund je Video

### `yudmv-futDk` — SCHATTEN (Gruppe 2)

- **Form:** Deutschsprachiger Rap/Sung-Rap, Ich-an-Du gerichtet, Strophe →
  Hook → Strophe → Hook → Abbruch. Kurze Zeilen (Median 6,5 Woerter), viele
  Negationen (`nicht` ist das haeufigste Wort ueberhaupt, 16×), Fragen ohne
  Antwort, Vokativ („Baby"). Reim unrein und am Zeilenende
  (`vorbei sein` / `entfernt`, `Nacht` / `Frage`). Wiederholung mittel
  (30–36 %): eine Hook kehrt woertlich wieder, die Strophen nicht.
- **Rhythmus:** Zeilen brechen mitten im Satz um; der Satz laeuft ueber die
  Zeile hinweg (Enjambement) und wird durch die Musikpausen (26 Marker)
  zerteilt. Kein durchgehendes Silbenmass, aber konstante Betonungszahl.
- **Haltung:** Verletzt-aggressive Zaertlichkeit — Besitzanspruch, Eifersucht,
  Frage-Kaskaden, Selbstvorwurf. Bildsprache: Schatten, Teufelskreis, Kopf.
- **FORM (uebertragbar):** kurze Zeilen; direkte Du-Anrede; Negations- und
  Fragehaeufung; eine woertlich wiederkehrende Hook; unreiner Endreim;
  Zeilenumbruch gegen den Satzbau; Abbruch statt Fazit.
- **INHALT (nicht kopieren):** Liebeskummer, Untreue, Eifersucht, „Baby",
  Schatten-Metapher, jede konkrete Zeile.

### `47uzk6sUoUI` — Lovesong (Gruppe 3)

- **Form:** Englischsprachige Ballade mit extremer Litanei-Struktur. TTR 0,17
  und 82 % wiederholte Dreiwortfolgen: der Text besteht fast vollstaendig aus
  **einer Satzschablone mit ausgetauschtem Schlusswort**
  (`home again` / `whole again` / `young again` / `fun again` / `free again` /
  `clean again`). Refrain (`however far away …`) kehrt woertlich wieder.
- **Rhythmus:** Sehr kurze, gleich lange Zeilen (7 Woerter, ca. 6–8 Silben),
  Zeilenende = Atempause, keine Enjambements gegen den Satz.
- **Haltung:** Ruhig, zugewandt, keine Steigerung, kein Konflikt. Die Dramatur-
  gie liegt nicht im Was, sondern im **Wie oft**: Bedeutung entsteht durch
  Akkumulation, nicht durch Entwicklung. Schluss = leichte Variation
  (`cuz I love you`).
- **FORM (uebertragbar):** Satzschablone mit einer variablen Stelle; woertlich
  gleicher Refrain; sehr kleiner Wortschatz; gleich lange Zeilen; Steigerung
  ausschliesslich durch Wiederholung; Schluss als minimale Abweichung.
- **INHALT (nicht kopieren):** Liebeserklaerung, „I will always love you",
  jede englische Zeile, jede konkrete Wortwahl.

### `kIa3kjlwbSg` — Interview (Gruppe 2, zweite Quelle)

**Nicht analysiert.** Keine Untertitelspur vorhanden (zwei Dienste
uebereinstimmend), Whisper per Anweisung ausgeschlossen. Die Gruppe-2-Anleitung
stuetzt sich daher allein auf `yudmv-futDk`. Was das Interview beigetragen
haette (Sprechregister, Fuellwoerter, Gespraechsdynamik im Dialog), fehlt —
siehe offene Punkte in `gruppe2-stil.md`.

## Abgrenzung Form / Inhalt — Regel fuer die Anwendung

Uebernommen wird **nur die Bauweise**: Zeilenlaenge, Anrede, Wiederholungs-
mechanik, Reimlage, Position des Bruchs. Uebernommen wird **nie**: Motive,
Metaphern, Vokabular, Figurenkonstellation oder Themen der Vorlage. Der
Inhalt kommt weiterhin ausschliesslich aus den Interviews der Gruppe.
Konkret verboten: Schatten/Teufelskreis-Bildlichkeit, „Baby"-Anrede,
`always love you`-Formeln, Liebeskummer als Thema, englische Textzeilen.

## Empfehlung zum Einhaengen (5 Zeilen)

1. Inhalt von `gruppe2-stil.md` bzw. `gruppe3-stil.md` als
   `zusatz.theatersoap2_bot.md` / `zusatz.theatersoap3_bot.md` **neben die DB**
   legen (`$(dirname $IT_DB)`); fuer Gruppe 1 keine Datei anlegen.
2. Geprueft in `anweisungen.py::system()`: der Zusatz wird **phasenunabhaengig**
   geladen (Basis → `phasen/<phase>.md` → `zusatz.md` → `zusatz.<bot>.md`) —
   es gibt **keine** Phasenbedingung fuer das Overlay.
3. Ausserdem: `system()` betrifft das **Gespraech**; der Szenentext entsteht in
   `szene.systemanweisung` — ein Overlay neben der DB wirkt also nicht
   automatisch auf den Feinschliff.
4. Empfehlung (nicht gebaut): in `szene.systemanweisung` einen Abschnitt
   `## Stil dieser Gruppe` einfuegen, der `zusatz.stil.<bot>.md` nur dann
   anhaengt, wenn `form != "prosa"` — so wirkt die Vorlage in Phase 7 und
   stoert die Prosa-Kurzgeschichte in Phase 6 nicht.
5. Fallback ohne Codeaenderung: die Datei trotzdem als `zusatz.<bot>.md`
   ablegen und mit dem Satz „Diese Regeln gelten nur, wenn du Szenentext in
   einer Form schreibst (Dialog, Monolog, Chor, Lied, Rap) — nicht im
   Gespraech und nicht in der Prosafassung." einleiten (so in beiden Dateien
   bereits vorangestellt).

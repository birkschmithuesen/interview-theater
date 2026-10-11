# InScribe Messung 2: A/B Pipeline gegen Agent mit Stückmodell-Werkzeugen — Design

Karte `t_c0056676` (Plan) → Umsetzung `t_9b2b33cb` (Branch `wt/t_9b2b33cb`).
Stand: 11.10.2026. Primärquelle der Fragestellung:
`~/hermes-shared/hermes-entities/entities/artesmobiles/projekte/inscribe/grundsatz-architektur-und-kollektiver-prozess.md`,
Folie 4 „Pipeline gegen Agent“ und Folie 7, Prüfweg Schritt 2 („Pipeline gegen
Agent auf einer Kopie der Padua-Daten … Kennzahlen: Treffer, stille Fehler,
Latenz, Kosten.“).

**Was diese Karte liefert:** Zahlen für Birks Grundsatzentscheidung. Keine
Empfehlung „umstellen“ ohne Zahlen; die Entscheidung trifft Birk. Default
bleibt `IT_ERKENNER_MODUS=json`, kein Bot-Neustart.

## 1. Drei Achsen

| Achse | Pipeline (heute) | Agent | Datengrundlage | Bedingung |
|---|---|---|---|---|
| **A Erkenner, Korpus** | Opus füllt das JSON-Schema (`erkenner.schema()`, 34 `ARTEN`), dann Wächter + `wende_an` | Opus ruft Werkzeuge: `stueck.WERKZEUGE` + ein generisches Werkzeug für die übrigen Arten | `korpus/erkenner.jsonl` (157) + `korpus/en/erkenner.jsonl` (103) | keine — läuft immer |
| **B Erkenner, Padua-Testsatz** | wie A | wie A | Padua-Testsatz aus Messung 1 (`t_dd94e894`/`t_7321edc8`/`t_0fedafe0`) auf `VACUUM INTO`-Kopie von `betrieb/padua.db` | 🔴 ANNAHME: Format unbekannt, siehe § 6 |
| **C Zitatsuche** | `schaerfung._mappe_ziel` je Szene/Figur, Pool = `repo.gepruefte_themen` (ein Beleg je Thema), Top-10 nach `staerke` | EIN Modell sucht selbst über das Interview-Archiv (Volltextsuche als Werkzeug), Top-10 Stellen | Gold-Korpus aus `t_2349e9a8`/`t_2f905d2c`, G1/G2/G3 | 🔴 ANNAHME: Gold-Korpus existiert heute nicht, siehe § 7 |

## 2. Geklärte Design-Fragen

### 2.1 Unterstützt der Proxy `tools`? — Ja (gemessen 11.10.2026)

Zwei Aufrufe gegen `http://127.0.0.1:28764/v1/messages`, Modell
`claude-opus-5-5`, Abo (0 CHF), kein Eingriff in den Betrieb:

1. Anfrage mit `tools: [{name: "setze_ort", input_schema: …}]` und
   `tool_choice: {type: "auto"}` → Antwort `stop_reason: "tool_use"`,
   `content: [{type: "tool_use", name: "setze_ort", input: {szene: 2, ort: "Küche"}}]`.
2. Folgeanfrage mit dem `tool_use`-Block als `assistant`-Nachricht und einem
   `tool_result` als `user`-Nachricht → `stop_reason: "end_turn"`, Text.

Der Proxy reicht `tools`, `tool_choice`, `tool_use` und `tool_result`
vollständig durch. Die Tools-Variante ist baubar wie beschrieben. Der Plan
wiederholt diese Probe als Task 0 (Vorbedingung, denn der Proxy kann sich
ändern).

### 2.2 Terminierung der Werkzeugschleife

Eine Schleife `Modell → tool_use → ausführen → tool_result → Modell` endet
deterministisch bei der ersten dieser Bedingungen:

- `stop_reason != "tool_use"` (Modell fertig) → `abbruch = None`;
- `MAX_RUNDEN = 6` Modellaufrufe erreicht → `abbruch = "runden"`;
- `MAX_WERKZEUGAUFRUFE = erkenner.MAX_AENDERUNGEN` (heute 5) ausgeführte
  Aufrufe erreicht → weitere `tool_use`-Blöcke werden nicht ausgeführt,
  sondern mit `tool_result {is_error: true, "Grenze erreicht"}` beantwortet,
  und die Schleife endet → `abbruch = "aufrufe"`;
- `GESAMT_TIMEOUT_S = 120.0` Wandzeit überschritten (geprüft vor jedem
  Modellaufruf) → `abbruch = "zeit"`.

Ein Abbruch ist laut: Vorfall `erkenner_werkzeug_abbruch` (Betrieb) bzw.
eigene Spalte im Bericht (Messung). Was bis dahin ausgeführt wurde, bleibt
ausgeführt (das ist Agent-Semantik und wird so gemessen).

**Fallback:** Scheitert der **erste** Modellaufruf (Proxy-Fehler,
`ClaudeFehler`), ist noch nichts ausgeführt → derselbe Fallback wie heute
(`modellwahl.aufruf_schema` → Kimi/gemma, JSON-Pfad, Vorfall
`opus_fallback`). Scheitert ein **späterer** Aufruf, wurde schon geschrieben
→ kein Fallback (ein JSON-Lauf über dasselbe Fenster würde doppelt
schreiben), Abbruch `abbruch = "fehler"`, Vorfall.

### 2.3 Was „still falsch gespeichert“ in der Tools-Variante heißt

Der Korpus erwartet `{"art", "wert"}`-Mengen. Die Tools-Variante wird in
**dieselbe Sprache** zurückübersetzt, damit `pruefe_prompts.vergleiche_erkenner`
unverändert zählt:

- **generisches Werkzeug** `aenderung_melden(art, wert)` → genau
  `{"art": art, "wert": wert}`, danach wie heute `erkenner.waechter_filter`;
- **Stückwerkzeug mit `ergebnis.ok == True`** → über eine feste
  Abbildungstabelle (`erkenner_werkzeuge.ART_FUER_WERKZEUG`):

  | Werkzeug | Korpus-`art` | `wert` (für `wert_passt`, Teilstring beidseitig) |
  |---|---|---|
  | `setze_rahmen` | `rahmen_setzen` | `rahmen` |
  | `setze_ort`, `setze_besetzung`, `figur_aus_szene`, `karte_aendern` | `szene_planen` | alle String-Argumente, mit Leerzeichen verbunden |
  | `figur_hinzu` | `figur_setzen` | `name` + `beschreibung` |
  | `frage_*`, `szene_wieder_oeffnen`, `reihenfolge_aendern`, `pruefe_szene` | — (`None`) | zählt als **„Werkzeug ohne Korpus-Art“** |

- **Stückwerkzeug mit `ok == False`** → zählt nicht als Speicherung, sondern
  in einer eigenen Spalte **„abgelehnt (laut)“** — `stueck` hat es mit
  `fehler` verweigert, das Modell hat es im `tool_result` gesehen. Das ist
  der gesuchte Unterschied zum JSON-Pfad, wo ein ungültiger Wert still in
  `wende_an` verschwindet.

**Stille Fehler** je Variante = gespeicherte Änderungen, die der Korpus
nicht erwartet:

- JSON: `FP` nach `waechter_filter` (wie heute im Korpusbericht);
- Tools: `FP` der zurückübersetzten Menge **plus** „Werkzeug ohne
  Korpus-Art“ mit `ok == True` (konservativ: es hat den Stand geändert, ohne
  dass jemand es verlangt hat). Beide Teilsummen stehen getrennt im Bericht.

Die Abbildungstabelle ist eine Messgrenze und steht als solche im Bericht.

## 3. Architektur der Tools-Variante (Produktivcode, hinter Schalter)

### 3.1 Schalter `IT_ERKENNER_MODUS`

- `einstellungen.Einstellungen.erkenner_modus: str = "json"`, gelesen aus
  `IT_ERKENNER_MODUS`; unbekannter Wert → `"json"` mit Log-Warnung.
- Wirkt **nur**, wenn `erkenner.ueber_claude(e, conn, chat_id)` wahr ist
  (Profilschalter `[erkenner] ueber_claude` + Einwilligung + nicht Phase 3).
  Im gemma/Kimi-Pfad gibt es kein Tool-Calling-Äquivalent; das zu bauen ist
  **nicht in Scope** (Stückmodell-SPEC Zeile 1295: „Werkzeug-Zuschnitt (B-vs-C
  bleibt offen, Folie 7)“ meint EIN starkes Modell, das Werkzeuge ruft).
- Kein neuer Profilschalter, kein Dortmund-Pfad.

### 3.2 Neues Modul `interview_theater/erkenner_werkzeuge.py` (Fachlogik)

Kein SQL, kein Modellaufruf, kein `tg`. Liest `stueck` und `erkenner`.

- `definitionen(arten: tuple[str, ...]) -> list[dict]` — Anthropic-Werkzeug-
  definitionen: je Name aus `stueck.WERKZEUGE` eine aus der Signatur
  (`inspect.signature`, nur Keyword-Only-Parameter; `quelle` und `szene_id`
  ausgeblendet) erzeugte `input_schema`, plus `aenderung_melden` mit
  `art`-Enum = übergebene `arten` (`erkenner.schema()`-Enum, also dieselben
  profil-/phasenabhängigen Arten wie im JSON-Pfad).
- `fuehre_aus(conn, chat_id, name, eingabe) -> Ausfuehrung` — Stückwerkzeug:
  `getattr(stueck, name)(conn, chat_id, **eingabe, quelle=stueck.QUELLE_AGENT)`;
  unbekannter Name / falsche Argumente → `Ausfuehrung(ok=False, fehler=…)`,
  nie eine Ausnahme nach außen. `aenderung_melden` führt **nichts** aus, sondern
  sammelt `{"art", "wert"}` für den heutigen `wende_an`-Weg (dort hängen
  Wächter, Undo, Interview-, Szenen-, Phasenlogik — die bleiben).
- `als_tool_result(ausfuehrung) -> str` — JSON des `stueck.Ergebnis`
  (`ok, aenderung_id, diff, warnungen, veraltet, fehler, frage_id`).
- `als_aenderung(name, eingabe, ausfuehrung) -> dict | None` — die
  Rückübersetzung aus § 2.3 (nur Messung und „Notiert:“-Meldung).
- Konstante `ART_FUER_WERKZEUG`.

**Korrektur zum Brief:** `wende_an` entfällt im Tools-Pfad **nicht ganz**.
Nur `szene_planen`-/`rahmen_setzen`-artige Fakten haben ein Stückwerkzeug;
die übrigen Arten (Interview, Phase, Szene schreiben, Kürzen, Begriffe …)
haben keins und laufen über `aenderung_melden` weiter durch `wende_an`.
Auch `szene_planen` bleibt im Enum: kein Stückwerkzeug legt eine **neue**
Szene an.

### 3.3 Werkzeugschleife in `szene_claude.py`

`werkzeug_schleife(conn, e, klient, chat_id, system, nutzer, werkzeuge,
ausfuehren, *, art, modell=None, max_runden=MAX_RUNDEN,
max_aufrufe=MAX_WERKZEUGAUFRUFE, gesamt_timeout=GESAMT_TIMEOUT_S)
-> Schleifenergebnis` — neuer, dritter Aufrufmodus neben `prosa` und
`schema`; `prosa`/`schema` bleiben zeichengleich. Blockierend (kein Strom),
`kosten.pruefe` vorab, je Runde eine `aufruf`-Zeile (Modus `C`, 0 CHF,
Token aus `usage`). `ausfuehren(name, eingabe) -> (tool_result_text,
is_error)` ist ein Callable, damit die Schleife nichts von `stueck` weiß.
`Schleifenergebnis` (frozen dataclass): `aufrufe: tuple[dict, ...]`
(`name`, `eingabe`, `is_error`), `runden`, `abbruch`, `eingabe_token`,
`ausgabe_token`, `dauer_ms`.

### 3.4 Einhängen in `erkenner.erkenne`

Neue Funktion `erkenne_mit_werkzeugschritten(klm, conn, e, chat_id)
-> tuple[list[dict], list[dict]]` — `(aenderungen, stueck_schritte)`.
`erkenne(klm, conn, e, chat_id) -> list[dict]` wird zu
`return erkenne_mit_werkzeugschritten(...)[0]` und bleibt Signatur- und
Verhaltensgleich. An der Verzweigung vor `_schema_aufruf` (heute Zeile 534):
wenn `e.erkenner_modus == "tools"` **und** `ueber_claude(...)` →
`_werkzeuglauf` (gleicher Prompt `prompt()` plus Werkzeug-Absatz aus
`prompts/erkenner_werkzeuge.md` bzw. `sprachen/en/prompts/erkenner_werkzeuge.md`
über `anweisungen.hole("erkenner_werkzeuge")`; `prompts/erkenner.md` bleibt
unverändert, die FP=0-Invariante des Erkenner-Prompts wird nicht berührt —
der neue Absatz wirkt nur im Tools-Modus), gleicher Nutzertext `_baue_nutzertext`);
sonst wie heute, `stueck_schritte = []`. `stueck_schritte` sind die
zurückübersetzten erfolgreichen Stückwerkzeug-Aufrufe (`als_aenderung`,
ohne `None`). Wasserzeichen und Fenster-Deckel wie heute.

`laufe` ruft `erkenne_mit_werkzeugschritten` und hängt `stueck_schritte` an
`wirkliche` an, damit `baue_meldung` sie in der „Notiert:“-Zeile nennt.

**Undo:** `_wende_an_mit_schnappschuss` hält `repo._LOCK` nur Millisekunden
um `wende_an` (Review-Fix Aufgabe 7); eine Modellschleife darf ihn nicht
sekundenlang halten. Darum deckt der Undo-Knopf im Tools-Modus **nur** den
`aenderung_melden`-Teil ab; Stückwerkzeug-Schritte stehen im
`stueck`-Änderungsprotokoll (`aenderung_id`), aber ohne Undo-Knopf. Das ist
ein Unterschied der Agent-Variante, den der Bericht als Befund nennt — kein
Umbau des Undo in dieser Karte.

`erkenne_in_aufnahme` (Transkripte) bleibt **unverändert** auf Infomaniak/JSON
— in beiden Modi.

## 4. Datenschutz (in beiden Modi gleich)

- Phase 3 (Interviews): `modellwahl.konversation_ueber_claude` liefert
  `False` → `ueber_claude` `False` → Tools-Modus greift nie, Erkenner bleibt
  Kimi/gemma-JSON. Test für **beide** Modi.
- `erkenne_in_aufnahme`: immer Infomaniak, beide Modi. Test.
- Interviewverdichtung (`verdichter.py`): unberührt, hart auf Kimi. Test, dass
  `IT_ERKENNER_MODUS=tools` keinen Verdichter-Aufruf über den Proxy schickt.
- **Achse C, Agent-Variante:** sie liest Volltranskripte (`aufnahme.transkript`).
  Transkripte gehen heute nie in die USA (`szene_claude.py` Docstring: „keine
  Transkripte“). Darum läuft die Zitatsuche-Agentin **auf Kimi (Infomaniak)**,
  nicht auf Opus — das ist Folie 4 („Verdichtungs-Werkzeug hart an Kimi
  binden“). Damit die Achse nicht an Kimis Tool-Calling hängt, ist die
  Agent-Schleife dort eine **Schema-Schleife**: je Runde ein `klm.schema`-
  Aufruf mit `{aktion: "suche"|"fertig", anfrage, stellen[]}`; das Messskript
  führt `suche` lokal aus und hängt die Treffer an den nächsten Nutzertext.
  Gleiche Deckel wie § 2.2. Kein Produktivcode — die Agent-Zitatsuche lebt nur
  im Messskript.
- Messung nur auf einer `VACUUM INTO`-Kopie von `betrieb/padua.db`
  (`mode=ro`, Muster `scripts/stueckmodell_kopie.kopiere`), nie auf
  `betrieb/padua-test*.db`.

## 5. Kennzahlen und Kosten-Asymmetrie

| Kennzahl | Quelle |
|---|---|
| Treffer / FN / FP | `vergleiche_erkenner` (Achse A, B) |
| stille Fehler | § 2.3 |
| abgelehnt (laut) | nur Tools |
| Abbrüche | nur Tools (`abbruch`) |
| Runden je Fall | nur Tools |
| Latenz | Wandzeit je Fall (alle Runden), Median und p90 |
| Token | Summe `usage` aller Runden (`aufruf`-Zeilen) |
| Kosten CHF | Opus = **strukturell 0 CHF (Abo, `kosten.CLAUDE_CHF_JE_AUFRUF`)** — der Bericht nennt dort Token, keine erfundene CHF-Zahl. Echte CHF nur für die optionale gemma-Kontrastzeile (Achse A) und die Kimi-Seite von Achse C (`kosten.PREISE_CHF_JE_MIO_TOKEN`). |
| Recall@10 | Achse C, je Gruppe G1/G2/G3 |

Achse C hat einen Modell-Störfaktor: die Pipeline läuft im Betrieb über Opus
(`schaerfung` mit `szene_claude.ist_aktiv`), die Agentin auf Kimi. Darum misst
C zusätzlich **Pipeline auf Kimi** (`ueber_claude=False`) als Kontrollzeile.

## 6. 🔴 ANNAHME: Testsatz-Format aus Messung 1

Messung 1 ist am 11.10.2026 **nicht gemergt**. Branch `wt/t_dd94e894` ändert
bisher nur `scripts/pruefe_prompts.py` und `tests/test_pruefe_prompts.py`;
`docs/messung/` existiert auf `main` nicht. Das Format des Padua-Testsatzes
ist also unbekannt. Die Umsetzung (`t_9b2b33cb`, wird erst nach Merge von
`t_0fedafe0` `ready`) prüft in Task 0, ob `docs/messung/` oder ein
`tests/padua_testsatz_*`/vergleichbares Format existiert, und gleicht
Achse B daran ab. Fehlt er, entfällt Achse B, der Bericht vermerkt
„0 — Padua-Testsatz fehlte“.

## 7. 🔴 ANNAHME: Gold-Korpus Zitatauswahl

Der Gold-Korpus (positiv: im Stück/auf Plakaten verwendete Stellen; negativ:
vorgeschlagen/verworfen) entsteht in `t_2349e9a8` → `t_2f905d2c` →
`t_20f9dc6b` → `t_e906dce3`; Befund: Board hermes-dev, Karte `t_56f8d856`,
Kommentar 1402 (10.10., Punkt 5 und Hypothese c). Er existiert am 11.10.2026
nicht. **Kein Dateipfad wird angenommen.** Achse C ist eine Spätphase mit
Bedingung: nur wenn der Gold-Korpus beim Start der Umsetzung im Repo-Stand
von `main` liegt (Pfad aus der gemergten Doku von `t_2f905d2c` lesen), sonst
entfällt C, der Bericht vermerkt „0 — Gold-Korpus fehlte“.

## 8. Messskript und Bericht

`scripts/ab_pipeline_vs_tools.py` (als Modul starten), Unterbefehle
`erkenner` (A), `padua` (B), `zitate` (C), `bericht`. Rohdaten je Lauf als
JSONL unter `korpus/berichte/ab/`; `bericht` baut
`docs/messung/2026-10-ab-pipeline-vs-tools.md` daraus (Tabelle je Kennzahl,
Kommandos zum Nachrechnen, Abschnitt „Was die Messung NICHT zeigt“: Live mit
Laien, Gruppenerlebnis, Gesprächsführung, Langzeitstabilität, Wirkung der
Notiert-Meldung). Der Lauf kostet (Kimi-Teil) Geld bzw. Abo-Kontingent und
läuft **nie automatisch** — Tests nutzen Attrappen.

## 9. Nicht in Scope

- Tool-Calling im gemma/Kimi-Erkenner.
- Neue Stückwerkzeuge oder Änderungen an `stueck.py` (die `tests/test_stueck_*.py`
  bleiben unverändert).
- Agent-Zitatsuche im Betrieb.
- Gesprächszug (`ablauf`) als Agent.
- Jede Empfehlung zum Umstellen.

## 10. Abnahme

- Bericht wie § 8.
- Volle Suite grün (`-m "not dortmund"`), `IT_ERKENNER_MODUS` Default `json`,
  Prompt-Snapshot Padua unverändert, `pruefe_profil padua-2026` grün.
- Kein Bot-Neustart.

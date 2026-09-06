# Prompt-Diff Kontext-Auftraege 1+2 — 06.09.2026

Erzeugt mit `scripts/erzeuge_prompts.py` und `kontext.umriss()` gegen zwei
**Kopien derselben** `betrieb/test.db` unter `/tmp` — einmal mit `origin/main`
(`9d00b98`), einmal mit `feat/kontext-1-2`. Gleiche Datenbank, gleicher
Auslöser, gleiche Phase (7); der einzige Unterschied ist der Code.

**Nur Blocknamen und Längen, keine Nachrichtentexte** — der Diff geht in ein
Repository, die Test-DB trägt Kopien echter Gruppen.

Gelesen wird er vor dem Merge: die Frage ist nicht „ist der Prompt kleiner",
sondern **stimmt die Verschiebung zwischen den Blöcken mit dem überein, was
Auftrag 1+2 ändern sollten** — und nichts sonst.

---

## 1. Gesprächs-Prompt (`01-gespraech`), Phase 7

| Block | vorher (Token) | nachher (Token) | Delta |
|---|---:|---:|---:|
| `verdichtungen` | 0 | 0 | — |
| `transkripte` | 0 | 0 | — |
| `kernpaket` | 260 | 260 | — |
| `arbeitsstand` | 391 | 391 | — |
| `phasenhinweis` | 0 | 0 | — |
| `figurenhinweis` | 195 | 195 | — |
| `szene` | 1.783 | 1.783 | — |
| `journal` | 283 | 283 | — |
| **`fenster`** | **0** | **2.312** | **+2.312** |
| `ausloeser` | 19 | 19 | — |
| `erstkontakt` | 0 | 0 | — |
| SYSTEM (Zeichen) | 26.365 | 26.365 | — |
| NUTZER (Zeichen) | 8.810 | 15.748 | +6.938 |
| gekürzt | nein | nein | — |

**Genau ein Block ändert sich, und es ist der beabsichtigte.** Alle anderen
zehn Blöcke sind bitgleich — Auftrag 1+2 fassen die Materiallage nicht an.

Das `fenster = 0` vorher ist **Befund C.2 des Audits**, reproduziert am echten
Datenstand: die jüngste Nachricht der Test-DB liegt um 23:56, die zwanzig
Kandidaten zwischen 21:53 und 22:32 — die harte 30-Minuten-Grenze schnitt
**alle zwanzig** weg. Der Bot antwortete mit Arbeitsstand, Kernpaket, Journal
und Szene, aber ohne einen einzigen Satz Gesprächsverlauf.

## 2. Erstkontakt-Prompt (`02-gespraech-erstkontakt`)

Identisches Bild: nur `fenster` 0 → 2.312 Token, `erstkontakt` bleibt bei 416,
alles andere unverändert. NUTZER 10.060 → 16.998 Zeichen.

## 3. Die übrigen 19 Prompt-Pfade

Unverändert. `03-auftragszug-*` (4×), `04-erkenner`, `05-erkenner-aufnahme`,
`06-verdichter`, `07-journal`, `08-sprachprofil`, `09-kernzitate`,
`10-schaerfung`, `11-szenenfolge`, `12-geschichte`, `13-szene-*` (5×),
`14-feldvorschlag` bauen ihren Nutzertext nicht über `kontext.baue` bzw. nicht
über das Gesprächsfenster — erwartungsgemäß rührt der Umbau sie nicht an.

*(Vorbehalt zur Reproduzierbarkeit: `13-szene-*` und die Auftragszüge lesen
`szene._chat_nachrichten`, das an `szene.geaendert_am` hängt und deshalb
zwischen zwei Läufen gegen dieselbe DB abweichen kann. Der Unterschied ist
nicht auf diesen Branch zurückzuführen; die Blockstruktur ist in beiden
Läufen dieselbe.)*

---

## 4. Das Fenster im Detail

| Größe | vorher | nachher |
|---|---:|---:|
| Einträge im Fenster | **0** | 7 |
| Zeichen | 0 | 6.930 |
| Pausenzeilen | 0 | **1** (`[Pause: 1 Stunde]`) |

Die Pausenmarkierung aus SPEC § 6.2 erscheint zum ersten Mal überhaupt. Sie
konnte es vorher nie: was vor der Pause lag, war schon weggefiltert, bevor die
Zeile hätte entstehen können.

Beim Menschen-Auslöser (der zweite gemessene Fall, `scripts/miss_kontext.py`):

| Größe | vorher | nachher |
|---|---:|---:|
| Fenster (Einträge) | 16 | 13 |
| Fenster (Zeichen) | 16.938 | 11.315 |
| Fenster (Token) | 4.801 | 3.775 |
| Körper (Zeichen) | 23.187 | 20.110 |
| **gekürzt** | **ja** | **nein** |

Das ist die zweite Hälfte von Auftrag 2: das zeichenbemessene Fenster hält sich
an sein eigenes Budget (11.315 ≤ 12.000), statt den Körper über die harte
Grenze zu treiben und die Gesamtkürzung Journal und Verdichtungen opfern zu
lassen. Die Kürzung greift hier gar nicht mehr — sie ist die zweite Bremse
dahinter, nicht mehr der Normalfall.

## 5. Journal-Extraktor (Befund C.3)

| Größe | vorher | nachher |
|---|---:|---:|
| unjournalisiert | 61 Nachrichten | 61 Nachrichten |
| davon verdrängt | 19 | **55** |
| Extraktor läuft | ja | ja |
| Grundlage der Rechnung | `BUDGETS["fenster"]` = 8.000 Token | `kontext.fenster_grenzen()` |

Vorher hielt der Extraktor 42 Nachrichten für „noch im Fenster", während der
Prompt 16 sah — die Differenz wurde nie journalisiert und stand danach
nirgends. Nachher ist die Teilung exakt: verdrängt + im Fenster = alle, ohne
Lücke und ohne Überschneidung (`tests/test_journal.py::
test_verdraengung_rechnet_gegen_dasselbe_fenster_wie_der_prompt`).

---

## 6. Was der Leser vor dem Merge prüfen sollte

1. **Nur `fenster` bewegt sich.** Bewegt sich in einem späteren Lauf ein
   anderer Block, gehört er nicht zu diesem Branch.
2. **Der Nutzertext wächst**, um rund 6.900 Zeichen — das ist der Verlauf, der
   vorher fehlte, nicht neue Dubletten (`test_gespraech_ohne_dubletten` läuft).
   Er bleibt unter der harten Grenze von 24.000.
3. **SYSTEM ist unverändert** (26.365 Zeichen). Auftrag 4 (Systemanweisung in
   die Messung nehmen) ist bewusst nicht Teil dieses Branches.
4. **Neuer Vorfalltyp** `kontext_kuerzung_erfolglos` — er erscheint in diesen
   Läufen nicht, weil keine Kürzung ihr Ziel verfehlt. Genau so ist es richtig:
   er ist ein Alarm, kein Protokoll.

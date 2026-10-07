# Workshop-Profil `padua-2026` — englisch, Inhalt aus dem Vault (Karte P)

**Stand 01.10.2026.** Methode (Sprache, Phasen, Formen, Einleitungen) von
Karte A1, Inhalt von **Karte P** aus genau zwei Vault-Dateien
(`projekte/padua-workshop/padua-workshop.md`, `notes/inscribe-padua-todo.md`).
Die Zeile `geruest = true` ist gestrichen; `python -m scripts.pruefe_profil
padua-2026` meldet „in Ordnung".

**Abgenommen am 01.10.2026.** Die sechs Angaben, die Karte P noch als
`# ANNAHME (unbelegt)` markiert hatte, hat Birk am Prompt-Dump entschieden;
`profil.toml` nennt seitdem je Angabe die Entscheidung statt der Annahme.
Gültig ist damit: die **Spielorte** sind offen formuliert — welche Orte
vorkommen, wählt die Gruppe aus ihren Interviews, erfunden oder real, und
Padua ist Herkunft des Materials, nicht Pflicht-Schauplatz („Venice" ist
raus); die **ausgeschlossenen Orte** bleiben wie sie waren (Schutz der
Befragten, kein Jugendschutz); die **Werkschau** findet am letzten Tag in oder
an der Akademie statt, 10–15 Minuten je Gruppe, Form und Mittel offen — kein
Teatro Verdi, keine KI-Projektion; es gibt **keine Beispielorte** mehr (im
englischen Prompt steht `<place>`); der **Konfliktrahmen** ist leer, es bleibt
„Conflict may be serious."; **ausgeschlossen** ist nur noch „No interviewed
person recognisable by name or address". Nachweis mit Prompt-Dump und
Greptabelle: `docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md`.

**Das Szenenmodell ist kein Profilfeld.** E9 (Szenen über
`claude-opus-5-5`, USA-Einwilligung bleibt) wird im Betrieb gesetzt, je
Gruppe in `betrieb/<gruppe>.env`:

```
IT_SZENE_ANBIETER=claude
IT_SZENE_MODELL=claude-opus-5-5
```

Ohne diese Zeilen gilt die Vorgabe aus `interview_theater/einstellungen.py`
(`IT_SZENE_ANBIETER=infomaniak`, `IT_SZENE_MODELL=claude-opus-5`).

**Die Profil-Anweisung** (`prompts/anweisung.md`, Karte P): eine knappe
Verhaltensanweisung an den Gesprächs-Bot (Rolle, Ton, Grenzen, Frageweise),
die `anweisungen.system()` zwischen Phasenanweisung und Regie-Zettel hängt.
Nur Padua hat sie — Dortmund bleibt bitgleich. **Abgenommen am 01.10.2026**;
ihr Schluss ist Birks Wortlaut: eine der angebotenen Optionen darf einen
überraschenden oder gegenläufigen Winkel nehmen, solange er aus dem Material
oder dem Thema der Gruppe wächst. Weil diese Datei am **Ende** des Prompts
steht (SPEC § 6.1), gilt sie gegen jede ältere Formulierung in
`sprachen/en/prompts/`.

## Was dieses Profil eigenständig macht (gesetzt von A1)

- **Sprache `en`**, Anrede `you` (`[sprache]`). Chat, Knöpfe, Gruppenseite
  und alle Prompts laufen englisch; die englischen Prompts und Texte liegen
  **nicht hier**, sondern in der Sprachschicht
  `interview_theater/sprachen/en/` (`texte.toml`, `prompts/**.md`). Dort liegen
  auch die englischen Rahmen-Vorlagen (`rahmen.md`, `rahmen-kurz.md`,
  `rahmen-knapp.md`, `projekt.md`), die nur Profil-Platzhalter benutzen —
  deshalb liegt im `prompts/`-Verzeichnis dieses Profils nur die
  Profil-Anweisung `anweisung.md` (Karte P), keine Rahmen-Vorlage (W1).
- **Whisper `auto`**: die Interviewsprache erkennt Whisper selbst; in Phase 3
  steht ein Knopf zum Umstellen, dazu `/sprache`. **Unbestätigt:** Annahme A1
  (Infomaniak-Whisper erkennt die Sprache, wenn das Feld `language` fehlt) ist
  nicht gemessen — der Rauchtest aus Aufgabe 9 ist offen geblieben, weil die
  Testaufnahmen fehlten. Fällt die Annahme, existiert der Rückweg schon: die
  Gruppe stellt per Knopf in Phase 3 oder mit `/sprache` eine feste Sprache
  ein, und das Profil kann `whisper = "en"` (oder `"it"`) setzen.
- **Pseudonyme** (`[datenschutz] pseudonyme = true`, E8): kein Prompt sieht
  einen Vornamen, dort stehen „Member 1, 2, …".
- **Englische Phasen** (`phasen.toml`): dieselben sieben Stationen wie in
  Dortmund — Terms, Questions, Interviews, Frame, Interview Selection,
  Scene Cards, Stage Script (bis 08.10.2026: Prose Draft, Rewrite, Stage
  Version; die alten Namen treffen weiter als Stichwort) —, mit englischen
  Stichwörtern. „Interview Selection" statt Birks „Interviews", weil
  Phase 3 so heißt; `vorrang` lässt die Wendung vor dem „interview" der
  Phase 3 treffen. Phase 4 kennt auch
  „core theme", „format", „setting", „story", weil der englische
  Erkenner-Prompt noch die alte Phasenliste nennt.
- **Englische Einleitungen** (`phasentexte.toml`), je zwei bis vier Sätze,
  unter 700 Zeichen.
- **Englische Formen** (`formen.toml`): Dialogue, Monologue, Chorus, Song,
  Rap — die Datenbankwerte bleiben `dialog`, `monolog`, `chor`, `lied`, `rap`.
- **Keine Beispielorte** (`orte.beispiele = []`, Birk 01.10.2026): im
  englischen Prompt steht statt eines Ortes `<place>` — wie `<character A>` —,
  weil Nachplappern von Beispielorten gemessen ist (Audit 06.09.2026). Die
  **leere Liste** steht ausdrücklich da: ein fehlender Schlüssel würde über
  `workshop._vereinige` die deutschen Vorgabewerte erben.

## Laengen-Rhythmus und Sprachpass (Karte R, 30.09.2026)

- **Wo die Zahlen stehen:** in `profil.toml` unter `[laengen]` (Schalter,
  `kurz_faktor`, `nachzaehl_schwelle`, Rueckfall `vorgabe_min`/`vorgabe_max`),
  `[laengen.rahmen]` (Woerter je Szene und Form: Dialog 200-450, Monolog
  150-350, Chor/Lied 80-200, Rap 120-250) und `[sprachpass]` (vier
  Grenzwerte). Aenderbar ohne Code; wirksam nach einem Neustart des Bots, weil
  die TOML nur beim Start gelesen wird.
- **Die Rahmenwerte sind ein Vorschlag und ungemessen.** Woran sie zu eichen
  sind -- Herkules.exe, Dortmund Textbuch v1/v2 -- steht in
  `docs/padua-r-laengen-2026-09-30/BEFUND.md`, Abschnitt 1. Sie liegen schon
  bei etwa einem Viertel des Herkules-Masses; ob das der Normalfall oder
  bereits die kurze Fassung ist, entscheidet Birk.
- **`kurz_faktor = 0.25` ist die Instagram-Entscheidung:** "Kuerzer (25 %)"
  unter der ganzen Geschichte legt diesen Faktor dauerhaft auf alle
  Budgets (`arbeitsstand.laengen_faktor`), auch auf Szenen, die es noch nicht
  gibt.
- **Zurueck zum Verhalten von vorher:** `[laengen] aktiv = false` (und
  `[sprachpass] aktiv = false`) -- dann gibt es weder ein Budget im Prompt
  noch einen Nachpass, genau wie in Dortmund.

## Phase 1+2 Umbau (Karte Padua Phase 1+2, 03.10.2026)

- **Hintergrund-Diskussion in Phase 1** (`[diskussion] aktiv = true`): das
  Mikrofon läuft mit, während die Gruppe frei diskutiert, ohne Gesprächszug,
  ohne Absichtserkenner, ohne CoThinker-Karte je Segment (`diskussion.py`).
  Erst am Ende läuft EIN Schema-Aufruf über das ganze zusammengefügte
  Transkript und destilliert, was Phase 2 und Phase 4+ später brauchen
  können — Zitatschutz wie überall (`zitat.pruefe`).
- **A/B-Vergleich eigene-vs-KI-Fragen in Phase 2** (`[fragen_ab] aktiv =
  true`): die KI-Fragen entstehen schon beim Eintritt in Phase 2, bevor die
  Gruppe ihre eigenen einspricht, und bleiben bis dahin versteckt — sonst
  wüsste die KI die Fragen der Gruppe und der Vergleich wäre nicht sauber.
  Erst wenn genügend eigene Fragen je Begriff vorliegen, kommt die
  Gegenüberstellung.
- Beide Schalter liest `workshop.diskussion_aktiv()` bzw.
  `workshop.fragen_ab_aktiv()` aus `profil.toml` (`[diskussion] aktiv` /
  `[fragen_ab] aktiv`, Vorgabe `false` — wie bei `[laengen]`). Dortmund und
  das eingebaute Vorgabeprofil setzen beide Zeilen nicht und bleiben
  unberührt.

## Was offen bleibt

- **Journal-, Verdichter- und Sprachprofil-Korpus auf Englisch** — nur der
  Erkenner hat einen englischen Korpus (`korpus/en/`, D8); die übrigen
  Prompts laufen in Padua ungemessen.
- **Simulations-Personas** (`simulation/stimmen/*.md`) schreiben deutsch.
- **Englische Befehlsaliase** (`/help`, `/status`) — Annahme A4, nicht Teil
  von A1.
- **Ein Web-Feld für die Whisper-Sprache** — gehört zu A2.
- **Der Whisper-Rauchtest** (Aufgabe 9, siehe oben).

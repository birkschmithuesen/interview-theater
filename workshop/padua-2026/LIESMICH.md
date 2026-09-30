# Workshop-Profil `padua-2026` — englisch, Inhalt aus dem Vault (Karte P)

**Stand 01.10.2026.** Methode (Sprache, Phasen, Formen, Einleitungen) von
Karte A1, Inhalt von **Karte P** aus genau zwei Vault-Dateien
(`projekte/padua-workshop/padua-workshop.md`, `notes/inscribe-padua-todo.md`).
Die Zeile `geruest = true` ist gestrichen; `python -m scripts.pruefe_profil
padua-2026` meldet „in Ordnung".

**Jede Angabe, die nicht wörtlich oder eindeutig im Vault steht, trägt in
`profil.toml` den Kommentar `# ANNAHME (unbelegt): …`** — mit dem Grund. Birk
nimmt sie am Prompt-Dump ab: `docs/prompt-audit/2026-09-30-padua/BEFUND.md`.
Markiert sind heute: die Spielorte (Padua/Venedig ist nur als Interviewort
belegt), die ausgeschlossenen Orte (Dortmunds Jugendschutz-Liste ersetzt durch
einen Schutz der Befragten), der Ort der Werkschau, die Beispielorte (A1), der
Konfliktrahmen (im Vault offen) und die Konflikt-Ausschlüsse.

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
Nur Padua hat sie — Dortmund bleibt bitgleich. Begründung und Vorher/Nachher
in `BEFUND.md`. Sie ist ein **Vorschlag zur Abnahme**.

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
  Dortmund — Terms, Questions, Interviews, Setting, Characters & Story,
  Sharpening, Scenes as Story, Polish —, mit englischen Stichwörtern. Phase 4
  kennt auch „core theme", „format", „setting", „story", weil der englische
  Erkenner-Prompt noch die alte Phasenliste nennt.
- **Englische Einleitungen** (`phasentexte.toml`), je zwei bis vier Sätze,
  unter 700 Zeichen.
- **Englische Formen** (`formen.toml`): Dialogue, Monologue, Chorus, Song,
  Rap — die Datenbankwerte bleiben `dialog`, `monolog`, `chor`, `lied`, `rap`.
- **Englische Beispielorte** (`orte.beispiele`): bus stop, piazza, café,
  station. Sie stehen in englischen Prompt-Sätzen; die italienischen Wörter
  des alten Gerüsts (`fermata`, `stazione`) wären dort Fremdkörper gewesen.

## Was offen bleibt

- **Journal-, Verdichter- und Sprachprofil-Korpus auf Englisch** — nur der
  Erkenner hat einen englischen Korpus (`korpus/en/`, D8); die übrigen
  Prompts laufen in Padua ungemessen.
- **Simulations-Personas** (`simulation/stimmen/*.md`) schreiben deutsch.
- **Englische Befehlsaliase** (`/help`, `/status`) — Annahme A4, nicht Teil
  von A1.
- **Ein Web-Feld für die Whisper-Sprache** — gehört zu A2.
- **Der Whisper-Rauchtest** (Aufgabe 9, siehe oben).

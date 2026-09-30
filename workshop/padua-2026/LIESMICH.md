# Workshop-Profil `padua-2026` — Gerüst mit englischer Methode

**Stand 30.09.2026.** Die Methode steht (Sprache, Phasen, Formen, Einleitungen),
der Inhalt ist Platzhalter. Solange in `profil.toml` die Zeile
`geruest = true` steht, startet kein Bot mit diesem Profil (`bot.main` bricht
ab, `scripts/pruefe_profil.py padua-2026` meldet es mit genau einem Fehler).
Die Zeile streicht **Karte P**, wenn der Inhalt aus Birks Vault drinsteht.

Der frühere Satz „Kein Satz hier drin ist von einem Agenten geschrieben
worden" gilt nicht mehr und steht deshalb nicht mehr da: Birk hat am
29.09.2026 entschieden, dass Padua auf **Englisch** läuft, und die englischen
Texte dieses Profils (Phasennamen, Einleitungen, Formnamen) sowie die
Platzhalterwerte hat Karte A1 geschrieben. Birk nimmt sie in Karte P am
vollständigen Prompt-Dump ab (Annahme A8 des Plans).

## Was dieses Profil eigenständig macht (gesetzt von A1)

- **Sprache `en`**, Anrede `you` (`[sprache]`). Chat, Knöpfe, Gruppenseite
  und alle Prompts laufen englisch; die englischen Prompts und Texte liegen
  **nicht hier**, sondern in der Sprachschicht
  `interview_theater/sprachen/en/` (`texte.toml`, `prompts/**.md`). Dort liegen
  auch die englischen Rahmen-Vorlagen (`rahmen.md`, `rahmen-kurz.md`,
  `rahmen-knapp.md`, `projekt.md`), die nur Profil-Platzhalter benutzen —
  deshalb hat dieses Profil kein `prompts/`-Verzeichnis (W1).
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

## Was Karte P ersetzt

- **Jede Zeile in `profil.toml` mit dem Marker `ANNAHME (Platzhalter A1`** —
  Beschreibung, Zielgruppe, Träger, Orte, Ausschlüsse, Aufführungsort,
  Konfliktrahmen, Projektbeschreibung, Beispielorte.
  `tests/test_profile_geruest.py` zählt die neun Inhaltszeilen und prüft den
  Marker in jeder.
- **Die Rahmen-Vorlagen**, falls die generische englische Fassung aus der
  Sprachschicht nicht reicht: dann als Profildateien unter
  `workshop/padua-2026/prompts/` (und der Test oben, der das Verzeichnis
  ausschließt, wird mit angepasst).
- **Die Prüfung am Prompt-Dump**: Birk liest die gerenderten englischen
  Prompts einmal ganz und nimmt Wortlaut und Idiomatik ab.
- Danach die Zeile `geruest = true` streichen.

## Was offen bleibt

- **Journal-, Verdichter- und Sprachprofil-Korpus auf Englisch** — nur der
  Erkenner hat einen englischen Korpus (`korpus/en/`, D8); die übrigen
  Prompts laufen in Padua ungemessen.
- **Simulations-Personas** (`simulation/stimmen/*.md`) schreiben deutsch.
- **Englische Befehlsaliase** (`/help`, `/status`) — Annahme A4, nicht Teil
  von A1.
- **Ein Web-Feld für die Whisper-Sprache** — gehört zu A2.
- **Der Whisper-Rauchtest** (Aufgabe 9, siehe oben).

# Workshop-Profil

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 2076–2169).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Workshop-Profil

**Anlass** (Birk, 06.09.2026, nach `docs/workshop-profil-analyse-2026-09-06.md`):
das Repository war an 1217 gemessenen Stellen „Dortmund" — Alter der Gruppe,
Trägerverein, Aufführungsort, Formenliste, Phasennamen, der Wortlaut der
Einleitungen. Für einen zweiten Einsatzort hieße das entweder das Repo
gabeln oder bei jedem Workshop dieselben sechs Dateien von Hand umschreiben;
beim nächsten `git pull` wäre es wieder weg. Seither liegt alles
Individuelle unter `workshop/<name>/` und wird über **`IT_WORKSHOP`** je
Prozess eingehängt (`betrieb/gruppeN.env`, nie global — zwei Workshops
können damit parallel auf einem Server laufen).

**Ohne Variable gilt das eingebaute Vorgabeprofil**
(`workshop.VORGABE_WERTE` und die drei Geschwister) mit exakt den Werten,
die vorher im Code standen. `workshop/dortmund-2026/` trägt dieselben. Das
war das Abnahmekriterium des Umbaus bis 04.10.2026: mit `IT_WORKSHOP=dortmund-2026`
und ohne Variable entstehen zeichengleiche Prompts. Geprüft wurde das dreifach in
`tests/test_profil_bitgleich.py` gegen
`docs/prompt-audit/schnappschuss-vor-profilumbau.txt` — 114 Abschnitte, je
ein SHA-256, erzeugt mit `scripts/prompt_schnappschuss.py` vor dem ersten
Umbauschritt. **Seit 04.10.2026 ist das kein Abnahmekriterium mehr** — siehe
den Absatz „Dortmund eingefroren" ganz oben. `test_profil_bitgleich.py`
bleibt bestehen, wird aber nicht mehr als Gate behandelt; rot nur wegen
Dortmund-Abweichung → `@pytest.mark.dortmund`.

**Der Einhängepunkt ist `anweisungen.py`** und nur der: es ist die einzige
Stelle, an der Prompt-Text entsteht. Die Reihenfolge im Gesprächs-Prompt
lautet seither

Basis → Phase → **Profil** (`workshop/<name>/prompts/anweisung.md`) →
`zusatz.md` → `zusatz.<bot>.md`.

Der Regie-Zettel bleibt hinten, weil das Ende des Prompts am schwersten
wiegt (SPEC § 6.1): eine spontane Regieanweisung soll Basis, Phase **und**
Profil überstimmen können.

**Platzhalter statt Dateiersatz** ist der Normalfall (E.1 Frage 2 der
Analyse). `{{rahmen}}`, `{{zielgruppe}}`, `{{formen_liste}}` werden aus dem
aktiven Profil gefüllt; jede Prompt-Datei ist zugleich der Wert ihres
Platzhalters (`prompts/rahmen.md` → `{{rahmen}}`,
`prompts/formen/dialog.md` → `{{formen_dialog}}`, Bindestrich wird
Unterstrich), und die Fassung des Profils gewinnt über die des Repos. Ganze
Dateien zu ersetzen ist **erlaubt** — eine gleichnamige Datei in
`workshop/<name>/prompts/` schlägt die Repo-Datei —, aber der Ausnahmefall:
wer eine ganze Datei ersetzt, bekommt jede spätere Verbesserung am
generischen Prompt nicht mehr mit. Für ein Prompt-Set in einer anderen
Sprache ist Ersetzen richtig, für eine andere Altersgruppe nicht.

**Der Cache trägt das Profil im Schlüssel**: `_CACHE[(Profilname, Herkunft,
Prompt-Name)]` statt wie früher nur den Namen. Solange ein Prozess ein
Profil hat (heute so: ein Prozess je Gruppe), fällt das alte Verhalten nicht
auf — sobald zwei Profile in **einem** Prozess vorkommen, liefert der Cache
den Text des falschen Workshops. Das ist kein hypothetischer Fall: der
Web-Dienst läuft einmal für alle Gruppen (D.5 der Analyse). Aus demselben
Grund beantworten `szene.FORMEN`, `szene.FORM_STICHWOERTER`,
`web_schreiben.FORMEN`, `szenenfolge.FORM_VORGABE`, `phasen.PHASEN`,
`phasen.STICHWOERTER`, `phasen.MEHRDEUTIG`, `phasen.MELDUNG`,
`phasen.ERSTE`, `phasen.LETZTE` und `phasentexte.EINLEITUNGEN` ihren Wert
über ein Modul-`__getattr__` (PEP 562) bei **jedem** Zugriff frisch, nicht
einmal beim Import. Innerhalb desselben Moduls greift das nicht — dort
rufen die Funktionen `workshop.*` direkt auf.

**Format ist TOML, nicht YAML.** PyYAML ist keine Abhängigkeit dieses
Projekts, und eine neue Abhängigkeit für eine Konfigurationsdatei ist der
falsche Preis; `tomllib` steht seit Python 3.11 in der Standardbibliothek.
Kein Profil-Element ist Python (E.1 Frage 10): wenn eine Anpassung Code
braucht, liegt sie in der falschen Schicht.

**Kein Halbstart.** Ein fehlendes oder kaputtes Profil bricht `bot.main` ab,
bevor eine Datenbank geöffnet wird; `scripts/pruefe_profil.py` prüft
dasselbe vorher und läuft in `scripts/betrieb-start.sh` **vor** dem Bot.
Ein angefangenes Profil trägt `geruest = true` in `profil.toml`: es lädt und
lässt sich ansehen (damit ein Test nicht daran scheitert, E.1 Frage 8),
aber kein Bot startet damit. Fehlerbild am Workshoptag ist die teuerste
Währung.

**Verhaltensänderung für den Workshoptag** (D.10): der Block „Rahmen des
Stuecks" steht nicht mehr in `prompts/system.md`, dort steht `{{rahmen}}`.
Wer ihn im laufenden Workshop ändert, ändert
`workshop/dortmund-2026/prompts/rahmen.md` — hot-reload gilt dort genauso.
Die TOML-Dateien werden dagegen nur beim Start gelesen: eine halb
gespeicherte `profil.toml` mitten im Gespräch wäre genau der Halbstart, den
der Lader verhindert.

**Tests zweistufig** (D.1): generische Tests prüfen Struktur und gelten für
jedes Profil; `tests/profile/test_dortmund.py` prüft die Werte im Wortlaut
und läuft ausdrücklich mit `IT_WORKSHOP=dortmund-2026`. Wer ein Literal
durch einen Profil-Lookup ersetzt, prüft am Ende nur noch, dass zwei
Stellen dasselbe sagen. Seit 04.10.2026 kein Abnahmekriterium mehr — siehe
„Dortmund eingefroren" oben; rot nur wegen Dortmund → `@pytest.mark.dortmund`.

Anleitung zum Anlegen eines Profils, offene Punkte und der Grund für jede
Abweichung von der Analyse: `docs/workshop-profil-umbau-2026-09-06.md`.

# Jinja-Templates wie im Fundusbot — Bewertung als Inspiration

06.09.2026, Prompt-Audit. Anlass: Birk — „Er kann sich beim Fundusbot
anschauen, wie es dort gemacht wird (Jinja-Template) — ggf. eine gute
Inspiration."

Gelesen (read-only): `fundusapps/botserver/llms/renderer.py` (232 Zeilen),
`llms/exts.py` (89), `templateLib/templates/context/base.txt`,
`templateLib/templates/models/{botmodel,scenemodel,storymodel,message,eventslog}/*.txt`.

## Was der Fundusbot macht

Ein `jinja2.Environment` mit `FileSystemLoader` über eine Liste von
Verzeichnissen (Projekt-Dir des Bots, Projekt-Dir der Story, Default-Lib —
das erste Verzeichnis mit passender Datei gewinnt, also **Overlay statt
Verzweigung im Code**), `trim_blocks`/`lstrip_blocks`, `auto_reload=True` und
— in `renderGeneric`/`renderCondition` — `undefined=StrictUndefined`. Der
Prompt selbst ist eine `.txt`-Datei; die Kontextblöcke sind je Modellobjekt
eine eigene Datei, die per `{% include %}` eingezogen wird
(`storymodel/base.txt` zieht `scenemodel/base.txt` je Szene und darin
`botmodel/base.txt` je Bot, eingerückt über `{% filter indent(width=4) %}`).
Der Verlauf ist eine Schleife: `message_history.txt` läuft über
`story.messages` und rendert je Zeile `message/line.txt`, das seinerseits
`message/base.txt` **erbt** und nur zwei Blöcke überschreibt.

Drei Erweiterungen tragen die Logik, die bei uns in Python steht:

* `SkipBlockExtension` filtert auf Token-Ebene ganze `{% block %}`-Bereiche
  weg — dieselbe Datei liefert je nach `env.skip_blocks` einen LLM-Prompt
  **oder** eine gescriptete Zeile.
* `MetaExtension` (`{% meta is_prompt=True %}`) lässt das Template selbst
  Metadaten an den Renderer zurückgeben; `renderPrompt` rendert deshalb
  zweimal — einmal, um `is_prompt` zu erfahren, einmal richtig.
* `LocalizationExtension` (`{% localize de %}…{% endlocalize %}`) wirft
  Blöcke der falschen Sprache beim Parsen weg.

Dazu `override_blocks`: der Aufrufer kann Blöcke zur Laufzeit ersetzen,
indem der Renderer ein `{% extends %}`-Template zusammenstringt.

## Was das gegenüber `kontext.baue` / `szene.baue_nutzertext` besser macht

1. **Der Prompt ist als Datei lesbar.** Bei uns steht die Form des
   Nutzertexts in Python: `kontext.baue` füllt ein Dict `bloecke`, und
   `_REIHENFOLGE` fügt am Ende zusammen. Wer wissen will, wie ein Prompt
   aussieht, muss `scripts/erzeuge_prompts.py` laufen lassen — genau deshalb
   gibt es dieses Skript. Beim Fundusbot ist die Datei die Antwort.
2. **Ein Fakt hat strukturell eine Stelle.** Unsere Audit-Regel („jeder Fakt
   einmal, ein Kopf muss liefern") ist heute ein *Test*
   (`tests/test_prompt_audit.py`, kein Satz über 80 Zeichen zweimal). Bei
   Templates mit `{% include %}` je Modellobjekt ist sie eine Eigenschaft
   des Aufbaus: die Zeile „Setting: …" steht in genau einer Datei, und wer
   sie doppelt will, muss zweimal includen.
3. **Bedingte Blöcke stehen dort, wo sie gelten.** Unser Datengetrieben-Sein
   (`if not daten: return ""` je `_baue_*`) ist richtig und funktioniert;
   im Template wäre es `{% if story.scenes %}` direkt über dem Block.
4. **Ein Renderweg statt sechs.** `renderGeneric(project_dir, template,
   model)` bedient jeden Pfad. Wir haben `kontext.baue`,
   `szene.baue_nutzertext`, `szenenfolge.baue_nutzertext_geschichte`,
   `schaerfung`, `sprachprofil`, `verdichter`, `kernzitate` — sieben
   Stringbauer mit je eigener Kürzungs- und Leerlogik.
5. **Overlay je Gruppe wäre umsonst dabei.** Unser `betrieb/zusatz.<bot>.md`
   ist ein angehängter Text; ein Loader über zwei Verzeichnisse könnte
   stattdessen einen *Block* ersetzen.

## Was ein Umstieg kostet

* **Abhängigkeit.** `jinja2` ist im Projekt-Python **nicht installiert**
  (`PY -c "import jinja2"` → `ModuleNotFoundError`; `pyproject.toml`
  kennt nur `httpx`). Das Systempython 3.9 hat es, die Bots laufen aber auf
  3.11. Der Prototyp aus Teil A ist deshalb **reines Python** geblieben,
  nichts wurde installiert.
* **`StrictUndefined` im Live-Betrieb.** Der Fundusbot lässt bei
  `renderPrompt` bewusst die Voreinstellung (`Undefined`, stiller leerer
  String) und nutzt `StrictUndefined` nur in `renderGeneric`/`renderCondition`.
  Für uns wäre die Reihenfolge umgekehrt gefährlich: eine `arbeitsstand`-Zeile
  mit einer Spalte, die eine alte Datenbank noch nicht hat, würde einen
  Gesprächszug mit `UndefinedError` abbrechen — heute fängt das
  `phasentexte._feld` / `phasen.voraussetzungen` mit `try/except KeyError` ab.
  Ein Template-Fehler ist ein Fehler in einer Datei, die im Workshop heiß
  nachgeladen wird; das ist derselbe Blindflug wie bei den Prompts, gegen den
  es den Korpus gibt.
* **Hot-Reload.** `auto_reload=True` löst das für Jinja sogar sauberer als
  unser mtime-Vergleich in `anweisungen.hole` — aber `anweisungen` bliebe
  trotzdem stehen (System- und Phasenanweisungen sind Markdown, kein
  Template), also zwei Nachlademechanismen statt einem.
* **Kürzung.** `kontext`s zweistufige Kürzung (Verlauf → Journal →
  Verdichtungen, `ZEICHEN_GRENZE_VORGABE`, Vorfall `kontext_gekuerzt`, das
  `protokoll=list` für die Simulation) arbeitet auf **Blöcken als Objekten**.
  Ein Template rendert einen String; die Kürzung müsste entweder vor dem
  Rendern auf den Daten passieren (dann ist die Zeichengrenze eine Schätzung)
  oder das Template mehrfach mit unterschiedlichen Datenmengen rendern. Das
  ist der teuerste Posten und der eigentliche Grund, `kontext` nicht
  anzufassen.

## Empfehlung

**Nicht auf Jinja umstellen — das Muster übernehmen, wo es billig ist.**

* **Jetzt (gemacht, Teil A):** die Phasen-Eintritts- und
  -Abschlussnachrichten liegen in `interview_theater/phasentexte.py` als
  Daten mit einer Renderfunktion je Nachricht. Das ist die Template-Idee
  ohne die Abhängigkeit: eine Stelle, an der steht, welche Phase welche
  Parameter hat (`PARAMETER`), und drei Leser (Eintritt, Abschluss,
  `/stand`), die sich diese Liste teilen. Genau die Dedupe-Eigenschaft, die
  beim Fundusbot aus `{% include %}` fällt.
* **Wenn jinja2 dazu darf (Aufwand ~½ Tag):** die *nicht-kritischen*
  Renderpfade zuerst — Phasennachrichten, `leitfaden.baue`,
  `szenenfolge.uebersicht`, die Weboberfläche. Alle vier bauen Text ohne
  Kürzung und ohne Zeitdruck; ein Template-Fehler dort kostet eine Nachricht,
  keinen Gesprächszug. Loader auf `interview_theater/vorlagen/`,
  `undefined=StrictUndefined` nur dort, ein Test je Template gegen die
  Fixture-DB im Spätstand (wie `tests/test_prompt_audit.py`).
* **Später, wenn sich das bewährt (~2 Tage):** `szene.baue_nutzertext` — der
  Pfad mit den meisten bedingten Blöcken (Aufgabe der Szene, Formblock,
  Kernpaket je Szene, Sprachprofile) und ohne Kürzungslogik.
* **`kontext.baue` bleibt Python.** Nicht aus Bequemlichkeit: die
  Kürzungsreihenfolge, das Block-Protokoll für die Simulation und der
  `kontext_gekuerzt`-Vorfall brauchen Blöcke als Objekte mit
  Token-Schätzung. Ein Template, das 24 000 Zeichen einhalten soll, müsste
  sie nachträglich zerschneiden — und das ist genau der Ort, an dem heute
  keine Fehler sind.

**Was auch ohne jinja2 sofort zu holen ist:** die Reihenfolge-Konstante
(`kontext._REIHENFOLGE`) und die Block-Bauer sind bereits die halbe
Template-Struktur. Was fehlt, ist ein *Verzeichnis*, in dem die Form je Block
als Datei steht — dafür ist `phasentexte.py` der erste Beleg.

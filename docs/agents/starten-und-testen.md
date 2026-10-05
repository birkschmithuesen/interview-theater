# Starten und testen

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 2325–2437 und 1395–1504).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Starten und testen

**Regelweg: systemd-User-Units, nie Handstart.** Zwei Handstarts desselben
Bots = beide bekommen `409 Conflict` bei `getUpdates`, keiner empfaengt —
passiert am 04.09.2026 zweimal. Unit-Vorlage `docs/interview-theater@.service`
(nach `~/.config/systemd/user/`, `daemon-reload`), Start ueber
`scripts/betrieb-start.sh <gruppe>` (waehlt Python 3.11 aus `.venv`/uv —
das System-Python 3.9 kann `X | None` nicht importieren).

```
systemctl --user enable --now interview-theater@gruppe1.service   # je Gruppe
systemctl --user restart interview-theater@gruppe1.service        # Neustart
tail -f betrieb/gruppe1.log                                 # Log je Gruppe
```

**Verhalten aendern ohne Neustart** (`interview_theater/anweisungen.py`): alle
Prompts unter `interview_theater/prompts/` werden bei jedem Aufruf per mtime
geprueft und heiss nachgeladen -- auch `szene.md` und die Negativliste
`theater-tells.md`, die im Workshop waechst und beim naechsten Szenenauftrag
wirkt. Fuer spontane Regieanweisungen gibt es
`betrieb/zusatz.md` (alle Bots) und `betrieb/zusatz.<IT_BOT_NAME>.md` (ein
Bot); der Inhalt wird ans Ende der Gespraechs-Systemanweisung gehaengt,
Loeschen der Datei nimmt ihn zurueck. Erkenner/Journal/Verdichter bekommen
bewusst keinen Zusatz (gemessene Few-Shot-Prompts). Bedienung aus Hermes:
Skill `interview-theater-live-ops`.

Umgebungsvariablen: siehe `docs/betrieb-env.beispiel` zum Kopieren nach
`betrieb/<name>.env`. Handstart nur zum Debuggen, und nur wenn die Unit
gestoppt ist:

```
set -a; . ./betrieb/gruppe1.env; set +a
python -m interview_theater.bot
```

- `pytest` — die Testsuite unter `tests/`, läuft ohne Netzzugriff (Attrappen
  statt echter Dienste). Enthält die Korpus-Validierung und die
  Bewertungsfunktionen aus `scripts/pruefe_prompts.py`, nicht den Lauf gegen
  das Modell.
- `python -m scripts.rauchtest [pfad-zu-audio.ogg]` — **kein Test, läuft nie
  automatisch, kostet Geld.** Ein echter Aufruf gegen Sprachmodell und
  optional Whisper, zur Kalibrierung der Token-Schätzung und als
  Erreichbarkeitsprüfung vor einem Einsatz.
- `python scripts/chat_leeren.py <chat_id> [--ja]` — setzt eine Gruppe auf
  null: löscht alle dem Bot bekannten Nachrichten aus dem Telegram-Chat
  (`deleteMessages`, Bot muss Admin sein; Nachrichten von vor seinem
  Eintritt und Telegram-Servicezeilen bleiben) und danach DB + Audio wie
  `loeschen.py`. Für den Workshop-Start nach einem Probelauf. Env der
  jeweiligen Gruppe laden — das Skript prüft, dass der Bot zur Gruppe passt.
- `python -m scripts.chat_leeren_blind <chat_id> [--zurueck 300]` — wenn die
  DB die Nachrichten nicht mehr kennt (nach `loeschen.py` oder nach einem
  Simulationslauf mit `--echte-db`): Marker senden, dann die letzten 300
  IDs rückwärts löschen. Telegram-Grenze: nur 48 h, nur als Admin.
- `python -m scripts.szenen_vergleich --nur opus,kimi,mistral,apertus` —
  eine Szene, gleicher Prompt, vier Modelle; Ausgabe als Markdown mit dem
  Prompt als Anhang. Grundlage der Entscheidung für Opus (05.09.).
- `python -m scripts.interviews_uebernehmen <ziel> <quelle> [<quelle> …] [--ja]`
  — hebt die Gruppengrenze für **Material** auf (06.09.2026, Ende Tag 2: nur
  noch eine Gruppe arbeitet weiter und soll alle Interviews sehen). Kopiert je
  Quellinterview Kopf, Teile, Transkripte, Verdichtung und
  `verdichtung_thema` (inkl. `zitat_geprueft`) sowie die Audiodateien in die
  Zielgruppe; **kein Modellaufruf**, die Quellen bleiben unverändert.
  Arbeitsstand, Figuren, Szenen, Knöpfe, Nachrichten, Journal und Kernzitate
  wandern bewusst **nicht** — das ist die Arbeit der Quellgruppe an ihrem
  Material, nicht das Material. `zum_kernthema_am` wird auf NULL gesetzt: was
  zur Kernfrage passt, entscheidet die Zielgruppe selbst. Die Nummerierung
  läuft weiter, weil `kontext.interviewbezeichnung` nach `id` zählt und neue
  Zeilen höhere ids bekommen; `name` wird beim Import auf „Interview N"
  gesetzt und nie aus der Quelle übernommen (dort kann ein Klarname stehen).
  Idempotent über `aufnahme.uebernommen_von` („`<quell_chat_id>:<alte_id>`",
  additiv migriert), alles in einer Transaktion, ohne `--ja` reiner
  Trockenlauf mit Zählung. Verweigert den Dienst, solange in Ziel oder Quelle
  eine Aufnahme läuft oder der Interviewmodus an ist. Mit `--ja` legt es
  selbst ein DB-Backup an, schreibt einen Journaleintrag in die Zielgruppe und
  eine Zeile in den Zielchat. Env der **Ziel**gruppe laden — die Quellen
  dürfen anderen Bots gehören, sie liegen in derselben Datenbank.
- `python scripts/loeschen.py <chat_id>` — der Löschweg: entfernt alle
  Datenbankzeilen einer Gruppe und ihr Audioverzeichnis, fragt vorher
  interaktiv nach Bestätigung. Es gibt bewusst keinen Löschbefehl im Chat.

`scripts/simulation_abdeckung.py` erzeugt die Abdeckungstabelle der
Simulation aus dem Code (Phasen aus `phasen.PHASEN`, Schritte aus den drei
`skript`-Listen, Pruefung aus `schritt.fertig.__name__`) und prueft jede
Behauptung der Simulations-Doku dagegen — kein Modell, kein Netz, keine
Kosten.

**Simulation** (`simulation/`, `scripts/simulation.py`, Stand 06.09.2026 nachts):
simulierte Gruppen spielen den Bot durch **alle Phasen** — mit Inline-Knöpfen
(`attrappe` merkt die Leisten, die Stimme drückt per Knopftext oder schreibt
frei) und dem Schrittplan `skript.SCHRITTE_TAG2`. Wie viele Phasen das sind,
steht nirgends im Simulator: er liest `phasen.PHASEN`, die Arbeitsstandfelder
aus `PRAGMA table_info(arbeitsstand)` und die Zielphase über
`skript.phase_szenen()` — ein Umbau an den Phasen soll ihn nicht mitreißen. Stimmen: drei erfundene Sets
plus **PII-freie Personas aus Tag 1** (`simulation/tag1.py`,
`simulation/stimmen/tag1-gruppe{1,2,3}.md`, `regie.md`): nur Begriffe/Fragen der
echten Gruppen, Themen-Stichworte und Verhaltensaggregate, nie Transkripte oder
Klarnamen — `tests/test_simulation_tag1.py` prüft das gegen die echte DB, wenn
sie da ist. Der Richter (Claude Opus über den Proxy) bewertet zusätzlich:
Nachrichten bis zum Speichern, Fragen je Bot-Nachricht, Wiederholungsquote,
„Bot redet parallel zum Auftrag", Knöpfe angeboten→gedrückt, Phasenwechsel
proaktiv, Form je Szene bestätigt, Exposition der Szene 1. Berichte
`simulation/laeufe/2026-09-06-*.md` + Sammelbericht. Läuft gegen ein anderes
Modell als der Bot. **Kein Test, kein Ersatz für `pytest` oder
`pruefe_prompts.py`**; Doku `simulation/README.md`.

**`python -m simulation.browser_lauf`** (Padua-UX-Simulation, 03.10.2026)
ist ein anderer Weg: statt den Bot-Code direkt anzufahren, bedient eine
Opus-Persona die echte Webseite in einem echten, headless Chromium
(Playwright) und sammelt dabei Screenshots, mechanische UX-Zaehler und ein
Opus-Urteil je Phase gegen `simulation/ux_rubrik.md` — eigene Module
(`simulation/browser_*.py`), eigene Doku (`simulation/README.md`, Abschnitt
„Der Browserlauf").

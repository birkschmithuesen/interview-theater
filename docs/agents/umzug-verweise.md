# Verweise auf AGENTS.md nach dem Umzug (05.10.2026)

Dies ist die Referenzliste für Abnahmekriterium 4 der Spezifikation `docs/superpowers/specs/2026-10-05-agents-md-index-design.md`: Alle geänderten Verweise und bewusst nicht geänderten Ausnahmefälle, mit Begründung je Fall.

## Geänderte Verweise (Beispiele je Zielpfad)

- `docs/agents/aufbau.md` — "Ein Sperren-Register je Nebenläufigkeit / Gleicher Code, verschiedene Sperren" (fragen_ki.py, vorschlagssperre.py, brainstorm.py, diskussion.py, begriffsboard.py, sprechweise.py, entwurf.py), "nginx auf herkules" (web_grenze.py), "@keyframes und @media nur in css_rahmen()" (web.py, test_web_cothinker_status_html.py — hier war der Vorlagentext allerdings eine Python-Docstring/Kommentar, kein Laufzeit-String), "eine gemeinsame Sperre würde den Gesprächszug am Szenenlauf hängen lassen" (test_vorschlagskollision.py).
- `docs/agents/entscheidungen.md` — "Die Form je Szene ist ein Vorschlag", "Phase 4 heißt Setting, Figuren & Geschichte", "Erst erfinden, dann schärfen", "Slash-Befehle werden nicht (mehr) beworben", "Datenstand ist nicht Absicht" (nur dort, wo das alte Kapitel namentlich zitiert wurde — die Kurzfassung selbst blieb unangetastet, siehe unten), "Fokus, kein Käfig", "Empfangen, Antworten und In-den-Prompt-legen sind drei getrennte Entscheidungen", "Aus einer Aufnahme darf der Erkenner fast nichts schreiben", "Ein Interview ist eine Einheit (SPEC § 10.6)", "Die Gruppe erfährt von einem Fehler nur…", "Bindende Entwurfsentscheidungen"/"Haltung 06.09.2026" (test_knoepfe_struktur.py, pruefe_prompt_dumps.py — wortwörtlich der Beispielfall aus dem Brief), "Ein Erkennerlauf ist mit einem Tipp zurücknehmbar" (flow_erwartungen.toml).
- `docs/agents/weboberflaeche.md` — "Drei Grenzen", "Abschlussreview I3", "Der Web-Kanal", "Die Phasenübersicht", Kanban-Karte Bühne/PTT (e2e-Test).
- `docs/agents/was-bewusst-fehlt.md` — "Der automatische Phasensprung", "Eine Menüzeile ist keine Geschichte", "Englische UI-Texte der Chatansicht", "fehlstellen" (roadmap.py, test_roadmap.py).
- `docs/agents/korpus-und-simulation.md` — "Prompt geändert? → Korpus laufen lassen", "Was FP heißt, hat sich am 05.09.2026 gedreht (N7)".
- `docs/agents/spec-abweichungen.md` — "kein Befehl ruft synchron ein Modell", "IT_MODELL_ERKENNER fehlte lange in docs/betrieb-env.beispiel" (test_web_betrieb_doku.py Docstring, wie im Brief ausdrücklich erlaubt).
- `docs/agents/workshop-profil.md` — Abschnitt "Workshop-Profil" (docs/HANDOFF.md).

## 117 bewusst unveränderte Stellen — Gründe

**A) Inhalt steht weiterhin wörtlich/sinngleich in AGENTS.md** (Dortmund-Absatz, Modulkarte, harte Invarianten inkl. "Die drei Knopf-Zusagen"/Zusage 1-3, "Jede Tabelle außer bot_zustand hat chat_id", "Die Phase setzt allein die Gruppe", "Nur anhängen", "repo.setze_szene_usa nimmt einen bool", "SQL nur in repo.py/db.py/web_daten.py", Fallen-Kurzfassung 1-10, "Starten und testen") — ca. 95 Stellen, u. a.:
  - Alle `Falle N`-Zitate (Fallen 2/3/4/6/8), auch generische `'Die Fallen'`-Verweise ohne Nummer.
  - Alle `Zusage 1/2/3`-Zitate (web_schreiben.py, kernzitate.py, szenenfolge.py, ablauf.py, aufnahme.py, schaerfung.py, web_kanal.py, repo.py, knoepfe/wirkung.py, viele Tests).
  - "Datenstand ist nicht Absicht" (entwurf.py, web_vereint.py JS/CSS-Kommentare — siehe C, test_roadmap.py, test_entwurf.py, test_entwurf_ablauf.py, knoepfe/wirkung.py).
  - "Nur anhängen"/Journal (laengen.py, ruecknahme.py, kontext.py, db.py, knoepfe/texte.py, dramaturgie/schleife.py, test_nachpass.py, test_ruecknahme.py, test_ruecknahme_rundreise.py, test_undo_knopf.py x2, test_prompt_audit.py, test_db.py, scripts/interviews_uebernehmen.py).
  - "Die Phase setzt allein die Gruppe" (phasen.py, web_schreiben.py, phasentexte.py, web.py).
  - "Jede Tabelle … chat_id" (web_schreiben.py, test_festlegung.py, test_ruecknahme_repo.py, scripts/interviews_uebernehmen.py).
  - "repo.setze_szene_usa nimmt einen bool" (test_szene_sprache.py, test_web_chat_interview.py, test_phase5_massnahmen.py).
  - "db.py migriert ausschließlich additiv" (test_web_strom.py, test_web_post.py).
  - "SQL nur in repo.py/db.py" (leitfaden.py, kosten.py).
  - "FP = 0 bleibt Exit-Kriterium" (scripts/pruefe_prompts.py:227, docs/HANDOFF.md:347).

**B) Selbstreferenziell — korrekt so, keine Änderung nötig** (beschreiben/lesen die Datei `AGENTS.md` selbst als Artefakt des Umzugs, nicht als Zitatquelle): `tests/agents_doku.py`, `tests/test_pruefe_agents_umzug.py`, `tests/test_agents_md_groesse.py`, `scripts/agents_umzug_aufteilen.py`, `scripts/pruefe_agents_umzug.py`, `tests/test_doku_laengen.py` (Docstring).

**C) Laufzeit-/servierte Strings — bewusst nicht angefasst** (würden Bytegleichheit von CSS/JS im HTTP-Response bzw. Snapshot-/Bitgleich-Tests verändern):
  - `interview_theater/web_vereint.py:253` (CSS-Kommentar in `_CSS_VEREINT`, ungescoped im Response).
  - `interview_theater/web_vereint.py:901` (JS-Kommentar in `_VEREINT_JS`, wird roh ausgeliefert).
  Beide zitieren ohnehin Inhalt, der weiterhin in AGENTS.md steht ("Datenstand ist nicht Absicht"), die Entscheidung ist also doppelt abgesichert.
  - `interview_theater/web_vereint.py:432` — CSP-Regel, ebenfalls Kategorie A (Inhalt in Harte Invarianten vorhanden) und zusätzlich Laufzeit-JS-Kommentar.

**D) Generische Index-Pointer, weiterhin korrekt** (README.md:51/171/184/190, docs/HANDOFF.md:12) — "siehe AGENTS.md" / "documented in AGENTS.md" als Verweis auf die Datei als Einstiegspunkt/Index; AGENTS.md ist weiterhin genau das (verlinkt von dort auf docs/agents/), daher keine Änderung.

**E) Kein eindeutiger Abschnitt auflösbar — gemäß Schritt 2 unverändert gelassen und hier genannt:**
  - `interview_theater/knoepfe/texte.py:169` — `(AGENTS.md, Fehlerhaltung)`: kein Abschnitt "Fehlerhaltung" in docs/agents/ oder AGENTS.md gefunden.
  - `tests/test_prompt_audit.py:472` — `Anti-Nachplapper (AGENTS.md)`: kein Treffer für "Anti-Nachplapper"/"Nachplapper"/"Eigennamen"/"Beispielname" in docs/agents/.
  - `tests/test_kontext_recall.py:74` — `(AGENTS.md, dieselbe Regel wie für die Prompt-Dumps)`: keine eindeutige Zielstelle für "Prompt-Dumps" gefunden (Datenschutz-Regel ist zwar in AGENTS.md vorhanden, aber nicht eindeutig derselbe Referenzpunkt).
  - `tests/test_web_chat_brainstorm_knopf.py:8` — `siehe AGENTS.md/Brief Abschnitt 1`: "Brief Abschnitt 1" bezieht sich auf ein externes Planungsdokument, nicht auf ein AGENTS.md-Kapitel.
  - `tests/test_fixture_padua_voll.py:25` — `AGENTS.md-Fallenkatalog`: generischer Verweis auf die Fallen insgesamt (Kurzfassung bleibt in AGENTS.md, daher ohnehin Kategorie A, aber ohne spezifische Fallennummer nicht eindeutig umzuschreiben).
  - `simulation/browser_elemente.py:5` — `AGENTS.md-Auftrag der Karte: "Elemente über Rolle/Text/data-* finden"`: Zitat einer Kartenanweisung, kein Treffer in docs/agents/.

## Laufzeit-Strings/Prompts/TOML-Werte — keine angefasst

Keine Fundstelle lag in einem tatsächlichen Prompt-Text, einer Nutzer-Meldung oder einem reinen TOML-**Wert** (nur ein TOML-**Kommentar** in `interview_theater/sprachen/en/texte.toml:1843` wurde geändert — Kommentare werden beim Parsen nicht gelesen und fließen nie in einen Prompt oder eine Chat-Antwort ein). Die zwei Fälle in `simulation/flow_erwartungen.toml` sind `beleg`-Freitextfelder eines internen Audit-/Erwartungs-Datensatzes (keine Nutzer- oder Modell-sichtbaren Strings, von `tests/test_flow_abdeckung.py` nicht auf exakten Wortlaut geprüft) und waren laut Brief explizit im Scope.

## Sonstiges

- `docs/agents/**` wurde nicht angefasst (per `git diff --stat` bestätigt, 0 Treffer dort).
- Der Commit enthält ausschließlich die in `git add -u interview_theater tests scripts simulation README.md pyproject.toml docs/HANDOFF.md` erfassten Pfade; `uv.lock` bleibt unberührt/untracked.
- Keine Bedenken: alle Zielpfade in `docs/agents/` existieren und wurden per `grep -n` gegen den tatsächlichen Inhalt verifiziert, bevor der Verweis geändert wurde.

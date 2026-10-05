# Padua Prompt-Check (vollstaendig) -- Implementierungsplan

> **Fuer agentische Arbeiter:** PFLICHT-TEILSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, Task fuer Task. Die Schritte
> tragen Checkboxen (`- [ ]`).

**Ziel:** Ein wiederholbarer, phasenvollstaendiger Prompt-Check fuer Padua --
Volltext-Dump JEDES Modellaufrufs, der in den Phasen 1-7 live vorkommt (System-
UND Nutzerteil, mit dem Modell, das ihn wirklich bedient), ein mechanischer
Pruefer, eine Opus-Lesung je Phase gegen Birks UX-Regeln; einmal gefahren,
abgelegt unter `docs/prompt-audit/2026-10-05-padua-voll/`, die eindeutigen
Widersprueche in den Phasen 3-7 behoben, und der Check als fester Schritt der
Abnahme/END.

**Architektur:** Vier neue Bausteine unter `scripts/`, keine Produktivaenderung
ausser an Prompt-Dateien (Task 10).
1. `scripts/fixture_padua_voll.py` -- eine erfundene Gruppe je Phase 1-7 in
   einer Wegwerf-Datenbank, mit realistischem Volumen (>= 34 Zuege inkl.
   Systemzeilen und Transkript-Echos, gefuellter Arbeitsstand, Journal,
   Festlegungen).
2. `scripts/mitschnitt.py` -- ein **mitschreibendes Double** an der
   Transportgrenze (`LLM.schema`/`LLM.prosa`, `szene_claude.schema`/`prosa`,
   `llm.LLM` als Klasse). Es zeichnet `(art, modell, weg, system, nutzer)` auf
   und gibt eine minimal gueltige Antwort zurueck. Kein Byte geht ins Netz.
3. `scripts/prompt_inventar.py` -- die Inventarliste `art -> Datei -> Phase`
   plus ein AST-Scanner ueber alle Modellaufruf-Stellen. Ein Test nagelt beides
   zusammen: ein neuer Modellaufruf macht die Suite rot, bis er im Dump steht.
   **Das** macht den Check zum festen Schritt.
4. `scripts/erzeuge_prompts_padua_voll.py` (Dump), `scripts/pruefe_prompt_dumps.py`
   (erweitert, mechanisch), `scripts/pruefe_prompts_lesung.py` (Opus-Lesung je
   Phase, Zitate mechanisch mit `zitat.pruefe` geprueft).

**Tech Stack:** Python 3.11, SQLite, Standardbibliothek + `httpx`, `pytest`,
`ast` fuer die Inventarpruefung, `simulation/claude.py` (Opus ueber den lokalen
Proxy, Abo, 0 CHF je Aufruf).

---

## Global Constraints

- **Kanban:** Planungskarte `t_d142c86a` fuer die Umsetzungskarte `t_1dcf3864`.
  Ausgefuehrt wird mit `superpowers:subagent-driven-development`; die
  mechanischen Tasks 1-8 und 10-11 gehen an `claude-sonnet-5`, **Task 9 faehrt
  der Controller selbst** (echte Modellaufrufe, muss blocken koennen).
- **Branch** `padua-workshop/t_1dcf3864-padua-prompt-check-volltext-dump-aller-m`.
  Kein Merge, kein Push nach `main`.
- `PY=python3.11` -- jeder Befehl unten setzt das voraus. **Gemessen:**
  `python3.11 -m pytest -q tests/test_prompt_audit.py` -> `64 passed in 16.19s`
  aus dem Wurzelverzeichnis des Worktrees. `uv run pytest` scheitert hier
  (`ModuleNotFoundError: No module named 'interview_theater'`) -- nicht benutzen.
- **Keine env-praefigierten Befehle** (`IT_WORKSHOP=... python3.11 ...`): die
  Sandbox dieser Session verlangt dafuer eine Freigabe. Jedes neue Skript setzt
  sein Profil selbst mit `os.environ.setdefault(workshop.VARIABLE, "padua-2026")`
  -- genau wie `scripts/erzeuge_prompts_padua.py` heute. **Gemessen:**
  `python3.11 -m scripts.erzeuge_prompts_padua /tmp/padua-probe-a` laeuft ohne
  Praefix durch.
- **Nur Wegwerf-Datenbank.** `IT_DB` zeigt auf eine Datei in einem
  `tempfile.TemporaryDirectory()`; `betrieb/` wird nie geoeffnet, auch nicht
  lesend. Grund: `anweisungen.system` sucht den Regie-Zettel (`zusatz.md`)
  neben `IT_DB` -- ein Zettel aus `betrieb/` stuende sonst im Dump.
- **Nur erfundenes Material.** Keine Token, keine Links, keine echten Namen,
  keine Sitzungsdaten ins Repository. Interviewmaterial ausschliesslich aus
  `simulation/interviews/set1/*.md` (frei erfunden).
- **Dortmund ist eingefroren** (AGENTS.md ganz oben). Nichts unter
  `workshop/dortmund-2026/` anfassen, keine deutsche Prompt-Datei anfassen, die
  der Dortmund-Schnappschuss hasht. Abnahme ist
  `python3.11 -m pytest -m "not dortmund" -q` **und**
  `python3.11 -m scripts.pruefe_profil padua-2026`. **Gemessen:** letzteres gibt
  heute `padua-2026: in Ordnung`; `-m "not dortmund" --collect-only` meldet
  `7638/7642 tests collected (4 deselected)`.
- **`erkenner.md` wird in dieser Karte NICHT geaendert** (DE und EN): jede
  Aenderung am Erkenner-Prompt verlangt den bezahlten Korpuslauf mit FP = 0.
  Befunde dort gehen auf die Birk-Liste.
- **Die Parallelkarte t_0b702d1d** (Branch
  `padua-workshop/t_0b702d1d-padua-abnahmelauf-phase-1-2-im-browser-s`) besitzt
  die Phase-1-2-Prompts. **Gemessen** (`git diff --name-only main...<branch>`):
  sie aendert `workshop/padua-2026/phasentexte.toml`,
  `workshop/padua-2026/prompts/phasen/2.md`,
  `interview_theater/sprachen/en/texte.toml`, `interview_theater/befehle.py`,
  `interview_theater/bot.py`, `interview_theater/repo.py`,
  `interview_theater/web_chat.py`, `interview_theater/web_vereint.py`,
  `simulation/README.md`, `simulation/ux_rubrik.md`,
  `tests/test_sprache_prompts.py`. `interview_theater/sprachen/en/prompts/system.md`
  ist dort (Stand heute) **nicht** angefasst -- trotzdem gilt: System.md und
  Phase-1-2-Dateien werden hier nicht geaendert, Befunde dort landen in BEFUND.md
  als „liegt bei t_0b702d1d".
- **Volle Suite genau EINMAL am Ende**, im Hintergrund:
  `python3.11 -m pytest -m "not dortmund" -q > .suite.log 2>&1`. Zwischendurch
  nur gezielte Tests. Auf das Ergebnis wird gewartet; in einem Subagenten wird
  die Suite nie in den Hintergrund gelegt.
- Jede Behauptung, die im Code nicht nachprüfbar war, steht im Plan mit
  `ANNAHME:` plus dem, was zu pruefen ist.

---

## Was bewusst NICHT in dieser Karte ist

- Kein bezahlter Lauf gegen Infomaniak. Der Dump faengt an der Transportgrenze
  ab; die Opus-Lesung laeuft ueber das Abo (0 CHF je Aufruf).
- Keine Aenderung an `erkenner.md`, an `system.md`, an Phase-1-2-Prompts, an
  deutschen Prompt-Dateien, an `workshop/dortmund-2026/`.
- Kein Gate-Exit-Code im mechanischen Pruefer (er ist ein Bericht). Das Gate
  ist der AST-Inventartest in der Suite plus die Pass-Regel im END-Template.
- Keine neue Abhaengigkeit.

---

## Dateiuebersicht

| Datei | Verantwortung | Task |
|---|---|---|
| `scripts/fixture_padua_voll.py` | 7 erfundene Gruppen (Phase 1-7) in einer Wegwerf-DB; `fensterbefund` | 1 |
| `tests/test_fixture_padua_voll.py` | Volumen, Systemzeilen, Transkript-Echos, gemessene Fensterschnitte | 1 |
| `scripts/mitschnitt.py` | Mitschreibendes Double + Patch-Kontext | 2 |
| `tests/test_mitschnitt.py` | Signaturtreue, minimale Antwort, Patchwirkung | 2 |
| `scripts/prompt_inventar.py` | `INVENTAR`, `NICHT_LIVE_IN_PADUA`, AST-Scanner | 3 |
| `tests/test_modellaufrufe_inventar.py` | Jede Aufrufstelle ist abgedeckt oder begruendet ausgenommen | 3 |
| `scripts/pruefe_prompt_dumps.py` | Mechanischer Pruefer (erweitert) | 4, 5 |
| `tests/test_pruefe_prompt_dumps.py` | Einheitstests der reinen Funktionen | 4, 5 |
| `scripts/erzeuge_prompts_padua_voll.py` | Der Dump-Lauf | 6, 7 |
| `tests/test_erzeuge_prompts_padua_voll.py` | Offline-Lauf in ein Temp-Verzeichnis | 6, 7 |
| `docs/prompt-audit/ux-regeln-participatory-bot-ux.md` | Repo-Kopie der UX-Regeln | 8 |
| `scripts/pruefe_prompts_lesung.py` | Opus-Lesung je Phase, Zitatwache | 8 |
| `tests/test_prompt_lesung.py` | Nummerierung, Zitatwache, Kappung, Fake-Klient | 8 |
| `docs/prompt-audit/2026-10-05-padua-voll/` | Dumps, `uebersicht.tsv`, `mechanik.md`, `BEFUND.md` | 9, 10 |
| `interview_theater/sprachen/en/prompts/phasen/{3..7}.md` u. a. | Die Fixes | 10 |
| `simulation/README.md`, `docs/flow-audit/vorlagen.md`, `AGENTS.md` | Doku | 11 |

## Reihenfolge und warum

Erst das Werkzeug, offline und getestet (1-8), dann **ein** Lauf (9), dann die
Fixes mit Neudump (10), dann die Doku und die volle Suite (11). Der Lauf steht
nicht vorn, weil ein halb fertiges Werkzeug einen halben Befund erzeugt, und ein
halber Befund wandert in den BEFUND und bleibt dort stehen.

| Task | Deliverable | gehoert |
|---|---|---|
| 1 | Fixture, Fensterschnitte gemessen | Subagent |
| 2 | Mitschreibendes Double | Subagent |
| 3 | Inventar + AST-Nagel (das Gate) | Subagent |
| 4-5 | Mechanischer Pruefer | Subagent |
| 6-7 | Dump-Lauf, alle Phasen | Subagent |
| 8 | UX-Regeln im Repo + Opus-Lesung | Subagent |
| **9** | **Der Lauf + BEFUND.md** | **Controller** |
| 10 | Fixes Phase 3-7 + Neudump | Subagent |
| 11 | Doku + volle Suite (genau einmal) | Subagent |

**Zur Nummerierung der Dumps:** `01`-`04` behalten die Namen des Vorgaengers
(`docs/prompt-audit/2026-10-02-padua-p2`, Vergleichbarkeit, D1), `05`-`09` sind
die fehlenden Gespraechsphasen, ab `10` die Hintergrundwege. Die Nummer `26`
bleibt **unbenutzt**: der Gespraechs-Dump der Phase 6 heisst schon
`02-gespraech-phase6`. Eine Luecke in der Nummerierung ist kein Fehler -- ein
umbenannter Vorgaengerdump waere einer.

---

## Task 1: Die Fixture -- sieben erfundene Gruppen mit realistischem Volumen

**Files:**
- Create: `scripts/fixture_padua_voll.py`
- Test: `tests/test_fixture_padua_voll.py`

**Interfaces:**
- Consumes: `interview_theater.{db,repo,kontext}`, `simulation/interviews/set1/*.md`
- Produces:
  ```python
  BASIS: datetime                      # 2026-10-05 08:00 UTC
  PHASEN: tuple[int, ...]              # (1, 2, 3, 4, 5, 6, 7)
  CHAT_ID_BASIS: int                   # 9_100_000_000_000
  INTERVIEW: Path                      # simulation/interviews/set1/2-ferzan-bahnhof.md
  def chat_id_fuer(phase: int) -> int
  def baue(conn, phase: int) -> int          # legt EINE Gruppe an, liefert chat_id
  def baue_alle(conn) -> dict[int, int]      # phase -> chat_id
  def fensterbefund(conn, chat_id: int) -> dict
      # {"nachrichten_gesamt": int, "im_fenster": int,
      #  "zeichen_im_fenster": int, "grund": str}
      # grund in ("nachrichten", "zeichen", "minuten", "keine")
  ```

**Warum so:** Gegen eine frische Datenbank zeigt sich keiner der Befunde, die
der Prompt-Audit vom 06.09.2026 gefunden hat (AGENTS.md, „Prompts werden nicht
gelesen, sondern erzeugt und gemessen"). Birks Zusatz vom 00:40 verlangt
deshalb ausdruecklich **realistisches Volumen**: >= 30 Zuege je Gruppe mit
Systemzeilen und Transkript-Echos, damit die Fenstergrenzen wirklich beissen
und im BEFUND gemessen statt behauptet werden koennen.

**Gemessen im Code, als Grundlage:**
- Systemzeilen landen in `nachricht` als `typ='text'`, `ist_bot=1` --
  `repo.merke_bot_zeile` (`interview_theater/repo.py:242`); der 📌-Wortlaut ist
  `erkenner._ZEILE_FESTGELEGT` (EN: `texte.toml:865` -> `"📌 Agreed: {titel} — {text}"`),
  die Notiert-Zeile `_TEXT_NOTIERT_ZEILE` (EN: `"Noted:\n{feld}: {wert}"`),
  die Undo-Zeile `_TEXT_UNDO_GEAENDERT` (EN:
  `"Changed since - please fix it in the work status"`).
- Transkript-Echos liegen als `typ='transkript'` (`repo.TYP_TRANSKRIPT`,
  `repo.py:268`) und fallen damit aus allen drei Fenstern.
- Fenstergrenzen: `kontext.FENSTER_NACHRICHTEN = 20`, `FENSTER_ZEICHEN = 12_000`,
  `FENSTER_MINUTEN = 30`, `FENSTER_MIN_NACHRICHTEN = 6`, `_FENSTER_POOL = 1000`;
  die eine Auswahlregel ist `kontext.waehle_fenster`, die eine Quelle der Werte
  `kontext.fenster_grenzen()`.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_fixture_padua_voll.py`:

```python
"""Die Padua-Fixture: sieben Gruppen mit realistischem Volumen.

Die Zahlen hier sind keine Wuensche, sondern die Bedingung dafuer, dass der
Prompt-Dump ueberhaupt etwas messen kann (Birk, 05.10.2026 00:40): gegen eine
frische Datenbank zeigt sich keiner der Befunde, die am 06.09.2026 gemessen
wurden.
"""
import pytest

from interview_theater import db, kontext, repo
from scripts import fixture_padua_voll as fix


@pytest.fixture
def conn(tmp_path):
    verbindung = db.verbinde(str(tmp_path / "fixture.db"))
    db.initialisiere(verbindung)
    fix.baue_alle(verbindung)
    yield verbindung
    verbindung.close()


def test_jede_phase_hat_eine_gruppe_mit_genug_verlauf(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        nachrichten = repo.alle_nachrichten(conn, chat_id)
        assert len(nachrichten) >= 34, (phase, len(nachrichten))


def test_jede_gruppe_traegt_systemzeilen_und_ein_transkript_echo(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        texte = [n["text"] for n in repo.alle_nachrichten(conn, chat_id)]
        assert any(t.startswith("📌 Agreed:") for t in texte), phase
        assert any(t.startswith("Noted:") for t in texte), phase
        assert any("please fix it in the work status" in t for t in texte), phase
        echos = conn.execute(
            "SELECT COUNT(*) FROM nachricht WHERE chat_id=? AND typ=?",
            (chat_id, repo.TYP_TRANSKRIPT),
        ).fetchone()[0]
        assert echos >= 1, phase


def test_mehrere_sprecher_je_gruppe(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        absender = {
            n["absender"] for n in repo.alle_nachrichten(conn, chat_id)
            if not n["ist_bot"]
        }
        assert len(absender) >= 3, (phase, absender)


def test_arbeitsstand_journal_und_festlegungen_sind_gefuellt(conn):
    for phase in fix.PHASEN:
        chat_id = fix.chat_id_fuer(phase)
        stand = repo.hole_arbeitsstand(conn, chat_id)
        assert stand["begriffe"], phase
        if phase >= 2:
            assert stand["fragen"], phase
        if phase >= 4:
            assert stand["rahmen"] and stand["geschichte"], phase
        assert repo.journal(conn, chat_id), phase
        assert repo.festlegungen(conn, chat_id), phase


def test_phase1_hat_diskussionssegmente_und_ein_begriffsboard(conn):
    chat_id = fix.chat_id_fuer(1)
    segmente = conn.execute(
        "SELECT COUNT(*) FROM aufnahme WHERE chat_id=? AND diskussion=1",
        (chat_id,),
    ).fetchone()[0]
    assert segmente >= 2
    board = conn.execute(
        "SELECT COUNT(*) FROM begriffsboard WHERE chat_id=?", (chat_id,)
    ).fetchone()[0]
    assert board >= 1


def test_ab_phase3_gibt_es_ein_verdichtetes_interview(conn):
    for phase in (3, 4, 5, 6, 7):
        chat_id = fix.chat_id_fuer(phase)
        assert repo.verdichtungen(conn, chat_id), phase


def test_das_fenster_schneidet_messbar_und_nicht_nur_nach_anzahl(conn):
    """Die Grenzen werden GEMESSEN, nicht angenommen (Birk 00:40).

    Mindestens eine Gruppe muss am Zeichenbudget schneiden und mindestens
    eine an der weichen Minutengrenze -- sonst ist die Fixture zu brav und
    der BEFUND kann zu den Fenstergrenzen nichts sagen."""
    gruende = set()
    for phase in fix.PHASEN:
        befund = fix.fensterbefund(conn, fix.chat_id_fuer(phase))
        assert befund["im_fenster"] < befund["nachrichten_gesamt"], phase
        assert befund["zeichen_im_fenster"] <= kontext.FENSTER_ZEICHEN
        gruende.add(befund["grund"])
    assert "zeichen" in gruende, gruende
    assert "minuten" in gruende, gruende
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_fixture_padua_voll.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scripts.fixture_padua_voll'`
(bzw. `ImportError` beim Sammeln).

- [ ] **Schritt 3: Die Repo-Leser pruefen, die der Test benutzt**

Bevor die Fixture entsteht: drei Namen im Test sind **nicht verifiziert**.
Nachsehen und, falls anders benannt, Test UND Fixture anpassen (nicht erfinden):

Run: `python3.11 -c "from interview_theater import repo; print([n for n in dir(repo) if n in ('alle_nachrichten','journal','festlegungen','verdichtungen','hole_arbeitsstand','TYP_TRANSKRIPT')])"`
Expected: alle sechs Namen in der Liste. Fehlt einer, mit
`grep -n "^def .*nachrichten\|^def journal" interview_theater/repo.py` den
richtigen Namen holen. `ANNAHME: repo.alle_nachrichten` und `repo.journal`
existieren unter diesen Namen -- im Code nur `repo.letzte_nachrichten`,
`repo.festlegungen`, `repo.verdichtungen`, `repo.hole_arbeitsstand`,
`repo.TYP_TRANSKRIPT` belegt. Rueckfall ohne neue Repo-Funktion: direktes
`conn.execute("SELECT * FROM nachricht WHERE chat_id=? ORDER BY gesendet_am", ...)`
im **Test** (nicht in `repo.py` -- dort kommt fuer einen Audit keine Funktion dazu).

- [ ] **Schritt 4: Die Fixture schreiben**

`scripts/fixture_padua_voll.py`:

```python
"""Sieben erfundene Padua-Gruppen, eine je Phase, in einer Wegwerf-Datenbank.

**Warum mit Volumen** (Birk, 05.10.2026 00:40): ein Prompt-Dump gegen eine
frische Datenbank zeigt keinen der Befunde, die am 06.09.2026 gemessen wurden
(52 k Zeichen Nutzertext, dieselbe Zusammenfassung 11x). Jede Gruppe hier traegt
deshalb >= 34 Zuege mit mehreren Sprechern, Bot-Antworten, Systemzeilen
(📌 / "Noted:" / "Changed since") und einem Transkript-Echo, dazu gefuellten
Arbeitsstand bis zu ihrer Phase, Journal und Festlegungen.

Alles ist **erfunden**. Das Interviewmaterial kommt aus
``simulation/interviews/set1`` (ebenfalls erfunden, gehoert ins Repository);
``betrieb/`` wird nie geoeffnet.

Die Zeitstempel sind absichtlich ungleich verteilt: die Haelfte der Zuege liegt
mehr als ``kontext.FENSTER_MINUTEN`` vor dem letzten, damit die weiche
Minutengrenze wirklich greift und ``fensterbefund`` etwas zu messen hat.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from interview_theater import kontext, repo

BASIS = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)
PHASEN = (1, 2, 3, 4, 5, 6, 7)

#: Weit oberhalb jedes Telegram-Bereichs und oberhalb von
#: ``repo.WEB_CHAT_ID_BASIS`` -- eine Fixture-chat_id soll mit keiner echten
#: Gruppe kollidieren, auch nicht in einer Entwicklungs-Datenbank.
CHAT_ID_BASIS = 9_100_000_000_000

INTERVIEW = Path("simulation/interviews/set1/2-ferzan-bahnhof.md")

#: Je Gruppe gleich: Ankunft, Technik, Alltag. 26 Zeilen.
_GRUNDVERLAUF = (
    ("Giulia", "ok we are all here, three phones on the table"),
    ("InScribe", "Good. The transcript runs live in the chat - check it once."),
    ("Marco", "the wifi in this room is terrible btw"),
    ("Giulia", "it works, just slow"),
    ("Chiara", "who is holding the second phone?"),
    ("Marco", "me"),
    ("InScribe", "Then you see the CoThinker tab. Nothing is lost if you close it."),
    ("Chiara", "can we talk in Italian sometimes?"),
    ("InScribe", "Yes. The recording understands both; I answer in English."),
    ("Giulia", "good"),
    ("Luca", "sorry i'm late, what did i miss"),
    ("Chiara", "nothing, we just started"),
    ("Marco", "do we have to finish this today?"),
    ("InScribe", "No. The workshop runs five days; today is the first."),
    ("Giulia", "ok let's keep going"),
    ("Luca", "wait, where do i see what we already decided?"),
    ("InScribe", "In the work status tab. Everything saved is there."),
    ("Luca", "ah ok"),
    ("Chiara", "my phone went to sleep"),
    ("Marco", "mine too, annoying"),
    ("Giulia", "ok can we go on"),
    ("InScribe", "Of course. Go ahead."),
    ("Luca", "is anyone writing this down"),
    ("Chiara", "the bot is"),
    ("Marco", "right"),
    ("Giulia", "ok"),
)

#: Je Phase acht Zeilen, die zu ihrer Arbeit gehoeren.
_JE_PHASE = {
    1: (
        ("Giulia", "here is our wall: arrival, waiting, strangers, home, noise, "
                   "trust, belonging, the city at night, family"),
        ("Marco", "we also had 'language' but we weren't sure"),
        ("Chiara", "i think 'waiting' is the strongest one"),
        ("Luca", "waiting is boring on stage though"),
        ("Chiara", "not if you show what people do while waiting"),
        ("InScribe", "Then 'waiting' carries two meanings for you: the empty "
                     "time, and what fills it."),
        ("Giulia", "yes exactly"),
        ("Marco", "can we keep nine terms or is that too many?"),
    ),
    2: (
        ("Giulia", "we wrote our own questions first, here they are"),
        ("Giulia", "1. what do you remember about your first day here / "
                   "2. where did you wait the longest / "
                   "3. when did a place start to feel like yours"),
        ("Luca", "question 2 sounds like a job interview"),
        ("Chiara", "i like it, it's concrete"),
        ("InScribe", "Your three are saved. Do you want to see mine next to them?"),
        ("Marco", "yes show us"),
        ("Luca", "but we decide, right"),
        ("InScribe", "You decide. Mine are only there to compare."),
    ),
    3: (
        ("Giulia", "we are at the station, it's loud"),
        ("Marco", "first interview done, 11 minutes"),
        ("InScribe", "I have it. The summary comes in a moment."),
        ("Chiara", "the man spoke about his broken bag the whole time"),
        ("Luca", "that was the best part honestly"),
        ("Giulia", "can we do one more before lunch"),
        ("Marco", "the opening line worked, people stopped"),
        ("Chiara", "one woman said no, that's fine"),
    ),
    4: (
        ("Giulia", "setting: the railway station, a wet november evening"),
        ("Marco", "three figures: Samir who just arrived, Elena at the cafe, "
                  "Tommaso the late cousin"),
        ("Chiara", "Elena should be annoyed first, not kind"),
        ("Luca", "and the bag opens in the hall, socks everywhere"),
        ("InScribe", "So the story ends with him laughing for the first time here."),
        ("Giulia", "yes"),
        ("Marco", "how many scenes do we need?"),
        ("InScribe", "That is yours to decide. Say a number and I will plan with it."),
    ),
    5: (
        ("Giulia", "ok three scenes: the bench, the cafe, socks on the floor"),
        ("Chiara", "scene 2 needs the loudspeaker line from the interview"),
        ("Marco", "which one"),
        ("Chiara", "the one about not understanding a single word"),
        ("InScribe", "That line is verified against the recording, so it can "
                     "stay verbatim."),
        ("Luca", "good, don't smooth it"),
        ("Giulia", "Elena speaks dry and short, questions instead of statements"),
        ("Marco", "Tommaso talks too fast and apologises twice"),
    ),
    6: (
        ("InScribe", "Here is your story in three sections. Tell me what should "
                     "change."),
        ("Giulia", "we like it. but Elena is too quiet in part 2"),
        ("Luca", "yes she should say something to him, not just watch"),
        ("Giulia", "can she be a bit rude at first? like annoyed"),
        ("Chiara", "and part 3 is too long"),
        ("Marco", "cut it by a quarter"),
        ("InScribe", "I will keep the three sections and their titles and "
                     "shorten inside them."),
        ("Giulia", "ok go"),
    ),
    7: (
        ("Giulia", "scene 1 dialogue, scene 2 dialogue, scene 3 chorus"),
        ("Luca", "chorus for the socks? really"),
        ("Chiara", "yes it's funnier with everyone talking at once"),
        ("InScribe", "Then scene 3 is a chorus. I have the forms for all three."),
        ("Marco", "how does Samir speak on stage?"),
        ("Chiara", "short sentences, he corrects himself, drops into his first "
                   "language"),
        ("Giulia", "Elena dry, Tommaso fast"),
        ("Marco", "when do we see the whole script?"),
    ),
}

#: Die drei Systemzeilen, mit genau den Wortlauten, die der Code schreibt
#: (``erkenner._ZEILE_FESTGELEGT`` / ``_TEXT_NOTIERT_ZEILE`` /
#: ``_TEXT_UNDO_GEAENDERT``, englische Fassung aus ``sprachen/en/texte.toml``).
#: Sie stehen hier woertlich und nicht per Import: die Fixture soll den Dump
#: nicht von der Sprachschicht abhaengig machen, und der Pruefer muss sie im
#: VERLAUF finden koennen, ohne dass eine Textaenderung ihn blind macht.
_SYSTEMZEILEN = (
    "📌 Agreed: Setting - A railway station in a northern Italian city",
    "Noted:\nterms: arrival, waiting, strangers, noise, belonging",
    "Changed since - please fix it in the work status",
)

#: Die Arbeitsstandfelder je Phase, additiv: Phase N bekommt alles von 1..N.
_STAND_JE_PHASE = {
    1: (("begriffe", "arrival, waiting, strangers, noise, belonging, home, "
                     "trust, family, the city at night"),),
    2: (("fragen", "1. What do you remember about your first day here?\n"
                   "2. Where did you wait the longest in your life?\n"
                   "3. When did a strange place start to feel like yours?"),
        ("interview_eroeffnung",
         "Hi, we are acting students from the academy. Do you have ten minutes "
         "for three questions?"),
        ("interview_abschluss",
         "Thank you. Your answers stay anonymous and become material for a "
         "fictional play.")),
    3: (),
    4: (("rahmen", "A railway station in a northern Italian city, one wet "
                   "November evening. A young man has just arrived and waits "
                   "for a cousin who does not come."),
        ("geschichte",
         "Samir waits on a bench with two bags, one of them broken. He "
         "rehearses how to order a coffee and never goes. The woman at the "
         "station cafe notices him. When his cousin finally arrives, the broken "
         "bag opens in the middle of the hall - and for the first time Samir "
         "laughs here.")),
    5: (),
    6: (),
    7: (),
}

_FIGUREN = (
    ("Samir", "just arrived, wants to arrive without asking anyone",
     "Short sentences, corrects himself, drops into his first language."),
    ("Elena", "runs the station cafe, sees everyone and says little",
     "Dry, practical, questions instead of statements."),
    ("Tommaso", "the cousin, late, embarrassed, overly cheerful",
     "Talks fast, apologises twice, jokes to cover it."),
)

_SZENEN = (
    (1, "The bench", "Samir waits and rehearses his order.", ("Samir",),
     "The hall smelled of wet coats. Samir held the broken bag shut with his "
     "foot and counted the trains he did not understand."),
    (2, "The cafe", "Elena watches him not coming in.", ("Samir", "Elena"),
     "Elena had wiped the same spot on the counter three times. The boy on the "
     "bench had looked at her menu for an hour."),
    (3, "Socks on the floor", "Tommaso arrives, the bag opens.",
     ("Samir", "Tommaso", "Elena"),
     "Tommaso came in running, said sorry twice and took the wrong bag. It "
     "opened. Socks everywhere. Samir laughed before he could stop himself."),
)

_FESTLEGUNGEN = (
    ("form", None, "One episode, the first of a series - not a closed play."),
    ("stil", None, "At most one page per scene from now on."),
)


def chat_id_fuer(phase: int) -> int:
    return CHAT_ID_BASIS + phase


def _iso(minuten: float) -> str:
    return (BASIS + timedelta(minutes=minuten)).isoformat(timespec="seconds")


def _zeitpunkte(anzahl: int) -> list[float]:
    """Minutenversaetze fuer ``anzahl`` Zuege -- vorne weit, hinten dicht.

    Die erste Haelfte liegt in Fuenf-Minuten-Schritten (also deutlich mehr als
    ``kontext.FENSTER_MINUTEN`` vor dem Ende), die zweite in halben Minuten.
    Damit greift die weiche Minutengrenze, ohne dass das Fenster leer wird
    (``FENSTER_MIN_NACHRICHTEN``)."""
    haelfte = anzahl // 2
    vorne = [i * 5.0 for i in range(haelfte)]
    start = vorne[-1] + 5.0 if vorne else 0.0
    hinten = [start + i * 0.5 for i in range(anzahl - haelfte)]
    return vorne + hinten


def _verlauf(conn, chat_id: int, phase: int) -> None:
    zeilen = list(_GRUNDVERLAUF) + list(_JE_PHASE[phase])
    # Die drei Systemzeilen dazwischen, als Bot-Zeilen (typ='text') -- genau
    # so, wie ``repo.merke_bot_zeile`` sie im Betrieb ablegt.
    for i, text in enumerate(_SYSTEMZEILEN):
        zeilen.insert(8 + i * 7, ("InScribe", text))
    versaetze = _zeitpunkte(len(zeilen))
    for i, ((absender, text), versatz) in enumerate(zip(zeilen, versaetze)):
        repo.merke_nachricht(
            conn, chat_id, 1000 + i, absender, int(absender == "InScribe"),
            "text", text, _iso(versatz),
        )
    # Das Transkript-Echo: typ='transkript', faellt aus allen drei Fenstern
    # (repo.TYP_TRANSKRIPT) und muss trotzdem in der Datenbank stehen -- der
    # Pruefer prueft, dass es NICHT im Verlaufsblock auftaucht.
    repo.merke_nachricht(
        conn, chat_id, 1000 + len(zeilen), "InScribe", 1, repo.TYP_TRANSKRIPT,
        "🎙 Interview 1\n\nthree hours on that bench and nothing to eat",
        _iso(versaetze[-1] + 0.25),
    )


def _material(conn, chat_id: int) -> int:
    """Ein verdichtetes Interview aus dem erfundenen Simulationsmaterial."""
    roh = INTERVIEW.read_text(encoding="utf-8")
    transkript = roh.split("---", 2)[2].strip()
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, 5, "lang", "text", status="fertig")
    repo.setze_transkript(conn, aufnahme_id, transkript)
    zitate = (
        "Ich habe drei Stunden auf dieser Bank gesessen und nichts gegessen.",
        "Der Lautsprecher hat geredet und ich habe kein einziges Wort verstanden.",
    )
    # Harte Zusicherung: ein unbelegtes Zitat waere im Dump ein erfundenes
    # Zitat -- genau das, was ``zitat.pruefe`` ueberall verhindert.
    assert all(z in transkript for z in zitate), "Interviewmaterial passt nicht"
    repo.speichere_verdichtung(
        conn, chat_id, aufnahme_id,
        "The interviewee remembers his first day: three hours on a station "
        "bench with a broken bag, waiting for a cousin, too unsure to buy "
        "food, unable to understand the announcements.",
        [
            {"thema": "waiting", "beleg_zitat": zitate[0], "zitat_geprueft": 1,
             "kurz": "three hours on the bench"},
            {"thema": "noise", "beleg_zitat": zitate[1], "zitat_geprueft": 1,
             "kurz": "the loudspeaker"},
        ],
    )
    return aufnahme_id


def _diskussion(conn, chat_id: int) -> None:
    """Phase 1: drei Hintergrund-Segmente plus ein Begriffsboard."""
    import json

    texte = (
        "we keep coming back to waiting. everybody waited for something",
        "and noise. the station is never quiet, you cannot think",
        "belonging is the hard one. you can wait and still belong",
    )
    letzte = 0
    for i, text in enumerate(texte):
        aufnahme_id = repo.lege_aufnahme_an(
            conn, chat_id, 200 + i, "kurz", "web", status="fertig",
            diskussion=True)
        repo.setze_transkript(conn, aufnahme_id, text)
        letzte = aufnahme_id
    board = [
        {"begriff": "waiting", "nennungen": 4, "zitat": texte[0],
         "begruendung": "the group returns to it twice",
         "doppelbedeutung": "empty time and what fills it"},
        {"begriff": "noise", "nennungen": 2, "zitat": texte[1],
         "begruendung": "named as the thing that blocks thinking",
         "doppelbedeutung": ""},
    ]
    repo.lege_begriffsboard_an(
        conn, chat_id, json.dumps(board, ensure_ascii=False), "claude", letzte)


def baue(conn, phase: int) -> int:
    chat_id = chat_id_fuer(phase)
    repo.sichere_gruppe(conn, chat_id, "padua1", f"Padua group phase {phase}")
    for stufe in range(1, phase + 1):
        for feld, wert in _STAND_JE_PHASE.get(stufe, ()):
            repo.setze_arbeitsstand(conn, chat_id, feld, wert)
    if phase >= 4:
        repo.setze_arbeitsstand(conn, chat_id, "figuren_fixiert_am", _iso(0))
    repo.setze_phase(conn, chat_id, phase)

    if phase >= 3:
        _material(conn, chat_id)
    if phase == 1:
        _diskussion(conn, chat_id)

    if phase >= 4:
        figuren = {}
        for name, beschreibung, stil in _FIGUREN:
            repo.setze_figur(conn, chat_id, name, beschreibung)
            figur_id = repo.hole_figur(conn, chat_id, name)["id"]
            repo.setze_figur_sprachstil(conn, figur_id, stil)
            figuren[name] = figur_id
        for nummer, titel, kurz, besetzung, prosa in _SZENEN:
            szene_id = repo.lege_szene_an(conn, chat_id, nummer, titel, kurz, None)
            # Ab Phase 5 steht Prosa, ab Phase 7 dazu ein Buehnentext --
            # ``phasen.voraussetzungen`` verlangt in 7 Prosa fuer JEDE Szene.
            if phase >= 5:
                repo.aktualisiere_szene(conn, szene_id, titel, kurz, None, prosa=prosa)
            if phase >= 7:
                repo.aktualisiere_szene(
                    conn, szene_id, titel, kurz,
                    f"SAMIR: {prosa.split('.')[0]}.\nELENA: And?",
                    prosa=prosa,
                )
                repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
            repo.setze_szenenfeld(conn, szene_id, "ort", "the railway station")
            repo.setze_szenenfeld(conn, szene_id, "zeit", "a wet November evening")
            repo.setze_szenenfeld(conn, szene_id, "anlass", "an arrival nobody meets")
            repo.setze_szenenfeld(conn, szene_id, "was_passiert", kurz)
            repo.setze_szene_figuren(
                conn, chat_id, szene_id, [figuren[n] for n in besetzung])

    for bereich, bezug, text in _FESTLEGUNGEN:
        repo.schreibe_festlegung(conn, chat_id, bereich, bezug, text)
    repo.schreibe_journal(conn, chat_id, "entschieden",
                          "Story as short story: 3 sections", quelle="szene")
    repo.schreibe_journal(conn, chat_id, "vorgeschlagen",
                          "A fourth scene on the platform - not decided",
                          quelle="journal")
    _verlauf(conn, chat_id, phase)
    return chat_id


def baue_alle(conn) -> dict[int, int]:
    return {phase: baue(conn, phase) for phase in PHASEN}


def fensterbefund(conn, chat_id: int) -> dict:
    """Was ``kontext.waehle_fenster`` an dieser Gruppe wirklich abschneidet.

    Der ``grund`` ist die Regel, die zuerst gegriffen hat -- in der Reihenfolge,
    in der ``waehle_fenster`` sie anwendet: Anzahl, dann Zeichen, dann die
    weiche Minutengrenze. Er geht in den BEFUND, damit die Fenstergrenzen
    gemessen und nicht angenommen sind (Birk 00:40)."""
    alle = [
        dict(zeile) for zeile in conn.execute(
            "SELECT * FROM nachricht WHERE chat_id=? AND typ='text' "
            "ORDER BY gesendet_am, message_id", (chat_id,),
        )
    ]
    grenzen = kontext.fenster_grenzen()
    fenster = kontext.waehle_fenster(alle)
    zeichen = sum(len(kontext.sprecherzeile(n)) + 1 for n in fenster)
    if not alle:
        grund = "keine"
    elif len(fenster) == len(alle):
        grund = "keine"
    elif len(alle) > grenzen["nachrichten"] and len(fenster) == grenzen["nachrichten"]:
        grund = "nachrichten"
    elif zeichen > grenzen["zeichen"] - kontext._FENSTER_POOL:
        grund = "zeichen"
    else:
        grund = "minuten"
    return {
        "nachrichten_gesamt": len(alle),
        "im_fenster": len(fenster),
        "zeichen_im_fenster": zeichen,
        "grund": grund,
    }
```

- [ ] **Schritt 5: Test laufen lassen und bis gruen nacharbeiten**

Run: `python3.11 -m pytest -q tests/test_fixture_padua_voll.py`
Expected: `8 passed`.

Drei Stellen, an denen es erfahrungsgemaess zuerst rot wird -- jede mit der
Loesung, nicht mit „anpassen":
1. **Signaturen.** `repo.setze_figur`, `repo.hole_figur`,
   `repo.setze_figur_sprachstil`, `repo.lege_szene_an`,
   `repo.aktualisiere_szene`, `repo.setze_szenenfeld`, `repo.setze_szene_figuren`,
   `repo.schreibe_festlegung`, `repo.schreibe_journal` sind genau die aus
   `scripts/erzeuge_prompts_padua.py` (dort nachlesen, Zeilen 90-180) -- ausser
   `schreibe_festlegung`, die dort nicht vorkommt. Nachsehen:
   `grep -n -A8 "^def schreibe_festlegung" interview_theater/repo.py`.
2. **`grund` trifft nie „zeichen".** Dann ist der Verlauf zu kurz. Die
   Einstellung ist `_GRUNDVERLAUF`: eine Zeile mit ~600 Zeichen anhaengen
   (eine lange Gruppennachricht, erfunden) statt die Grenze zu senken --
   `kontext.FENSTER_ZEICHEN` ist Produktivcode und wird hier nicht angefasst.
3. **`grund` trifft nie „minuten".** Dann greift `_zeitpunkte` nicht; die
   Fuenf-Minuten-Schritte in der ersten Haelfte auf zehn erhoehen.

- [ ] **Schritt 6: Festschreiben, dass die Fixture nie in `betrieb/` fasst**

An `tests/test_fixture_padua_voll.py` anhaengen:

```python
def test_fixture_nennt_kein_betriebsverzeichnis():
    """Die Fixture darf keine Betriebsdatei kennen -- auch nicht lesend."""
    import inspect

    quelle = inspect.getsource(fix)
    for wort in ("betrieb/", "soap.db", "IT_DB"):
        assert wort not in quelle, wort
```

Run: `python3.11 -m pytest -q tests/test_fixture_padua_voll.py`
Expected: `9 passed`.

- [ ] **Schritt 7: Commit**

```bash
git add scripts/fixture_padua_voll.py tests/test_fixture_padua_voll.py
git commit -m "Prompt-Check Padua: Fixture mit sieben Gruppen und gemessenen Fensterschnitten"
```

---

## Task 2: Das mitschreibende Double an der Transportgrenze

**Files:**
- Create: `scripts/mitschnitt.py`
- Test: `tests/test_mitschnitt.py`

**Interfaces:**
- Consumes: `interview_theater.{llm,szene_claude}`
- Produces:
  ```python
  PROSA_MARKE: str = "[MITSCHNITT]"

  @dataclasses.dataclass(frozen=True)
  class Aufruf:
      art: str
      weg: str      # "infomaniak" | "claude"
      modell: str
      system: str
      nutzer: str

  def minimale_antwort(schema: dict) -> dict

  class Mitschnitt:
      def __init__(self, e) -> None
      aufrufe: list[Aufruf]
      _klient: object            # Platzhalter, damit kein httpx.Client entsteht
      def schema(self, chat_id, system, nutzer, schema, art, modell=None,
                 temperature=None, bei_teil=None, teil_feld="antwort") -> dict
      def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
                timeout=None, bei_teil=None) -> str
      def letzter(self, art: str) -> Aufruf | None

  @contextlib.contextmanager
  def fange_alles(schnitt: "Mitschnitt")
  ```

**Warum an der Transportgrenze** (Entscheidung D1 des Architekten): einen Prompt
nachzubauen hiesse, eine zweite Wahrheit zu pflegen -- genau der Fehler, den
`ruecknahme.py` mit dem Diff-Ansatz vermeidet. Was das Double aufzeichnet, ist
per Konstruktion das, was der Bot verschickt haette.

**Gemessen im Code:**
- `llm.LLM.schema(chat_id, system, nutzer, schema, art, modell=None, temperature=None, bei_teil=None, teil_feld="antwort")`
  (`interview_theater/llm.py:208`).
- `llm.LLM.prosa(chat_id, system, nutzer, art, max_tokens=None, timeout=None, bei_teil=None)`
  (`llm.py:259`).
- `szene_claude.prosa(conn, e, klient, chat_id, system, nutzer, art, timeout, bei_teil=None)`
  (`szene_claude.py:335`), Modell = `getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE`
  (`szene_claude.py:351`).
- `szene_claude.schema(conn, e, klient, chat_id, system, nutzer, schema_, art, timeout, bei_teil=None, teil_feld=None)`
  (`szene_claude.py:490`).
- `modellwahl.aufruf_schema` holt den Klienten mit
  `getattr(klm, "_klient", None) or httpx.Client(...)` (`modellwahl.py:95`) --
  deshalb traegt das Double ein `_klient`-Attribut, sonst entstuende je Aufruf
  ein echter `httpx.Client`.
- `dramaturgie/fanout.Richter.frage` baut sich fuer den Infomaniak-Weg **selbst
  ein `LLM`** (`fanout.py:219-223`) und ruft dafuer `dataclasses.replace(e, ...)`
  -- deshalb muss `fange_alles` auch `interview_theater.llm.LLM` ersetzen, und
  `e` muss ein echtes `einstellungen.Einstellungen` sein (frozen dataclass,
  `einstellungen.py:56`), kein Ad-hoc-Objekt.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_mitschnitt.py`:

```python
"""Das mitschreibende Double: Signaturtreue und Patchwirkung."""
import httpx
import pytest

from interview_theater import einstellungen, llm, szene_claude
from scripts import mitschnitt as ms


def _e():
    return einstellungen.Einstellungen(
        bot_token="x", bot_name="padua1", db_pfad=":memory:", audio_verz="audio",
        llm_url="http://127.0.0.1:1/chat/completions", llm_key="k",
        llm_modell="moonshotai/Kimi-K2.6", stt_basis="http://127.0.0.1:1",
        stt_produkt="p", erkenner_modell="google/gemma-4-31B-it",
        szene_anbieter="claude", szene_modell="claude-opus-5",
    )


def test_minimale_antwort_fuellt_jedes_pflichtfeld():
    schema = {
        "type": "object", "required": ["antwort", "liste", "zahl", "ja"],
        "properties": {
            "antwort": {"type": "string"},
            "liste": {"type": "array", "items": {"type": "string"}},
            "zahl": {"type": "integer"},
            "ja": {"type": "boolean"},
        },
    }
    assert ms.minimale_antwort(schema) == {
        "antwort": ms.PROSA_MARKE, "liste": [], "zahl": 0, "ja": False,
    }


def test_schema_zeichnet_auf_und_liefert_eine_gueltige_antwort():
    schnitt = ms.Mitschnitt(_e())
    schema = {"type": "object", "required": ["antwort"],
              "properties": {"antwort": {"type": "string"}}}
    ergebnis = schnitt.schema(1, "SYS", "NUTZ", schema, "gespraech")
    assert ergebnis["antwort"] == ms.PROSA_MARKE
    letzter = schnitt.letzter("gespraech")
    assert (letzter.system, letzter.nutzer) == ("SYS", "NUTZ")
    assert letzter.weg == "infomaniak"
    assert letzter.modell == "moonshotai/Kimi-K2.6"


def test_schema_mit_modell_zeichnet_das_gemma_modell_auf():
    schnitt = ms.Mitschnitt(_e())
    schnitt.schema(1, "S", "N", {"type": "object", "properties": {}}, "erkenner",
                   modell="google/gemma-4-31B-it")
    assert schnitt.letzter("erkenner").modell == "google/gemma-4-31B-it"


def test_prosa_zeichnet_auf():
    schnitt = ms.Mitschnitt(_e())
    assert schnitt.prosa(1, "S", "N", "szene") == ms.PROSA_MARKE
    assert schnitt.letzter("szene").weg == "infomaniak"


def test_fange_alles_leitet_den_claude_weg_um():
    schnitt = ms.Mitschnitt(_e())
    with ms.fange_alles(schnitt):
        szene_claude.prosa(None, _e(), None, 1, "S", "N", "szene", timeout=1.0)
        szene_claude.schema(
            None, _e(), None, 1, "S2", "N2",
            {"type": "object", "properties": {"antwort": {"type": "string"}}},
            "gespraech", timeout=1.0,
        )
    arten = [a.art for a in schnitt.aufrufe]
    assert arten == ["szene", "gespraech"]
    assert all(a.weg == "claude" for a in schnitt.aufrufe)
    assert all(a.modell == "claude-opus-5" for a in schnitt.aufrufe)


def test_fange_alles_ersetzt_auch_die_LLM_klasse_und_stellt_sie_zurueck():
    """``fanout.Richter.frage`` baut sich fuer den Richter selbst ein ``LLM``."""
    echt = llm.LLM
    schnitt = ms.Mitschnitt(_e())
    with ms.fange_alles(schnitt):
        assert llm.LLM is not echt
        gebaut = llm.LLM(_e(), httpx.Client(), None)
        gebaut.prosa(1, "S", "N", "dramaturgie_b1")
    assert llm.LLM is echt
    assert schnitt.letzter("dramaturgie_b1").weg == "infomaniak"


def test_double_hat_einen_klienten_platzhalter():
    """Sonst baut ``modellwahl.aufruf_schema`` je Aufruf einen echten Klienten."""
    assert ms.Mitschnitt(_e())._klient is not None
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_mitschnitt.py`
Expected: FAIL beim Sammeln, `ModuleNotFoundError: No module named 'scripts.mitschnitt'`.

- [ ] **Schritt 3: Das Modul schreiben**

`scripts/mitschnitt.py`:

```python
"""Ein mitschreibendes Double an der Transportgrenze zum Sprachmodell.

**Warum an der Grenze und nicht per Nachbau** (Architekt-Entscheidung D1,
05.10.2026): einen Prompt nachzubauen hiesse, eine zweite Wahrheit zu pflegen.
Was hier aufgezeichnet wird, ist per Konstruktion genau das, was der Bot
verschickt haette -- dieselbe Ueberlegung, aus der ``ruecknahme.py`` einen
Erkennerlauf per Diff erfasst statt je Art nachzubauen.

Kein Byte geht ins Netz: ``Mitschnitt`` ersetzt ``klm``, und ``fange_alles``
ersetzt zusaetzlich ``szene_claude.schema``/``prosa`` sowie die Klasse
``interview_theater.llm.LLM`` -- letztere, weil ``dramaturgie.fanout.Richter.frage``
sich fuer den Infomaniak-Richter selbst ein ``LLM`` baut.

Das Double gibt eine **minimal gueltige** Antwort zurueck (``minimale_antwort``)
statt eine Ausnahme zu werfen: Pfade mit mehreren Aufrufen hintereinander
(``verdichter`` zweiter Versuch, ``ablauf._ohne_echo``) sollen weiterlaufen und
auch ihren zweiten Prompt hinterlassen.
"""

from __future__ import annotations

import contextlib
import dataclasses

from interview_theater import llm as llm_modul
from interview_theater import szene_claude

#: Der Platzhalter, den das Double als String-Antwort liefert. Nicht leer:
#: ``ablauf._antworttext`` wirft bei leerer Antwort einen ``LLMFehler``, und
#: ``szene.schreibe`` prueft auf Inhalt.
PROSA_MARKE = "[MITSCHNITT]"

_VORGABE = {
    "string": PROSA_MARKE,
    "array": [],
    "object": {},
    "integer": 0,
    "number": 0,
    "boolean": False,
}


@dataclasses.dataclass(frozen=True)
class Aufruf:
    """Ein aufgezeichneter Modellaufruf -- genau die fuenf Angaben, die der
    Dump braucht: ``art`` fuer die Zuordnung, ``weg``/``modell`` fuer die
    Kopfzeile, ``system``/``nutzer`` fuer den Inhalt."""
    art: str
    weg: str
    modell: str
    system: str
    nutzer: str


def minimale_antwort(schema: dict) -> dict:
    """Das kleinste Objekt, das ``schema`` erfuellt.

    Nur die Pflichtfelder bekommen Werte, der Rest bleibt weg: ein Double, das
    mehr liefert als verlangt, verdeckt einen Aufrufer, der auf ein optionales
    Feld baut."""
    eigenschaften = (schema or {}).get("properties") or {}
    pflicht = (schema or {}).get("required") or list(eigenschaften)
    antwort = {}
    for name in pflicht:
        typ = (eigenschaften.get(name) or {}).get("type", "string")
        antwort[name] = _VORGABE.get(typ, PROSA_MARKE)
    return antwort


class _Klient:
    """Platzhalter fuer ``klm._klient``.

    ``modellwahl.aufruf_schema`` und die vier ``szene_claude``-Aufrufer holen
    sich ``getattr(klm, "_klient", None) or httpx.Client(...)``. Ohne dieses
    Attribut entstuende je Aufruf ein echter Klient -- harmlos, aber er wird
    nie geschlossen, und ein Audit soll keine Sockets hinterlassen."""


class Mitschnitt:
    """Ersetzt ``interview_theater.llm.LLM`` als ``klm``."""

    def __init__(self, e) -> None:
        self._e = e
        self.aufrufe: list[Aufruf] = []
        self._klient = _Klient()

    # -- die zwei Methoden der echten LLM ----------------------------------

    def schema(self, chat_id, system, nutzer, schema, art, modell=None,
               temperature=None, bei_teil=None, teil_feld="antwort") -> dict:
        self._merke(art, modell or getattr(self._e, "llm_modell", ""),
                    system, nutzer)
        return minimale_antwort(schema)

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None,
              timeout=None, bei_teil=None) -> str:
        self._merke(art, getattr(self._e, "llm_modell", ""), system, nutzer)
        return PROSA_MARKE

    # -- Lesen --------------------------------------------------------------

    def letzter(self, art: str) -> Aufruf | None:
        for aufruf in reversed(self.aufrufe):
            if aufruf.art == art:
                return aufruf
        return None

    # -- innen --------------------------------------------------------------

    def _merke(self, art, modell, system, nutzer, weg="infomaniak") -> None:
        self.aufrufe.append(
            Aufruf(art=art, weg=weg, modell=modell or "",
                   system=system or "", nutzer=nutzer or "")
        )


@contextlib.contextmanager
def fange_alles(schnitt: Mitschnitt):
    """Leitet den Claude-Weg und die selbstgebaute ``LLM`` auf ``schnitt`` um.

    Drei Patches, alle am Modul und nicht am Objekt -- die Aufrufer greifen
    ``szene_claude.prosa`` beim Namen (``interview_theater/szene.py:2366``,
    ``kurzgeschichte.py:448``, ``szenenfolge.py:1176``,
    ``stueckpruefung.py:293``, ``buehnenkarte.py:119``,
    ``dramaturgie/fanout.py:213``) und ``llm.LLM`` ebenfalls
    (``fanout.py:219``, lokaler Import in der Funktion)."""
    echte_prosa = szene_claude.prosa
    echtes_schema = szene_claude.schema
    echte_klasse = llm_modul.LLM

    def claude_prosa(conn, e, klient, chat_id, system, nutzer, art, timeout,
                     bei_teil=None):
        schnitt._merke(
            art, getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE,
            system, nutzer, weg="claude",
        )
        return PROSA_MARKE

    def claude_schema(conn, e, klient, chat_id, system, nutzer, schema_, art,
                      timeout, bei_teil=None, teil_feld=None):
        schnitt._merke(
            art, getattr(e, "szene_modell", None) or szene_claude.MODELL_VORGABE,
            system, nutzer, weg="claude",
        )
        return minimale_antwort(schema_)

    def fabrik(e, klient=None, conn=None, *rest, **schluessel):
        """Ersatz fuer ``LLM(e, klient, conn)``.

        Liefert ein Double, das in **dieselbe** Liste schreibt und das
        ``llm_modell`` des durchgereichten ``e`` traegt -- bei der
        Dramaturgie-Pruefung ist das das Richtermodell
        (``fanout.Richter.frage``: ``dataclasses.replace(e, llm_modell=...)``)."""
        doppel = Mitschnitt(e)
        doppel.aufrufe = schnitt.aufrufe
        return doppel

    szene_claude.prosa = claude_prosa
    szene_claude.schema = claude_schema
    llm_modul.LLM = fabrik
    try:
        yield schnitt
    finally:
        szene_claude.prosa = echte_prosa
        szene_claude.schema = echtes_schema
        llm_modul.LLM = echte_klasse
```

- [ ] **Schritt 4: Test laufen lassen**

Run: `python3.11 -m pytest -q tests/test_mitschnitt.py`
Expected: `8 passed`.

Wenn `test_fange_alles_ersetzt_auch_die_LLM_klasse...` rot ist, weil
`fanout` `LLM` beim Import bindet: pruefen mit
`grep -n "from interview_theater.llm import LLM" interview_theater/dramaturgie/fanout.py`
-- **gemessen** steht der Import **in** `frage()` (Zeile 217), also greift der
Modulpatch. Steht er irgendwann oben, muss `fange_alles` zusaetzlich
`fanout.LLM` patchen; der Test deckt genau das ab.

- [ ] **Schritt 5: Commit**

```bash
git add scripts/mitschnitt.py tests/test_mitschnitt.py
git commit -m "Prompt-Check Padua: mitschreibendes Double an der Transportgrenze"
```

---

## Task 3: Das Inventar und der AST-Nagel

**Files:**
- Create: `scripts/prompt_inventar.py`
- Test: `tests/test_modellaufrufe_inventar.py`

**Interfaces:**
- Produces:
  ```python
  @dataclasses.dataclass(frozen=True)
  class Eintrag:
      datei: str        # Dumpname ohne .txt, z. B. "13-begriffsboard"
      art: str          # der art-Wert in der Tabelle `aufruf`
      phase: int
      modul: str        # "interview_theater.begriffsboard"
      art_quelle: str   # ast.unparse des art-Arguments an der Aufrufstelle
      weg: str          # "abgefangen" | "gebaut"
      grund: str = ""   # Pflicht bei weg="gebaut"

  INVENTAR: tuple[Eintrag, ...]
  NICHT_LIVE_IN_PADUA: dict[tuple[str, str], str]   # (modul, art_quelle) -> Grund

  AUFRUFE: dict[tuple[str, str], int]   # (Zielobjekt, Methode) -> Position von `art`
  @dataclasses.dataclass(frozen=True)
  class Stelle:
      modul: str
      zeile: int
      aufruf: str
      art_quelle: str
  def aufrufstellen(wurzel: Path | None = None) -> list[Stelle]
  def abgedeckt() -> set[tuple[str, str]]
  def offen() -> list[Stelle]
  def eintrag_fuer(datei: str) -> Eintrag
  ```

**Warum ein AST-Nagel** (D2, Muster `tests/test_knoepfe_struktur.py`): `art` wird
fast immer **positionell** uebergeben -- ein `grep 'art="'` findet so gut wie
nichts (gemessen: von 30 Aufrufstellen tragen zwei ein `art=`-Schluesselwort).
Der Scanner liest deshalb den AST und nimmt das Argument an der Position, die
die Signatur vorgibt.

**Die gemessenen Positionen** (aus den Signaturen in Task 2 plus
`modellwahl.aufruf_schema(conn, klm, e, chat_id, system, nutzer, schema, art, ...)`,
`modellwahl.py:77`):

| Aufruf | Position von `art` |
|---|---|
| `schema` (`klm.schema`) | 4 |
| `prosa` (`klm.prosa`) | 3 |
| `aufruf_schema` | 7 |
| `szene_claude.schema` | 7 |
| `szene_claude.prosa` | 6 |

- [ ] **Schritt 1: Die Aufrufstellen einmal aufnehmen (Messung, kein Code)**

Run:
```bash
python3.11 - <<'PY'
import ast, pathlib
AUFRUFE = {"schema": 4, "prosa": 3, "aufruf_schema": 7}
for datei in sorted(pathlib.Path("interview_theater").rglob("*.py")):
    baum = ast.parse(datei.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call) or not isinstance(knoten.func, ast.Attribute):
            continue
        name = knoten.func.attr
        if name not in AUFRUFE:
            continue
        ziel = ast.unparse(knoten.func.value)
        if ziel not in ("klm", "richter_klm", "modellwahl", "szene_claude"):
            continue
        i = AUFRUFE[name] + (3 if ziel == "szene_claude" else 0)
        art = next((k.value for k in knoten.keywords if k.arg == "art"), None)
        quelle = ast.unparse(art) if art is not None else (
            ast.unparse(knoten.args[i]) if len(knoten.args) > i else "?")
        print(f"{datei}:{knoten.lineno}\t{ziel}.{name}\t{quelle}")
PY
```
Expected: rund 30 Zeilen, darunter
`interview_theater/ablauf.py:1331  modellwahl.aufruf_schema  'gespraech'`,
`interview_theater/begriffsboard.py:350  modellwahl.aufruf_schema  ART`,
`interview_theater/verdichter.py:127  klm.schema  'verdichter'`,
`interview_theater/szene.py:2372  klm.prosa  art`.
Die Ausgabe ist die Grundlage von `INVENTAR` und `NICHT_LIVE_IN_PADUA` -- sie
wird **abgeschrieben, nicht geraten**. Fehlt `szene_claude` in der Ausgabe
(eigene Positionen), den Block ein zweites Mal mit
`AUFRUFE = {"schema": 7, "prosa": 6}` und `ziel == "szene_claude"` fahren.

- [ ] **Schritt 2: Den fehlschlagenden Test schreiben**

`tests/test_modellaufrufe_inventar.py`:

```python
"""Jeder Modellaufruf im Produktivcode ist im Prompt-Dump -- oder begruendet nicht.

Das ist der Nagel, der den Prompt-Check zum festen Schritt macht (Architekt D2,
Muster ``tests/test_knoepfe_struktur.py``): wer einen neuen Modellaufruf baut,
macht die Suite rot, bis er im Inventar steht. Gelesen wird der **Quelltext**,
nicht das Verhalten -- ``art`` wird fast immer positionell uebergeben, ein
``grep 'art="'`` findet fast nichts.
"""
import pytest

from scripts import prompt_inventar as inv


def test_der_scanner_findet_die_bekannten_stellen():
    """Sichert den Scanner selbst ab: findet er die Stellen nicht mehr, ist
    nicht der Code sauber, sondern der Scanner kaputt."""
    stellen = inv.aufrufstellen()
    assert len(stellen) >= 25, len(stellen)
    paare = {(s.modul, s.art_quelle) for s in stellen}
    assert ("interview_theater.verdichter", "'verdichter'") in paare
    assert ("interview_theater.begriffsboard", "ART") in paare
    assert ("interview_theater.ablauf", "'gespraech'") in paare


def test_keine_offene_aufrufstelle():
    offen = inv.offen()
    assert not offen, "\n".join(
        f"{s.modul}:{s.zeile} {s.aufruf} art={s.art_quelle}" for s in offen
    )


def test_jeder_inventareintrag_zeigt_auf_eine_echte_aufrufstelle():
    paare = {(s.modul, s.art_quelle) for s in inv.aufrufstellen()}
    for eintrag in inv.INVENTAR:
        assert (eintrag.modul, eintrag.art_quelle) in paare, eintrag


def test_jede_ausnahme_traegt_einen_grund():
    for schluessel, grund in inv.NICHT_LIVE_IN_PADUA.items():
        assert grund.strip(), schluessel
        assert len(grund) > 20, (schluessel, grund)


def test_dumpnamen_sind_eindeutig_und_jede_phase_kommt_vor():
    namen = [e.datei for e in inv.INVENTAR]
    assert len(namen) == len(set(namen))
    assert {e.phase for e in inv.INVENTAR} >= {1, 2, 3, 4, 5, 6, 7}


def test_gebaute_eintraege_begruenden_sich():
    for eintrag in inv.INVENTAR:
        if eintrag.weg == "gebaut":
            assert len(eintrag.grund) > 20, eintrag
        else:
            assert eintrag.weg == "abgefangen", eintrag


def test_die_vier_dumps_des_vorgaengers_behalten_ihre_namen():
    """Vergleichbarkeit mit docs/prompt-audit/2026-10-02-padua-p2 (D1)."""
    namen = {e.datei for e in inv.INVENTAR}
    for alt in ("01-gespraech-phase1", "02-gespraech-phase6",
                "03-kurzgeschichte-phase6", "04-szene-prosa-phase6"):
        assert alt in namen, alt
```

- [ ] **Schritt 3: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_modellaufrufe_inventar.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scripts.prompt_inventar'`.

- [ ] **Schritt 4: Das Inventar schreiben**

`scripts/prompt_inventar.py`. Der Kopf und die Mechanik sind vollstaendig; die
`INVENTAR`-Liste unten ist die Abschrift der Messung aus Schritt 1 (die
`art_quelle`-Spalte **genau** so uebernehmen, wie der Scanner sie ausgibt --
`'gespraech'` mit Anfuehrungszeichen, `ART` ohne).

```python
"""Welcher Modellaufruf in Padua live vorkommt -- und wo sein Dump liegt.

**Warum es diese Liste gibt** (Architekt D2): der Prompt-Check soll nicht
veralten. Ein Test liest den Quelltext aller Modellaufrufe und vergleicht sie
mit dieser Liste; ein neuer Aufruf macht die Suite rot, bis er hier steht oder
mit Grund in ``NICHT_LIVE_IN_PADUA``. Dieselbe Bauart wie
``tests/test_knoepfe_struktur.py``, und aus demselben Grund: eine Tabelle laesst
sich auslesen, eine Kaskade nicht.

``art`` wird im Repo fast immer **positionell** uebergeben. Die Positionen
stehen in ``AUFRUFE`` und sind an den Signaturen gemessen
(``llm.LLM.schema``/``prosa``, ``modellwahl.aufruf_schema``,
``szene_claude.schema``/``prosa``).
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

WURZEL = Path("interview_theater")

#: Aufrufname -> Position des ``art``-Arguments. ``szene_claude`` hat drei
#: Parameter mehr vorn (conn, e, klient) und steht deshalb getrennt.
AUFRUFE = {
    ("klm", "schema"): 4,
    ("klm", "prosa"): 3,
    ("richter_klm", "prosa"): 3,
    ("modellwahl", "aufruf_schema"): 7,
    ("szene_claude", "schema"): 7,
    ("szene_claude", "prosa"): 6,
}


@dataclasses.dataclass(frozen=True)
class Stelle:
    modul: str
    zeile: int
    aufruf: str
    art_quelle: str


@dataclasses.dataclass(frozen=True)
class Eintrag:
    datei: str
    art: str
    phase: int
    modul: str
    art_quelle: str
    weg: str = "abgefangen"
    grund: str = ""


def aufrufstellen(wurzel: Path | None = None) -> list[Stelle]:
    gefunden: list[Stelle] = []
    for datei in sorted((wurzel or WURZEL).rglob("*.py")):
        modul = ".".join(datei.with_suffix("").parts)
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not isinstance(knoten, ast.Call):
                continue
            if not isinstance(knoten.func, ast.Attribute):
                continue
            schluessel = (ast.unparse(knoten.func.value), knoten.func.attr)
            if schluessel not in AUFRUFE:
                continue
            stelle = AUFRUFE[schluessel]
            schluesselwort = next(
                (k.value for k in knoten.keywords if k.arg == "art"), None)
            if schluesselwort is not None:
                quelle = ast.unparse(schluesselwort)
            elif len(knoten.args) > stelle:
                quelle = ast.unparse(knoten.args[stelle])
            else:
                quelle = "?"
            gefunden.append(Stelle(modul, knoten.lineno,
                                   ".".join(schluessel), quelle))
    return gefunden


def abgedeckt() -> set[tuple[str, str]]:
    return ({(e.modul, e.art_quelle) for e in INVENTAR}
            | set(NICHT_LIVE_IN_PADUA))


def offen() -> list[Stelle]:
    bekannt = abgedeckt()
    return [s for s in aufrufstellen() if (s.modul, s.art_quelle) not in bekannt]


def eintrag_fuer(datei: str) -> Eintrag:
    for eintrag in INVENTAR:
        if eintrag.datei == datei:
            return eintrag
    raise KeyError(datei)


#: ------------------------------------------------------------------------
#: Was in Padua live ist. Ein Dump je Zeile. Die vier Namen 01-04 sind die
#: des Vorgaengers (docs/prompt-audit/2026-10-02-padua-p2) und bleiben, damit
#: die Groessen vergleichbar sind (D1).
INVENTAR = (
    # --- Gespraechszug je Phase. EINE Aufrufstelle (ablauf.py:1331), sieben
    # Dumps: der Prompt unterscheidet sich nur durch Phase und Datenlage.
    Eintrag("01-gespraech-phase1", "gespraech", 1,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("05-gespraech-phase2", "gespraech", 2,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("06-gespraech-phase3", "gespraech", 3,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("07-gespraech-phase4", "gespraech", 4,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("08-gespraech-phase5", "gespraech", 5,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("02-gespraech-phase6", "gespraech", 6,
            "interview_theater.ablauf", "'gespraech'"),
    Eintrag("09-gespraech-phase7", "gespraech", 7,
            "interview_theater.ablauf", "'gespraech'"),
    # --- Hintergrundwege
    Eintrag("10-erkenner-verlauf", "erkenner", 4,
            "interview_theater.erkenner", "'erkenner'"),
    Eintrag("11-erkenner-aufnahme", "erkenner", 3,
            "interview_theater.erkenner", "'erkenner'"),
    Eintrag("12-journal", "journal", 4,
            "interview_theater.journal", "'journal'"),
    Eintrag("13-begriffsboard", "begriffsboard", 1,
            "interview_theater.begriffsboard", "ART"),
    Eintrag("14-diskussion-verdichtung", "diskussion_verdichtung", 1,
            "interview_theater.diskussion", "ART"),
    Eintrag("15-fragen-ki", "fragen_ki_vorschlag", 2,
            "interview_theater.fragen_ki", "ART"),
    Eintrag("16-verdichter", "verdichter", 3,
            "interview_theater.verdichter", "'verdichter'"),
    Eintrag("17-buehnenkarte", "brainstorm_karte", 4,
            "interview_theater.buehnenkarte", "'brainstorm_karte'"),
    # --- Phase 4: Szenenfolge, Geschichte, Felder
    Eintrag("18-szenenfolge", "szenenfolge", 4,
            "interview_theater.szenenfolge", "art"),
    Eintrag("19-geschichte", "geschichte", 4,
            "interview_theater.szenenfolge", "art",
            weg="gebaut",
            grund="Dieselbe Aufrufstelle wie 18; der Unterschied steckt "
                  "allein in systemanweisung_geschichte/baue_nutzertext_"
                  "geschichte, die der Treiber direkt ruft."),
    Eintrag("20-szenenfelder", "szenenfelder", 4,
            "interview_theater.szenenfolge", "art",
            weg="gebaut",
            grund="Ebenfalls dieselbe Aufrufstelle; System- und Nutzertext "
                  "baut starte_feldvorschlag inline (szenenfolge.py:1374)."),
    # --- Phase 5
    Eintrag("21-schaerfung", "schaerfung", 5,
            "interview_theater.schaerfung", "ART"),
    Eintrag("22-entwurf-uebersicht", "entwurf_uebersicht", 5,
            "interview_theater.entwurf", "ART_UEBERSICHT"),
    Eintrag("23-sprachprofil", "sprachprofil", 5,
            "interview_theater.sprachprofil", "ART"),
    Eintrag("24-kernzitate", "kernzitate", 5,
            "interview_theater.kernzitate", "ART"),
    # --- Phase 6
    Eintrag("25-kurzgeschichte", "kurzgeschichte", 6,
            "interview_theater.kurzgeschichte", "art"),
    Eintrag("03-kurzgeschichte-phase6", "kurzgeschichte", 6,
            "interview_theater.kurzgeschichte", "art",
            weg="gebaut",
            grund="Der Kuerzungslauf derselben Stelle (vorlage=True, "
                  "kuerzung.notiz_fuer_prosa) -- Name aus dem Vorgaengerdump."),
    Eintrag("04-szene-prosa-phase6", "szene", 6,
            "interview_theater.szene", "art",
            weg="gebaut",
            grund="szene._lauf baut system=systemanweisung(form, stil) und "
                  "nutzer=baue_nutzertext(...) und uebergibt sie unveraendert "
                  "-- der gebaute Prompt ist zeichengleich (szene.py:2361)."),
    # --- Phase 7: Formen, Sprechweise, Stil, Stueckpruefung
    Eintrag("27-sprechweise", "sprechweise", 7,
            "interview_theater.sprechweise", "ART"),
    Eintrag("28-szene-dialog", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 04: der Treiber ruft systemanweisung('dialog') und "
                  "baue_nutzertext; eine Form je Dump."),
    Eintrag("29-szene-monolog", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, Form monolog."),
    Eintrag("30-szene-chor", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, Form chor."),
    Eintrag("31-szene-lied", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, Form lied."),
    Eintrag("32-szene-rap", "szene", 7,
            "interview_theater.szene", "art", weg="gebaut",
            grund="Wie 28, Form rap."),
    Eintrag("33-sprachstil", "sprachstil", 7,
            "interview_theater.sprachstil", "ART"),
    Eintrag("34-stueckpruefung", "stueckpruefung", 7,
            "interview_theater.stueckpruefung", "ART"),
    # --- Die Richterfragen des Prueflaufs (prueflauf.FRAGEN_*).
    Eintrag("35-dramaturgie-b1", "dramaturgie_b1", 6,
            "interview_theater.dramaturgie.fanout", "art"),
    Eintrag("36-dramaturgie-a2", "dramaturgie_a2", 6,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Dieselbe Aufrufstelle wie b1 (Richter.frage); der Treiber "
                  "ruft frage_a2 und faengt dort ab."),
    Eintrag("37-dramaturgie-a6", "dramaturgie_a6", 6,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Wie 36, Frage a6 (frage_a6)."),
    Eintrag("38-dramaturgie-a9", "dramaturgie_a9", 6,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Wie 36, Frage a9 (frage_a9)."),
    Eintrag("39-dramaturgie-a10", "dramaturgie_a10", 7,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Wie 36, Frage a10 (frage_a10) -- ab Phase 7 die Formregeln."),
    Eintrag("40-dramaturgie-a11", "dramaturgie_a11", 6,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Wie 36, Frage a11 (frage_a11)."),
    Eintrag("41-dramaturgie-c1", "dramaturgie_c1", 7,
            "interview_theater.dramaturgie.fanout", "art", weg="gebaut",
            grund="Wie 36, Frage c1 (frage_c1)."),
)

#: Aufrufstellen, die in Padua NICHT live sind -- mit Grund, nicht nur mit
#: Haken. Schluessel ist ``(modul, art_quelle)``, genau wie der Scanner sie
#: ausgibt.
NICHT_LIVE_IN_PADUA = {
    ("interview_theater.begriffsboard_analyse", "ART"):
        "Kein Live-Aufrufer -- einziger Aufrufer ist "
        "scripts/rauchtest_begriffsboard_resonanz.py, festgehalten in "
        "tests/test_begriffsboard_analyse.py::test_kein_live_aufrufer. Ob ein "
        "zweiter Live-Aufruf kommt, entscheidet Birk.",
    ("interview_theater.bot", "'erkenner'"):
        "Warmlauf beim Prozessstart (bot.warmlaufen) mit dem festen Text "
        "'Testaufruf.' -- kein Prompt der Gruppe, nichts zu pruefen.",
}
```

**Wichtig fuer den Ausfuehrenden:** `INVENTAR` und `NICHT_LIVE_IN_PADUA` oben
sind der **Entwurf aus der Planung**. Die Messung aus Schritt 1 ist die
Wahrheit. Jede Stelle, die der Scanner findet und die hier fehlt, wird
ergaenzt -- mit Phase und, wenn sie in Padua nicht laeuft, mit Grund.
`ANNAHME:` fuenf Punkte, die am Code zu pruefen sind, bevor das Inventar
eingefroren wird:
1. **`kernzitate`** (24) -- gerufen aus `knoepfe/figuren.py:201`. Lauft der
   Knopf in Padua noch an? Pruefen: `grep -n -B20 "kernzitate.starte" interview_theater/knoepfe/figuren.py`
   und ob der Weg hinter `ebene2_erlaubt` haengt. Wenn nicht erreichbar ->
   nach `NICHT_LIVE_IN_PADUA` mit genau diesem Grund.
2. **`sprachstil`** (33) -- `knoepfe/figuren.py:395`, nur bei
   `sprachstil.stilmaterial(...)`. Gleiche Pruefung.
3. **`nachpass`** (`szene_nachpass`, `kurzgeschichte_nachpass`) -- laeuft ueber
   `szene.schreibe`/`kurzgeschichte.hole_text` mit anderer `art`, also **keine
   eigene Aufrufstelle**. Pruefen mit
   `grep -rn "art=\|ART_SZENE\|ART_PROSA" interview_theater/nachpass.py`. Wenn
   keine eigene Stelle: kein Inventareintrag noetig; der Prompt ist der von 04
   plus der Regie-Notiz. Im BEFUND als Satz vermerken.
4. **`prueflauf_ueberarbeitung`** -- dito (`prueflauf.py:349/363` ruft
   `szene.schreibe`/`kurzgeschichte.schreibe` mit `art=ART_UEBERARBEITUNG`).
5. **`entwurf`/`sprechweise`/`schaerfung`** rufen `modellwahl.aufruf_schema`
   **mit** `modell=e.erkenner_modell`: ohne Claude laufen sie auf gemma, mit
   Claude auf Opus. Die Kopfzeile des Dumps muss das zeigen -- sie kommt aus
   dem Mitschnitt, ist also automatisch richtig.

- [ ] **Schritt 5: Test laufen lassen und das Inventar vervollstaendigen**

Run: `python3.11 -m pytest -q tests/test_modellaufrufe_inventar.py`
Expected: `7 passed`. Solange `test_keine_offene_aufrufstelle` rot ist, nennt
die Fehlermeldung Modul, Zeile und `art`-Ausdruck jeder fehlenden Stelle -- jede
davon wird ergaenzt, keine wird in eine Sammel-Ausnahme geschoben.

- [ ] **Schritt 6: Commit**

```bash
git add scripts/prompt_inventar.py tests/test_modellaufrufe_inventar.py
git commit -m "Prompt-Check Padua: Inventar aller Modellaufrufe, per AST genagelt"
```

---

## Task 4: Der mechanische Pruefer, Teil 1 -- Systemteil

**Files:**
- Modify: `scripts/pruefe_prompt_dumps.py` (heute 60 Zeilen, bleibt erhalten)
- Test: `tests/test_pruefe_prompt_dumps.py` (neu)

**Interfaces:**
- Consumes: nichts aus dem Projekt -- reine Textfunktionen, kein Import aus
  `interview_theater`. Der Pruefer liest Dateien, keine Datenbank.
- Produces:
  ```python
  DUBLETTE_AB: int = 80                        # bestehend
  VERBOTEN: tuple[str, ...]                    # bestehend
  KOPFZEILEN: tuple[str, ...]
  DE_STOPWOERTER: frozenset[str]
  VERBOTENE_UX: tuple[tuple[str, str], ...]    # (Muster, Erklaerung)
  FRAGEREGEL: re.Pattern
  def zeilen(text: str) -> list[str]           # bestehend
  def teile(text: str) -> tuple[str, str]      # (system, nutzer)
  def inhaltszeilen(text: str) -> list[tuple[int, str]]
  def deutsche_reste(text: str) -> list[tuple[int, str, str]]
  def verbotene_muster(text: str) -> list[tuple[int, str, str]]
  def frageregel_zeilen(text: str) -> list[tuple[int, str]]
  ```

**Warum DE-Reste gezaehlt werden:** Padua laeuft auf Englisch
(`[sprache] code = "en"`), und W3 im Code sagt: ein englischer Systemprompt mit
deutschem Nutzertext laesst das Modell deutsch antworten. Ein deutscher Rest ist
damit ein Betriebsfehler, kein Schoenheitsfehler.

**Gemessen am 05.10.2026 (Grundlage der Schwelle):** gegen die vier Dumps von
`docs/prompt-audit/2026-10-02-padua-p2/` liefert die Liste unten **0 Treffer**
in allen vier Dateien -- sobald die Kopfzeilen des Dumps selbst
(`# <name>`, `=== SYSTEM (26943 Zeichen, ~9112 Token) ===`) ausgenommen werden.
Ohne diese Ausnahme sind es genau 2 Treffer je Datei, beide das Wort
„Zeichen" aus der Kopfzeile, die `erzeuge_prompts._schreibe` schreibt.
**Also: Schwelle 0, Kopfzeilen uebersprungen.** Ebenfalls gemessen und deshalb
**nicht** in der Liste, weil auch englisch und damit Falsch-Positive: `also`
(1 Treffer je Datei), `was` (6-14 Treffer je Datei), dazu `wie`, `hier`, `war`,
`an`, `in`, `so`, `die`, `hat`, `man`, `bei`.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_pruefe_prompt_dumps.py`:

```python
"""Der mechanische Prompt-Pruefer: reine Funktionen, offline.

Die Schwelle fuer deutsche Reste ist 0, und das ist gemessen, nicht gesetzt:
gegen die vier Dumps vom 02.10.2026 liefert DE_STOPWOERTER null Treffer, sobald
die Kopfzeilen des Dumps selbst ausgenommen sind (sie tragen "Zeichen").
"""
from pathlib import Path

import pytest

from scripts import pruefe_prompt_dumps as p

BASIS_DUMPS = Path("docs/prompt-audit/2026-10-02-padua-p2")

DUMP = """# 99-probe
# eine Notiz
=== SYSTEM (42 Zeichen, ~14 Token) ===
Every suggestion message ends with an open question to the group.
At most ONE question per message -- and that one at the end.
Under the reflection of ONE value "Yes, save" and "No, change it again".
Bitte korrigiere das und schreibe eine Antwort.

=== NUTZER (17 Zeichen, ~6 Token) ===
Terms (0/3) saved.
"""


def test_teile_trennt_system_und_nutzer():
    system, nutzer = p.teile(DUMP)
    assert "Every suggestion message" in system
    assert "Terms (0/3)" in nutzer
    assert "Terms (0/3)" not in system


def test_inhaltszeilen_laesst_die_eigenen_kopfzeilen_weg():
    gefunden = p.inhaltszeilen(DUMP)
    texte = [t for _, t in gefunden]
    assert not any(t.startswith("===") or t.startswith("# ") for t in texte)
    assert gefunden[0][0] == 4      # 1-basiert auf die Datei bezogen
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: FAIL mit `AttributeError: module 'scripts.pruefe_prompt_dumps' has no attribute 'teile'`.

- [ ] **Schritt 3: `teile` und `inhaltszeilen` implementieren**

In `scripts/pruefe_prompt_dumps.py` **unter** die bestehenden Konstanten
(`from pathlib import Path` ist dort schon importiert):

```python
#: Die Kopfzeilen, die ``erzeuge_prompts._schreibe`` selbst schreibt. Sie sind
#: deutsch ("=== SYSTEM (26943 Zeichen, ~9112 Token) ===") und waeren in jedem
#: englischen Dump ein Falsch-Positiv -- gemessen am 05.10.2026 genau zwei
#: Treffer je Datei, beide aus dieser Zeile.
KOPFZEILEN = ("=== ", "# ")


def teile(text: str) -> tuple[str, str]:
    """(Systemteil, Nutzerteil). Der Trenner ist ``=== NUTZER``, wie in
    ``erzeuge_prompts._schreibe``."""
    stuecke = text.split("=== NUTZER")
    return stuecke[0], (stuecke[1] if len(stuecke) > 1 else "")


def inhaltszeilen(text: str) -> list[tuple[int, str]]:
    """Nummerierte, nicht-leere Zeilen ohne die Kopfzeilen des Dumps.

    Die Nummer ist **1-basiert und auf die Datei bezogen** -- genau die Zahl,
    die die Opus-Lesung spaeter in ihrem Befund nennt, damit das Zitat
    mechanisch geprueft werden kann."""
    ergebnis = []
    for nummer, zeile in enumerate(text.splitlines(), start=1):
        knapp = zeile.strip()
        if not knapp or knapp.startswith(KOPFZEILEN):
            continue
        ergebnis.append((nummer, knapp))
    return ergebnis
```

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: `2 passed`.

- [ ] **Schritt 4: Test fuer die drei Systemteil-Pruefungen schreiben**

An `tests/test_pruefe_prompt_dumps.py` anhaengen:

```python
def test_deutsche_reste_findet_den_deutschen_satz_mit_zeilennummer():
    treffer = p.deutsche_reste(DUMP)
    assert treffer, "der deutsche Satz in Zeile 7 muss gefunden werden"
    assert {n for n, _, _ in treffer} == {7}, treffer
    assert {"das", "und", "eine"} & {w for _, _, w in treffer}


def test_deutsche_reste_meldet_keine_englischen_woerter():
    englisch = "=== SYSTEM ===\nThis was also so in the past, man.\n"
    assert p.deutsche_reste(englisch) == []


def test_die_vier_dumps_vom_02_10_sind_deutschfrei():
    """Die gemessene Grundlage der Schwelle 0."""
    if not BASIS_DUMPS.exists():
        pytest.skip("Vergleichsdumps nicht im Worktree")
    for pfad in sorted(BASIS_DUMPS.glob("*.txt")):
        assert p.deutsche_reste(pfad.read_text(encoding="utf-8")) == [], pfad.name


def test_verbotene_ux_muster_mit_zeilennummer_und_erklaerung():
    treffer = p.verbotene_muster(p.teile(DUMP)[0])
    muster = {m for _, m, _ in treffer}
    assert "Yes, save" in muster
    assert "No, change it again" in muster
    for nummer, _, erklaerung in treffer:
        assert nummer > 0
        assert erklaerung.strip()


def test_verbotene_ux_muster_nur_im_systemteil():
    """Eine Systemzeile im VERLAUF ist kein Promptfehler.

    "Changed since - please fix it in the work status" ist ein echter
    Bot-Wortlaut (sprachen/en/texte.toml:48, _TEXT_UNDO_GEAENDERT). Im
    Systemteil ist er ein Befund, im Nutzerteil ist er Geschichte."""
    nutzer = "=== NUTZER ===\nYou: Changed since - please fix it in the work status\n"
    assert p.verbotene_muster(p.teile(nutzer)[1]) == []


def test_frageregel_zeilen_stellt_die_widersprueche_nebeneinander():
    texte = [t for _, t in p.frageregel_zeilen(p.teile(DUMP)[0])]
    assert any("ends with an open question" in t for t in texte)
    assert any("that one at the end" in t for t in texte)
```

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: FAIL, `AttributeError: ... has no attribute 'deutsche_reste'`.

- [ ] **Schritt 5: Die drei Pruefungen implementieren**

```python
#: Deutsche Funktionswoerter, die **kein** englisches Wort sind. Jedes Wort
#: hier ist am 05.10.2026 gegen die vier Dumps von 2026-10-02-padua-p2
#: gemessen worden: null Treffer. Bewusst NICHT in der Liste, weil auch
#: englisch und damit Falsch-Positive: also, was, wie, hier, war, an, in, so,
#: die, hat, man, bei.
DE_STOPWOERTER = frozenset({
    "und", "oder", "nicht", "eine", "einen", "einem", "dass", "sich", "der",
    "das", "den", "dem", "ist", "sind", "wird", "werden", "aber", "auch",
    "noch", "schon", "wenn", "weil", "ihre", "wir", "fuer", "für", "von",
    "zum", "zur", "aus", "ueber", "über", "durch", "ohne", "kann", "soll",
    "muss", "nur", "sehr", "immer", "jede", "jeder", "etwas", "nichts",
    "mehr", "weniger", "zwei", "drei", "vier", "fuenf", "fünf", "steht",
    "gibt", "wurde", "seine", "diese", "dieser", "damit", "dafuer", "dafür",
    "dabei", "dann", "dort", "woerter", "wörter", "zeichen", "deine", "euer",
    "eure", "bitte", "keine", "kein", "vielleicht", "natuerlich", "natürlich",
    "trotzdem", "deshalb", "ausserdem", "außerdem", "korrigiere", "schreibe",
})

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]+")

#: Was Birks UX-Regeln in einem Prompt verbieten -- je Eintrag Muster und der
#: Satz, der im Bericht daneben steht. Ein Muster ohne Erklaerung ist eine
#: Zahl, die niemand nachrechnen kann.
#:
#: ACHTUNG: "Yes, save"/"No, change it again" sind zugleich die ECHTEN
#: Knopfbeschriftungen (sprachen/en/texte.toml: _TEXT_SPEICHERN_KNOPF /
#: _TEXT_ANDERS_KNOPF). Ein Treffer ist deshalb kein automatischer Fix, sondern
#: eine Frage an Birk -- siehe Task 10.
VERBOTENE_UX = (
    ("Yes, save",
     "Bestaetigungs-Zeremonie: Entscheidungen werden automatisch gespeichert "
     "und mit EINER Systemzeile plus Undo quittiert (UX-Regel 3). Zugleich die "
     "echte Knopfbeschriftung -- vor einem Fix pruefen, siehe BEFUND."),
    ("No, change it again",
     "Wie 'Yes, save': dieselbe Zeremonie, dieselbe Doppelrolle."),
    ("please fix it in the work status",
     "Schiebt die Arbeit zur Gruppe zurueck, statt einen Weg anzubieten "
     "(UX-Regel 3: jedes Speichern hat ein Undo)."),
    ("ask whether",
     "Rueckfrage vor dem Speichern: 'speichern beim ersten Mal, keine "
     "Rueckfrage davor' (AGENTS.md, Haltung 06.09.2026)."),
    ("how many scenes",
     "Zahl und Umfang entscheidet die Gruppe; der Bot schlaegt keine Anzahl "
     "vor (UX-Regel 1)."),
    ("wake word",
     "Kein Weckwort fuer einen Bot, der in der Sitzung ohnehin zuhoert "
     "(UX-Regel 4)."),
)

#: Zeilen, die eine Frageregel aufstellen UND eine Position nennen. Sie werden
#: nebeneinander gedruckt, damit ein Mensch den Widerspruch sieht -- gemessen in
#: sprachen/en/prompts/system.md: Z146 "ends with an open question", Z148
#: "BEFORE the suggestion block", Z151 "that one at the end".
FRAGEREGEL = re.compile(
    r"question.{0,80}?\b(ends?|before|after|first|last)\b"
    r"|\b(ends?|before|after|first|last)\b.{0,80}?question",
    re.IGNORECASE | re.DOTALL,
)


def deutsche_reste(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Zeile, getroffenes Wort) je deutschem Funktionswort."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for wort in _WORT.findall(zeile.lower()):
            if wort in DE_STOPWOERTER:
                treffer.append((nummer, zeile, wort))
    return treffer


def verbotene_muster(text: str) -> list[tuple[int, str, str]]:
    """(Zeilennummer, Muster, Erklaerung). **Nur auf den Systemteil anwenden**
    -- im Nutzerteil sind diese Wortlaute Geschichte und kein Promptfehler."""
    treffer = []
    for nummer, zeile in inhaltszeilen(text):
        for muster, erklaerung in VERBOTENE_UX:
            if muster.lower() in zeile.lower():
                treffer.append((nummer, muster, erklaerung))
    return treffer


def frageregel_zeilen(text: str) -> list[tuple[int, str]]:
    return [(n, z) for n, z in inhaltszeilen(text) if FRAGEREGEL.search(z)]
```

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: `8 passed`.

Wenn `test_deutsche_reste_findet_den_deutschen_satz_mit_zeilennummer` eine
andere Nummer meldet: die Zeilen in `DUMP` nachzaehlen (`# 99-probe` ist Zeile 1,
der deutsche Satz Zeile 7) -- **nicht** die Funktion auf die Erwartung biegen.

- [ ] **Schritt 6: Commit**

```bash
git add scripts/pruefe_prompt_dumps.py tests/test_pruefe_prompt_dumps.py
git commit -m "Prompt-Check Padua: Pruefer Teil 1 -- deutsche Reste, UX-Muster, Frageregeln"
```

---

## Task 5: Der mechanische Pruefer, Teil 2 -- Nutzerteil, Groessen, Bericht

**Files:**
- Modify: `scripts/pruefe_prompt_dumps.py`
- Modify: `tests/test_pruefe_prompt_dumps.py`

**Interfaces:**
- Consumes: `teile`, `inhaltszeilen`, `deutsche_reste`, `verbotene_muster`,
  `frageregel_zeilen` aus Task 4
- Produces:
  ```python
  QUOTE: re.Pattern            # "(0/3)" und Verwandte
  SPRECHER: re.Pattern         # "Du:" / "You:" / "Mitglied 3:" / "Member 3:"
  SYSTEMMARKEN: tuple[str, ...]
  ECHO_MARKE: str
  def verlaufsbefund(nutzer: str) -> dict
  def dubletten_quer(nutzer: str) -> list[tuple[str, int]]
  def groessen(tsv) -> dict[str, int]
  def bericht(pfad: Path, basis: dict | None = None) -> dict   # erweitert
  def mechanik_markdown(berichte: list[dict]) -> str
  def main() -> None   # argv: <ordner> [--basis <tsv>|-] [--nach <datei>]
  ```

**Was Birk am 00:40 verlangt und wo es landet:**

| Frage | Funktion | Schluessel |
|---|---|---|
| Wie viele Zuege, wer spricht? | `verlaufsbefund` | `zuege`, `sprecher` |
| Gehen Bot- und Systemzeilen mit? | `verlaufsbefund` | `bot_zeilen`, `systemzeilen` |
| Transkript-Echos im Verlauf? | `verlaufsbefund` | `transkript_echos` |
| Quotenzaehler „(0/3)"? | `verlaufsbefund` | `quoten` |
| Dubletten Verlauf <-> Zusammenfassung? | `dubletten_quer` | `dubletten_quer` |
| Groesse gegen den letzten Befund | `groessen` | `delta_zeichen` |

**Die eine bewusste Abweichung von D5:** der **Token-Anteil je Block**
(system/status/verlauf/zusammenfassung) kommt **nicht** von hier. Der Pruefer
kennt keine Datenbank und importiert nichts aus `interview_theater`; die Anteile
entstehen im Dump-Lauf aus `kontext.baue(..., protokoll=...)` und stehen in
`uebersicht.tsv` (Task 7). Begruendung: ein Pruefer, der `kontext` importiert,
braucht eine Datenbank und ist dann kein Dateipruefer mehr.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

An `tests/test_pruefe_prompt_dumps.py` anhaengen:

```python
VERLAUF = """# 98-verlauf
=== SYSTEM (10 Zeichen, ~3 Token) ===
You are InScribe.

=== NUTZER (10 Zeichen, ~3 Token) ===
## What the group has decided so far
terms: arrival, waiting, strangers
progress: terms (0/3) done

## The conversation so far
Member 1: here is our wall of terms from the plenary
You: Good. The transcript runs live in the chat.
Member 2: i think waiting is the strongest one here
You: 📌 Agreed: Setting - A railway station
You: Noted:
You: Changed since - please fix it in the work status
Member 1: here is our wall of terms from the plenary
🎙 Interview 1: three hours on that bench

## Now
Member 3: can we go on
"""


def test_verlaufsbefund_zaehlt_zuege_sprecher_und_systemzeilen():
    befund = p.verlaufsbefund(p.teile(VERLAUF)[1])
    assert befund["zuege"] == 9
    assert befund["sprecher"] == ["Member 1", "Member 2", "Member 3", "You"]
    assert befund["bot_zeilen"] == 5
    assert befund["systemzeilen"] == 3
    assert befund["transkript_echos"] == 1
    assert [z for _, z in befund["quoten"]] == ["progress: terms (0/3) done"]


def test_dubletten_quer_findet_die_wortgleiche_wiederholung():
    treffer = p.dubletten_quer(p.teile(VERLAUF)[1])
    assert ("Member 1: here is our wall of terms from the plenary", 2) in treffer


def test_groessen_liest_die_basis_tsv(tmp_path):
    tsv = tmp_path / "uebersicht.tsv"
    tsv.write_text(
        "pfad\tsystem_zeichen\tnutzer_zeichen\ttoken_gesamt\n"
        "01-gespraech-phase1\t26943\t393\t9112\n", encoding="utf-8")
    assert p.groessen(tsv)["01-gespraech-phase1"] == 27336
    assert p.groessen(None) == {}


def test_groessen_liest_auch_eine_tsv_mit_neuen_spalten(tmp_path):
    """Die neue uebersicht.tsv (Task 7) hat mehr Spalten in anderer Ordnung --
    ``groessen`` liest deshalb nach SPALTENNAME, nicht nach Position."""
    tsv = tmp_path / "uebersicht.tsv"
    tsv.write_text(
        "pfad\tart\tphase\tsystem_zeichen\tnutzer_zeichen\n"
        "13-begriffsboard\tbegriffsboard\t1\t100\t50\n", encoding="utf-8")
    assert p.groessen(tsv)["13-begriffsboard"] == 150


def test_bericht_traegt_alle_schluessel(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    b = p.bericht(pfad, basis={"98-verlauf": 10})
    for schluessel in ("datei", "name", "system_zeichen", "nutzer_zeichen",
                       "dubletten", "verboten", "deutsche_reste", "ux_muster",
                       "frageregeln", "verlauf", "dubletten_quer",
                       "delta_zeichen"):
        assert schluessel in b, schluessel
    assert b["delta_zeichen"] > 0


def test_bericht_ohne_basis_meldet_neu(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    assert p.bericht(pfad, basis={})["delta_zeichen"] is None


def test_mechanik_markdown_nennt_datei_zuege_und_quotenzeile(tmp_path):
    pfad = tmp_path / "98-verlauf.txt"
    pfad.write_text(VERLAUF, encoding="utf-8")
    text = p.mechanik_markdown([p.bericht(pfad, basis={})])
    assert "## 98-verlauf.txt" in text
    assert "Zuege=9" in text
    assert "(0/3)" in text
    assert "neu" in text
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: FAIL, `AttributeError: ... has no attribute 'verlaufsbefund'`.

- [ ] **Schritt 3: Die Nutzerteil-Pruefungen implementieren**

```python
#: Ein Quotenzaehler: "(0/3)", "(2 / 5)". Birk 00:40: steht er als Quote da
#: ("du hast erst 0 von 3") oder neutral? Der Pruefer entscheidet das nicht --
#: er stellt die Zeilen hin, damit die Lesung sie beurteilen kann.
QUOTE = re.compile(r"\(\s*\d+\s*/\s*\d+\s*\)")

#: Eine Sprecherzeile im Verlaufsblock. Deutsch UND englisch, weil der
#: Nutzertext in Padua englisch ist (``kontext._SPRECHER_BOT`` -> "You",
#: ``_PSEUDONYM`` -> "Member {nummer}"), der Dump aber auch gegen ein deutsches
#: Profil gefahren werden kann. Die letzte Alternative faengt einen Klarnamen
#: (Dortmund ohne Pseudonyme) und ist bewusst eng: hoechstens 28 Zeichen und
#: Grossbuchstabe am Anfang, sonst waere "Note: see above" eine Sprecherzeile.
SPRECHER = re.compile(r"^(Du|You|Mitglied \d+|Member \d+|[A-Z][\w .'-]{0,27}):")

#: Die Systemzeilen, die als Bot-Zeile im Verlauf mitgehen. Gemessen:
#: ``repo.merke_bot_zeile`` legt sie als typ='text', ist_bot=1 ab -- sie sind
#: also Teil des Fensters, und genau das ist Birks Frage ("Gehen Bot-Zeilen,
#: Systemzeilen und Transkript-Echos mit?").
SYSTEMMARKEN = ("📌", "Noted:", "Changed since")

#: Das Mikrofon vor einem Transkript-Echo. Es soll im Verlauf NICHT stehen
#: (``repo.TYP_TRANSKRIPT`` faellt aus allen drei Fenstern) -- steht es da, ist
#: das ein Befund und keine Kleinigkeit: der Erkenner las am 06.09.2026
#: Interviewinhalt als Gruppenabsicht.
ECHO_MARKE = "🎙"


def verlaufsbefund(nutzer: str) -> dict:
    """Was im Nutzerteil an Verlauf steckt (Birk, 05.10.2026 00:40).

    Keine Bewertung, nur Zaehlung: ob fuenf Bot-Zeilen auf vier Gruppenzeilen
    richtig sind, entscheidet die Lesung -- hier entsteht die Zahl, an der sie
    sich festhalten kann."""
    zuege = []
    for nummer, zeile in inhaltszeilen(nutzer):
        treffer = SPRECHER.match(zeile)
        if treffer:
            zuege.append((nummer, treffer.group(1), zeile))
    return {
        "zuege": len(zuege),
        "sprecher": sorted({name for _, name, _ in zuege}),
        "bot_zeilen": sum(1 for _, name, _ in zuege if name in ("Du", "You")),
        "systemzeilen": sum(
            1 for _, _, zeile in zuege
            if any(marke in zeile for marke in SYSTEMMARKEN)
        ),
        "transkript_echos": sum(
            1 for _, zeile in inhaltszeilen(nutzer) if ECHO_MARKE in zeile
        ),
        "quoten": [(n, z) for n, z in inhaltszeilen(nutzer) if QUOTE.search(z)],
    }


def dubletten_quer(nutzer: str) -> list[tuple[str, int]]:
    """Wortgleiche Zeilen im Nutzerteil, ab 20 Zeichen.

    Kuerzer als ``DUBLETTE_AB``, weil hier Verlauf und Zusammenfassungsbloecke
    aneinanderstossen: die Dublette, die am 06.09.2026 wehgetan hat ("dieselbe
    Interview-Zusammenfassung 11x"), war eine Zeile und kein Satz."""
    gezaehlt = Counter(z for _, z in inhaltszeilen(nutzer) if len(z) >= 20)
    return sorted(((z, n) for z, n in gezaehlt.items() if n > 1),
                  key=lambda paar: (-paar[1], paar[0]))


def groessen(tsv) -> dict[str, int]:
    """``pfad -> system_zeichen + nutzer_zeichen`` aus einer ``uebersicht.tsv``.

    Gelesen wird nach **Spaltenname**, nicht nach Position: die neue Uebersicht
    (Task 7) hat mehr Spalten in anderer Ordnung, und ein Vergleich, der an
    Spalte 2 haengt, vergliche dann Phasennummern mit Zeichenzahlen.

    Ohne Pfad oder ohne Datei ein leeres Dict -- dann gilt jeder Dump als neu."""
    if tsv is None:
        return {}
    pfad = Path(tsv)
    if not pfad.exists():
        return {}
    reihen = pfad.read_text(encoding="utf-8").splitlines()
    if not reihen:
        return {}
    kopf = reihen[0].split("\t")
    try:
        i_pfad = kopf.index("pfad")
        i_sys = kopf.index("system_zeichen")
        i_nutz = kopf.index("nutzer_zeichen")
    except ValueError:
        return {}
    ergebnis = {}
    for zeile in reihen[1:]:
        felder = zeile.split("\t")
        if len(felder) <= max(i_pfad, i_sys, i_nutz):
            continue
        try:
            ergebnis[felder[i_pfad]] = int(felder[i_sys]) + int(felder[i_nutz])
        except ValueError:
            continue
    return ergebnis
```

- [ ] **Schritt 4: `bericht` erweitern und `mechanik_markdown` schreiben**

Die bestehende `bericht`-Funktion **ersetzen** -- alle alten Schluessel bleiben,
damit ein etwaiger Altaufrufer nicht bricht:

```python
def bericht(pfad, basis: dict | None = None) -> dict:
    pfad = Path(pfad)
    roh = pfad.read_text(encoding="utf-8")
    system, nutzer = teile(roh)
    lang = [z for z in zeilen(roh) if len(z) >= DUBLETTE_AB]
    vorher = (basis or {}).get(pfad.stem)
    jetzt = len(system) + len(nutzer)
    return {
        "datei": pfad.name,
        "name": pfad.stem,
        "system_zeichen": len(system),
        "nutzer_zeichen": len(nutzer),
        "dubletten": {z: n for z, n in Counter(lang).items() if n > 1},
        "verboten": [w for w in VERBOTEN if w in roh],
        "deutsche_reste": deutsche_reste(roh),
        "ux_muster": verbotene_muster(system),
        "frageregeln": frageregel_zeilen(system),
        "verlauf": verlaufsbefund(nutzer),
        "dubletten_quer": dubletten_quer(nutzer),
        "delta_zeichen": None if vorher is None else jetzt - vorher,
    }


def mechanik_markdown(berichte: list[dict]) -> str:
    """Ein Abschnitt je Dump. Geht so in ``mechanik.md`` wie nach stdout --
    zwei Formate waeren zwei Wahrheiten."""
    aus = ["# Mechanischer Prompt-Check", ""]
    for b in berichte:
        v = b["verlauf"]
        delta = "neu" if b["delta_zeichen"] is None else f"{b['delta_zeichen']:+d}"
        aus.append(f"## {b['datei']}")
        aus.append(
            f"- Groesse: system={b['system_zeichen']} "
            f"nutzer={b['nutzer_zeichen']} (gegen Basis: {delta})"
        )
        aus.append(
            f"- Verlauf: Zuege={v['zuege']} Bot-Zeilen={v['bot_zeilen']} "
            f"Systemzeilen={v['systemzeilen']} "
            f"Transkript-Echos={v['transkript_echos']} "
            f"Sprecher={', '.join(v['sprecher']) or '-'}"
        )
        for titel, eintraege in (
            ("Deutsche Reste",
             [f"Z{n}: {w} -- {z[:100]}" for n, z, w in b["deutsche_reste"]]),
            ("UX-Muster",
             [f"Z{n}: {m} -- {e}" for n, m, e in b["ux_muster"]]),
            ("Frageregeln (nebeneinander lesen)",
             [f"Z{n}: {z[:110]}" for n, z in b["frageregeln"]]),
            ("Quotenzaehler",
             [f"Z{n}: {z[:110]}" for n, z in v["quoten"]]),
            ("Dubletten im Nutzertext",
             [f"{n}x {z[:110]}" for z, n in b["dubletten_quer"]]),
            ("Dubletten ueber 80 Zeichen",
             [f"{n}x {z[:110]}" for z, n in sorted(
                 b["dubletten"].items(), key=lambda paar: -paar[1])]),
            ("Verbotene Reste", list(b["verboten"])),
        ):
            if eintraege:
                aus.append(f"- **{titel}:**")
                aus.extend(f"  - {e}" for e in eintraege)
        aus.append("")
    return "\n".join(aus)
```

- [ ] **Schritt 5: `main` ersetzen**

```python
def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Prompt-Dumps messen")
    zerleger.add_argument("ordner")
    zerleger.add_argument(
        "--basis",
        default="docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv",
        help="uebersicht.tsv des Vergleichsstands; '-' schaltet den Vergleich aus",
    )
    zerleger.add_argument(
        "--nach", default=None,
        help="Zieldatei des Markdown-Berichts (Vorgabe: <ordner>/mechanik.md)",
    )
    argumente = zerleger.parse_args()

    ordner = Path(argumente.ordner)
    basis = groessen(None if argumente.basis == "-" else argumente.basis)
    berichte = [bericht(p, basis) for p in sorted(ordner.glob("*.txt"))]
    text = mechanik_markdown(berichte)
    ziel = Path(argumente.nach) if argumente.nach else ordner / "mechanik.md"
    ziel.write_text(text + "\n", encoding="utf-8")
    print(text)
    # **Exit 0, immer.** Der Pruefer ist ein Bericht, kein Gate: das Gate ist
    # tests/test_modellaufrufe_inventar.py in der Suite plus die Pass-Regel im
    # END-Template (docs/flow-audit/vorlagen.md, Task 11). Ein Exit-Code, der
    # an einer Zaehlung haengt, macht aus jeder neuen Prompt-Zeile einen roten
    # Lauf -- und dann schaltet ihn jemand ab.
```

Der bestehende `import sys` darf weg, wenn ihn nichts mehr braucht; `re`,
`Counter` und `Path` sind bereits importiert.

- [ ] **Schritt 6: Tests laufen lassen**

Run: `python3.11 -m pytest -q tests/test_pruefe_prompt_dumps.py`
Expected: `15 passed`.

- [ ] **Schritt 7: Gegen den alten Stand fahren -- der Pruefer muss ihn lesen koennen**

Run:
```bash
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-02-padua-p2 \
  --basis - --nach /tmp/mechanik-alt.md > /tmp/mechanik-alt.stdout; echo "exit=$?"
grep -c "^## " /tmp/mechanik-alt.md
grep -c "Deutsche Reste" /tmp/mechanik-alt.md || true
grep -c "Yes, save" /tmp/mechanik-alt.md || true
```
Expected:
- `exit=0`
- `4` (ein Abschnitt je Dump)
- `0` fuer „Deutsche Reste" -- die gemessene Null aus Task 4
- `>= 1` fuer „Yes, save" (steht in `sprachen/en/prompts/phasen/6.md` und damit
  im Systemteil von `02-gespraech-phase6.txt`)

`/tmp/mechanik-alt.md` wird **nicht** committet, und
`docs/prompt-audit/2026-10-02-padua-p2/` bleibt unberuehrt (deshalb `--nach`).

- [ ] **Schritt 8: Commit**

```bash
git add scripts/pruefe_prompt_dumps.py tests/test_pruefe_prompt_dumps.py
git commit -m "Prompt-Check Padua: Pruefer Teil 2 -- Nutzerteil, Groessenvergleich, mechanik.md"
```

---

## Task 6: Der Dump-Lauf, Teil 1 -- Geruest, Treiber, Phasen 1-3

**Files:**
- Create: `scripts/erzeuge_prompts_padua_voll.py`
- Test: `tests/test_erzeuge_prompts_padua_voll.py`

**Interfaces:**
- Consumes: `scripts.fixture_padua_voll` (Task 1), `scripts.mitschnitt` (Task 2),
  `scripts.prompt_inventar` (Task 3), `simulation.attrappe.TelegramAttrappe`
- Produces:
  ```python
  BLOCKGRUPPEN: dict[str, tuple[str, ...]]
  TSV_SPALTEN: tuple[str, ...]
  THREAD_FRIST_S: float = 30.0

  class TreiberFehler(RuntimeError): ...

  def umgebung() -> einstellungen.Einstellungen
  @contextlib.contextmanager
  def fange_umriss(sammler: list)
  def kopfzeile(eintrag, aufruf) -> str
  def anteile(umriss: dict) -> dict[str, int]
  def schreibe_dump(ziel: Path, eintrag, aufruf, umriss=None) -> dict
  TREIBER: dict[str, callable]     # Dumpname -> (conn, e, tg, klm, chats) -> dict|None
  def treibe(conn, e, tg, klm, chats, eintrag) -> tuple[Aufruf, dict | None]
  def main_fuer_test(ziel, nur=None) -> list[dict]   # derselbe Lauf, ohne sys.argv
  def main() -> None               # argv: [zielverzeichnis] [--nur <name,name>]
  ```

**Warum ein eigenes Skript und nicht `erzeuge_prompts_padua` erweitert:** das
alte Skript ist der Nachweis der Karte P (01.10.2026) und wird von
`docs/prompt-audit/2026-10-01-padua-fix/BEFUND.md` beim Namen genannt. Es bleibt
unveraendert; das neue erbt nur `_schreibe`/`_entschaerfe` nicht, weil es eine
Kopfzeile mehr schreibt (das Modell) und eine Spalte mehr in die TSV.

**Die Kopfzeile** (D3, berechnet und nicht tabelliert): sie kommt aus dem, was
das Double wirklich bekommen hat.

```
# 13-begriffsboard
# art=begriffsboard phase=1 weg=claude modell=claude-opus-5 quelle=abgefangen
# Begriffsboard: ein Schema-Aufruf je qualifizierendem Segment
=== SYSTEM (…) ===
```

**Die Umgebung spiegelt den Live-Betrieb** (D3): `IT_WORKSHOP=padua-2026`
(vom Skript selbst gesetzt), `szene_anbieter="claude"`,
`szene_modell="claude-opus-5"`, `llm_modell="moonshotai/Kimi-K2.6"`,
`erkenner_modell="google/gemma-4-31B-it"`. Die Einwilligung entfaellt per
Profil (`[modellwahl] einwilligung = false`), also ist
`szene_claude.ist_aktiv` allein vom Betreiberschalter abhaengig.
**Die Env-Dateien unter `betrieb/` werden dafuer NICHT gelesen** -- die Werte
stehen in `umgebung()`. `ANNAHME:` die Live-Envs setzen `IT_SZENE_ANBIETER=claude`
und `IT_LLM_MODELL=moonshotai/Kimi-K2.6`; zu pruefen von Birk oder mit
`grep -h "IT_SZENE_ANBIETER\|IT_LLM_MODELL" betrieb/padua-gruppe*.env` von Hand
(nicht im Code). Stimmt etwas nicht, wird `umgebung()` angepasst und im BEFUND
vermerkt.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_erzeuge_prompts_padua_voll.py`:

```python
"""Der vollstaendige Padua-Prompt-Dump, offline in ein Temp-Verzeichnis.

Der Lauf geht nie ins Netz: ``scripts.mitschnitt`` ersetzt den Modellklienten,
``simulation.attrappe.TelegramAttrappe`` den Kanal, und die Datenbank ist eine
Wegwerfdatei.
"""
from pathlib import Path

import pytest

from scripts import erzeuge_prompts_padua_voll as dump
from scripts import prompt_inventar as inv

#: Die Dumps, die Task 6 fahren muss. Task 7 setzt diese Liste auf
#: ``[e.datei for e in inv.INVENTAR]`` hoch.
TEIL1 = (
    "01-gespraech-phase1", "05-gespraech-phase2", "06-gespraech-phase3",
    "10-erkenner-verlauf", "11-erkenner-aufnahme", "12-journal",
    "13-begriffsboard", "14-diskussion-verdichtung", "15-fragen-ki",
    "16-verdichter",
)


def test_umgebung_spiegelt_den_padua_betrieb():
    e = dump.umgebung()
    assert e.szene_anbieter == "claude"
    assert e.szene_modell == "claude-opus-5"
    assert e.llm_modell.startswith("moonshotai/")
    assert e.erkenner_modell.startswith("google/gemma")


def test_anteile_fasst_die_bloecke_in_vier_gruppen():
    umriss = {
        "system": 100,
        "bloecke": {"arbeitsstand": 10, "festlegungen": 5, "fenster": 40,
                    "ausloeser": 2, "verdichtungen": 20, "journal": 3},
        "gesamt": 80, "gesamt_mit_system": 180, "gekuerzt": False,
    }
    assert dump.anteile(umriss) == {
        "tok_system": 100, "tok_status": 15, "tok_verlauf": 42,
        "tok_zusammenfassung": 23,
    }


def test_kopfzeile_nennt_art_phase_weg_modell_und_quelle():
    from scripts.mitschnitt import Aufruf

    eintrag = inv.eintrag_fuer("13-begriffsboard")
    zeile = dump.kopfzeile(eintrag, Aufruf("begriffsboard", "claude",
                                           "claude-opus-5", "S", "N"))
    for stueck in ("art=begriffsboard", "phase=1", "weg=claude",
                   "modell=claude-opus-5", "quelle=abgefangen"):
        assert stueck in zeile, stueck


@pytest.mark.parametrize("name", TEIL1)
def test_jeder_dump_entsteht_und_traegt_system_und_nutzertext(tmp_path, name):
    zeilen = dump.main_fuer_test(tmp_path, nur=[name])
    pfad = tmp_path / f"{name}.txt"
    assert pfad.exists(), name
    text = pfad.read_text(encoding="utf-8")
    assert "=== SYSTEM" in text and "=== NUTZER" in text
    system = dump_system(text)
    assert len(system) > 200, (name, len(system))
    assert len(zeilen) == 1


def dump_system(text: str) -> str:
    return text.split("=== NUTZER")[0]


def test_phase3_gespraech_laeuft_auf_kimi_und_nicht_auf_opus(tmp_path):
    """Die unverhandelbare Ausnahme (modellwahl.py, Phase 3 = Interviews)."""
    dump.main_fuer_test(tmp_path, nur=["06-gespraech-phase3"])
    kopf = (tmp_path / "06-gespraech-phase3.txt").read_text(encoding="utf-8")
    assert "weg=infomaniak" in kopf
    assert "modell=moonshotai/" in kopf


def test_phase1_gespraech_laeuft_auf_opus(tmp_path):
    """Seit der Padua Phase 1+2 Karte ist jede Phase ausser 3 Opus-faehig."""
    dump.main_fuer_test(tmp_path, nur=["01-gespraech-phase1"])
    kopf = (tmp_path / "01-gespraech-phase1.txt").read_text(encoding="utf-8")
    assert "weg=claude" in kopf


def test_verdichter_laeuft_immer_auf_kimi(tmp_path):
    """verdichter.py ruft modellwahl NICHT an -- das ist die ganze
    Durchsetzung (modellwahl.py, Moduldocstring)."""
    dump.main_fuer_test(tmp_path, nur=["16-verdichter"])
    kopf = (tmp_path / "16-verdichter.txt").read_text(encoding="utf-8")
    assert "weg=infomaniak" in kopf
    assert "modell=moonshotai/" in kopf


def test_erkenner_und_journal_laufen_auf_gemma(tmp_path):
    for name in ("10-erkenner-verlauf", "11-erkenner-aufnahme", "12-journal"):
        dump.main_fuer_test(tmp_path, nur=[name])
        kopf = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
        assert "modell=google/gemma" in kopf, name


def test_ein_dump_ohne_aufzeichnung_ist_ein_lauter_fehler(tmp_path):
    """Ein Treiber, der den Aufruf nicht erreicht, darf keine leere Datei
    hinterlassen -- sonst sieht ein fehlender Pfad aus wie ein kurzer Prompt."""
    with pytest.raises(dump.TreiberFehler):
        dump.main_fuer_test(tmp_path, nur=["99-gibt-es-nicht"])


def test_das_skript_oeffnet_nie_betrieb():
    import inspect

    quelle = inspect.getsource(dump)
    for wort in ("betrieb/", "soap.db"):
        assert wort not in quelle, wort
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_erzeuge_prompts_padua_voll.py`
Expected: FAIL beim Sammeln, `ModuleNotFoundError: No module named 'scripts.erzeuge_prompts_padua_voll'`.

- [ ] **Schritt 3: Geruest, Umgebung, Umriss-Fang, Kopfzeile, Schreiber**

`scripts/erzeuge_prompts_padua_voll.py`:

```python
"""Jeder Modellaufruf, der in Padua live vorkommt -- als Volltext-Dump.

Aufruf (Karte t_1dcf3864, 05.10.2026)::

    python3.11 -m scripts.erzeuge_prompts_padua_voll \\
        docs/prompt-audit/2026-10-05-padua-voll

Das Skript setzt ``IT_WORKSHOP=padua-2026`` selbst (eine andere Variable weist
es ab) und baut sich eine Wegwerf-Datenbank mit sieben erfundenen Gruppen,
eine je Phase (``scripts.fixture_padua_voll``). ``IT_DB`` zeigt auf diese
Datei, weil ``anweisungen.system`` den Regie-Zettel (``zusatz.md``) daneben
sucht -- ein Zettel aus ``betrieb/`` stuende sonst im Dump. Die echte
Betriebsdatenbank wird nie geoeffnet.

**Aufgezeichnet wird an der Transportgrenze** (``scripts.mitschnitt``), nicht
nachgebaut: was im Dump steht, ist per Konstruktion das, was der Bot
verschickt haette. Wo das Fahren des echten Pfades unverhaeltnismaessig waere,
steht ``weg="gebaut"`` im Inventar -- mit Grund, und die Spalte ``quelle`` in
``uebersicht.tsv`` macht den Unterschied sichtbar.

Je Dump eine Datei mit Kopfzeile (art, phase, weg, modell, quelle),
``=== SYSTEM ===`` und ``=== NUTZER ===`` -- dasselbe Format wie
``scripts/erzeuge_prompts.py``, plus die Kopfzeile. Dazu ``uebersicht.tsv``
mit den Groessen und, fuer die Gespraechs-Dumps, dem Token-Anteil je
Blockgruppe (Birk, 05.10.2026 00:40).
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

from interview_theater import (
    anweisungen, db, einstellungen, kontext, repo, workshop,
)
from scripts import fixture_padua_voll as fixture
from scripts import mitschnitt as ms
from scripts import prompt_inventar as inv

#: Die vier Gruppen, in denen Birk den Nutzertext bemessen sehen will
#: (00:40: "token share per block ... (system/status/history/summary)").
#: Die Blocknamen sind die aus ``kontext._REIHENFOLGE`` -- gemessen:
#: verdichtungen, transkripte, kernpaket, arbeitsstand, festlegungen,
#: diskussion, begriffe_detail, phasenhinweis, figurenhinweis, szene, journal,
#: fenster, ausloeser, erstkontakt.
BLOCKGRUPPEN = {
    "tok_status": ("arbeitsstand", "festlegungen", "kernpaket", "szene",
                   "begriffe_detail", "phasenhinweis", "figurenhinweis"),
    "tok_verlauf": ("fenster", "ausloeser", "erstkontakt"),
    "tok_zusammenfassung": ("verdichtungen", "transkripte", "journal",
                            "diskussion"),
}

TSV_SPALTEN = (
    "pfad", "art", "phase", "weg", "modell", "quelle",
    "system_zeichen", "nutzer_zeichen", "token_gesamt",
    "tok_system", "tok_status", "tok_verlauf", "tok_zusammenfassung",
)

#: Wie lange auf einen Thread gewartet wird, den ein ``starte_*`` aufgemacht
#: hat. Das Double antwortet sofort; 30 s sind der Notausgang gegen einen
#: haengenden Lauf, kein Zielwert.
THREAD_FRIST_S = 30.0

#: Die Markierung vor der Profil-Anweisung, nur im Dump -- uebernommen aus
#: ``scripts/erzeuge_prompts_padua.py`` (Birk hat sie am 01.10.2026
#: abgenommen). Der Bot bekommt sie nie.
MARKE = "<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->"


class TreiberFehler(RuntimeError):
    """Ein Treiber hat seinen Modellaufruf nicht erreicht.

    Laut und nicht still: eine fehlende Datei sieht beim Lesen des Audits aus
    wie ein kurzer Prompt, und genau so verschwindet ein Pfad aus dem Check."""


def umgebung() -> einstellungen.Einstellungen:
    """Die Einstellungen des Padua-Live-Betriebs, als echte (frozen) dataclass.

    Echt und nicht ad hoc, weil ``dramaturgie.fanout.Richter.frage``
    ``dataclasses.replace(e, ...)`` ruft -- ein Ad-hoc-Objekt wuerde dort mit
    ``TypeError`` auffliegen."""
    return einstellungen.Einstellungen(
        bot_token="dump",
        bot_name="padua1",
        db_pfad=os.environ.get("IT_DB", ":memory:"),
        audio_verz="audio",
        llm_url="http://127.0.0.1:1/chat/completions",
        llm_key="dump",
        llm_modell="moonshotai/Kimi-K2.6",
        stt_basis="http://127.0.0.1:1",
        stt_produkt="dump",
        erkenner_modell="google/gemma-4-31B-it",
        szene_anbieter="claude",
        szene_modell="claude-opus-5",
    )


def _markiere(system: str) -> str:
    """Setzt die Abnahme-Markierung vor die Profil-Anweisung -- nur im Dump."""
    anweisung = (anweisungen.hole_optional(anweisungen.PROFIL_ANWEISUNG) or "").strip()
    if anweisung and anweisung in system:
        return system.replace(anweisung, f"{MARKE}\n{anweisung}", 1)
    return system


@contextlib.contextmanager
def fange_umriss(sammler: list):
    """Reicht ``protokoll=`` an jedes ``kontext.baue`` durch.

    **Warum gepatcht und nicht zweimal gerufen:** ``ablauf`` ruft
    ``kontext.baue`` ohne ``protokoll`` (``ablauf.py:1322``). Ein zweiter
    Messaufruf mit denselben Argumenten waere nicht derselbe Prompt -- der
    erste merkt sich das Phasenangebot (``arbeitsstand.phase_angeboten``) und
    kann einen Vorfall schreiben, der zweite saehe also eine andere Datenlage.
    Ein Patch misst genau den Aufruf, der auch den Dump fuellt."""
    echt = kontext.baue

    def baue(conn, chat_id, ausloeser, e, erstkontakt=False, protokoll=None,
             ueber_claude=False):
        eigen: list = [] if protokoll is None else protokoll
        text = echt(conn, chat_id, ausloeser, e, erstkontakt=erstkontakt,
                    protokoll=eigen, ueber_claude=ueber_claude)
        sammler.extend(eigen)
        return text

    kontext.baue = baue
    try:
        yield sammler
    finally:
        kontext.baue = echt


def kopfzeile(eintrag, aufruf) -> str:
    return (f"# art={eintrag.art} phase={eintrag.phase} weg={aufruf.weg} "
            f"modell={aufruf.modell} quelle={eintrag.weg}")


def anteile(umriss: dict) -> dict[str, int]:
    """Token je Blockgruppe aus einem ``kontext.umriss``.

    Ein Block, den ``BLOCKGRUPPEN`` nicht nennt, faellt heraus -- deshalb
    prueft ein Test, dass die Summe der Gruppen die Bloecke des Umrisses
    vollstaendig abdeckt."""
    bloecke = umriss.get("bloecke") or {}
    ergebnis = {"tok_system": int(umriss.get("system") or 0)}
    for gruppe, namen in BLOCKGRUPPEN.items():
        ergebnis[gruppe] = sum(int(bloecke.get(name) or 0) for name in namen)
    return ergebnis


def schreibe_dump(ziel: Path, eintrag, aufruf, umriss=None) -> dict:
    system = _markiere(aufruf.system or "")
    nutzer = aufruf.nutzer or ""
    notiz = eintrag.grund or eintrag.art
    (ziel / f"{eintrag.datei}.txt").write_text(
        f"# {eintrag.datei}\n{kopfzeile(eintrag, aufruf)}\n# {notiz}\n"
        f"=== SYSTEM ({len(system)} Zeichen, "
        f"~{kontext.schaetze(system)} Token) ===\n{system}\n\n"
        f"=== NUTZER ({len(nutzer)} Zeichen, "
        f"~{kontext.schaetze(nutzer)} Token) ===\n{nutzer}\n",
        encoding="utf-8",
    )
    zeile = {
        "pfad": eintrag.datei,
        "art": eintrag.art,
        "phase": eintrag.phase,
        "weg": aufruf.weg,
        "modell": aufruf.modell,
        "quelle": eintrag.weg,
        "system_zeichen": len(system),
        "nutzer_zeichen": len(nutzer),
        "token_gesamt": kontext.schaetze(system) + kontext.schaetze(nutzer),
        "tok_system": "", "tok_status": "", "tok_verlauf": "",
        "tok_zusammenfassung": "",
    }
    if umriss:
        zeile.update(anteile(umriss))
    return zeile
```

Run: `python3.11 -m pytest -q tests/test_erzeuge_prompts_padua_voll.py -k "umgebung or anteile or kopfzeile or betrieb"`
Expected: `4 passed`.

- [ ] **Schritt 4: Die Treiber der Phasen 1-3 schreiben**

Weiter in `scripts/erzeuge_prompts_padua_voll.py`. Jeder Treiber bekommt
`(conn, e, tg, klm, chats)` und laeuft **synchron**; gibt er einen Umriss
zurueck, landet er in der TSV.

```python
def _gespraech(phase: int):
    """Der echte Gespraechszug dieser Phase.

    Gefahren wird ``ablauf.antworte`` -- der oeffentliche Weg, nicht
    ``kontext.baue`` von Hand: nur so stehen Systemanweisung, Streamsenke und
    die Modellwahl (``modellwahl.konversation_ueber_claude``, Phase-3-Ausnahme)
    wirklich wie im Betrieb im Prompt."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater import ablauf

        chat_id = chats[phase]
        offen = repo.letzte_nachrichten(conn, chat_id, anzahl=1)
        umriss: list = []
        with fange_umriss(umriss):
            ablauf.antworte(conn, tg, klm, e, chat_id, list(offen))
        return umriss[-1] if umriss else None
    return treiber


def _erkenner_verlauf(conn, e, tg, klm, chats):
    from interview_theater import erkenner

    chat_id = chats[4]
    erkenner.erkenne(conn, klm, e, chat_id)
    return None


def _erkenner_aufnahme(conn, e, tg, klm, chats):
    from interview_theater import erkenner

    chat_id = chats[3]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    text = repo.zusammengefuegtes_transkript(conn, aufnahme["id"]) or ""
    erkenner.erkenne_in_aufnahme(conn, klm, e, chat_id, text)
    return None


def _journal(conn, e, tg, klm, chats):
    from interview_theater import journal

    chat_id = chats[4]
    journal.extrahiere(conn, klm, e, chat_id)
    return None


def _begriffsboard(conn, e, tg, klm, chats):
    from interview_theater import begriffsboard

    chat_id = chats[1]
    bis = max(a["id"] for a in repo.transkripte(conn, chat_id))
    begriffsboard._lauf_einmal(conn, klm, e, chat_id, bis)
    return None


def _diskussion(conn, e, tg, klm, chats):
    from interview_theater import diskussion

    chat_id = chats[1]
    diskussion.starte(conn, tg, klm, e, chat_id)
    return None


def _fragen_ki(conn, e, tg, klm, chats):
    from interview_theater import fragen_ki

    chat_id = chats[2]
    fragen_ki.starte(conn, tg, klm, e, chat_id)
    return None


def _verdichter(conn, e, tg, klm, chats):
    from interview_theater import verdichter

    chat_id = chats[3]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    text = repo.zusammengefuegtes_transkript(conn, aufnahme["id"]) or ""
    verdichter.verdichte(conn, klm, e, chat_id, aufnahme["id"], text)
    return None


TREIBER = {
    "01-gespraech-phase1": _gespraech(1),
    "05-gespraech-phase2": _gespraech(2),
    "06-gespraech-phase3": _gespraech(3),
    "10-erkenner-verlauf": _erkenner_verlauf,
    "11-erkenner-aufnahme": _erkenner_aufnahme,
    "12-journal": _journal,
    "13-begriffsboard": _begriffsboard,
    "14-diskussion-verdichtung": _diskussion,
    "15-fragen-ki": _fragen_ki,
    "16-verdichter": _verdichter,
}


def treibe(conn, e, tg, klm, chats, eintrag):
    """Faehrt einen Inventareintrag und liefert ``(Aufruf, Umriss|None)``.

    Ein Treiber, der seinen Aufruf nicht erreicht, ist ein ``TreiberFehler`` --
    nicht eine leere Datei."""
    treiber = TREIBER.get(eintrag.datei)
    if treiber is None:
        raise TreiberFehler(f"kein Treiber fuer {eintrag.datei}")
    vorher = len(klm.aufrufe)
    umriss = treiber(conn, e, tg, klm, chats)
    neu = [a for a in klm.aufrufe[vorher:] if a.art == eintrag.art]
    if not neu:
        gesehen = sorted({a.art for a in klm.aufrufe[vorher:]})
        raise TreiberFehler(
            f"{eintrag.datei}: kein Aufruf mit art={eintrag.art!r} "
            f"aufgezeichnet (gesehen: {gesehen})"
        )
    return neu[0], umriss
```

**`ANNAHME:` fuenf Funktionsnamen in den Treibern sind nicht verifiziert.**
Vor dem Implementieren pruefen und, wenn sie anders heissen, den richtigen
Namen nehmen (nicht erfinden, nicht eine neue Funktion bauen):

```bash
grep -n "^def erkenne\|^def erkenne_in_aufnahme" interview_theater/erkenner.py
grep -n "^def extrahiere\|^def laufe" interview_theater/journal.py
grep -n "^def verdichte" interview_theater/verdichter.py
grep -n "^def transkripte\|^def zusammengefuegtes_transkript\|^def letzte_nachrichten" interview_theater/repo.py
```
Expected: je eine Zeile. `repo.transkripte` und
`repo.zusammengefuegtes_transkript` sind in `scripts/erzeuge_prompts.py:123-124`
belegt, `repo.letzte_nachrichten` in `erzeuge_prompts.py:139`;
`erkenner.erkenne_in_aufnahme` ist im Code belegt (`erkenner.py:545` liegt in
dieser Funktion) -- die **Signaturen** der drei Erkenner-/Journal-/Verdichter-
Funktionen sind es nicht.

- [ ] **Schritt 5: `main` und `main_fuer_test` schreiben**

```python
def _schreibe_tsv(ziel: Path, zeilen: list[dict]) -> str:
    aus = ["\t".join(TSV_SPALTEN)]
    for zeile in zeilen:
        aus.append("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))
    text = "\n".join(aus) + "\n"
    (ziel / "uebersicht.tsv").write_text(text, encoding="utf-8")
    return text


def _lauf(ziel: Path, nur: list[str] | None) -> list[dict]:
    os.environ.setdefault(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    anweisungen._CACHE.clear()
    if workshop.name() != "padua-2026":
        raise SystemExit(
            "IT_WORKSHOP=padua-2026 setzen -- sonst entsteht der Dortmunder Prompt."
        )
    ziel.mkdir(parents=True, exist_ok=True)
    eintraege = [e for e in inv.INVENTAR if not nur or e.datei in nur]
    if nur:
        bekannt = {e.datei for e in inv.INVENTAR}
        fehlend = [n for n in nur if n not in bekannt]
        if fehlend:
            raise TreiberFehler(f"nicht im Inventar: {fehlend}")

    from simulation.attrappe import TelegramAttrappe

    zeilen: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        pfad = os.path.join(tmp, "padua-prompts.db")
        os.environ["IT_DB"] = pfad
        conn = db.verbinde(pfad)
        db.initialisiere(conn)
        chats = fixture.baue_alle(conn)
        e = umgebung()
        tg = TelegramAttrappe()
        klm = ms.Mitschnitt(e)
        with ms.fange_alles(klm):
            for eintrag in eintraege:
                aufruf, umriss = treibe(conn, e, tg, klm, chats, eintrag)
                zeilen.append(schreibe_dump(ziel, eintrag, aufruf, umriss))
        conn.close()
    _schreibe_tsv(ziel, zeilen)
    return zeilen


def main_fuer_test(ziel, nur=None) -> list[dict]:
    """Derselbe Lauf, aber mit Rueckgabewert und ohne ``sys.argv``."""
    return _lauf(Path(ziel), list(nur) if nur else None)


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Padua-Prompt-Dump")
    zerleger.add_argument(
        "ziel", nargs="?", default="docs/prompt-audit/2026-10-05-padua-voll")
    zerleger.add_argument(
        "--nur", default=None,
        help="Kommaliste von Dumpnamen (Vorgabe: alle aus prompt_inventar)")
    argumente = zerleger.parse_args()
    nur = argumente.nur.split(",") if argumente.nur else None
    zeilen = _lauf(Path(argumente.ziel), nur)
    print("\t".join(TSV_SPALTEN))
    for zeile in zeilen:
        print("\t".join(str(zeile.get(s, "")) for s in TSV_SPALTEN))


if __name__ == "__main__":
    main()
```

- [ ] **Schritt 6: Tests laufen lassen und bis gruen nacharbeiten**

Run: `python3.11 -m pytest -q tests/test_erzeuge_prompts_padua_voll.py`
Expected: `19 passed` (4 Struktur + 10 parametrisiert + 5 Modellwege/Fehler).

Erwartbare Ursachen, wenn ein `TreiberFehler` fliegt -- jeweils mit Loesung:
1. **`ablauf.antworte` steigt vorher aus** (`_zug_faellt_aus`,
   `ist_wiederholung`, `ist_auftrag`). Pruefen mit
   `grep -n "def _zug_faellt_aus" -A12 interview_theater/ablauf.py`. Loesung:
   die letzte Zeile des Fixture-Verlaufs je Phase ist eine **Gruppen**zeile
   (kein Bot), kurz, keine Wiederholung der vorigen Bot-Nachricht und kein
   Auftrag -- in `fixture_padua_voll._JE_PHASE` steht sie schon so (`"ok"`,
   `"when do we see the whole script?"`). Falls doch: eine neutrale
   Gruppenzeile anhaengen, nicht die Vorfahrtsregel anfassen.
2. **`begriffsboard._lauf_einmal` findet kein Transkript.** `repo.transkripte`
   liefert nur `klasse='lang'`-Aufnahmen? Dann in der Fixture statt
   `repo.transkripte` direkt
   `SELECT id FROM aufnahme WHERE chat_id=? AND diskussion=1` im Treiber lesen.
3. **`fragen_ki.starte`/`diskussion.starte` laufen in einem Thread.** Beide
   haben `versuche_start`/`beende`; wenn `starte` einen Thread liefert, mit
   `thread.join(THREAD_FRIST_S)` warten. Pruefen mit
   `grep -n -A12 "^def starte" interview_theater/fragen_ki.py`.
4. **Ein Profilschalter blockt** (`[diskussion] aktiv`, `[fragen_ab] aktiv`) --
   beide sind in `workshop/padua-2026/profil.toml` auf `true` (gemessen).
   Blockt trotzdem etwas, nennt der Code den Grund im Log; dann den Grund in
   `NICHT_LIVE_IN_PADUA` schreiben statt den Schalter umzubiegen.

- [ ] **Schritt 7: Commit**

```bash
git add scripts/erzeuge_prompts_padua_voll.py tests/test_erzeuge_prompts_padua_voll.py
git commit -m "Prompt-Check Padua: Dump-Lauf Teil 1 -- Geruest und Phasen 1-3"
```

---

## Task 7: Der Dump-Lauf, Teil 2 -- Phasen 4-7 und die Blockanteile

**Files:**
- Modify: `scripts/erzeuge_prompts_padua_voll.py`
- Modify: `scripts/prompt_inventar.py` (nur `weg`/`grund` dreier Gruppen)
- Modify: `tests/test_erzeuge_prompts_padua_voll.py`

**Interfaces:**
- Consumes: alles aus Task 6
- Produces: `TREIBER` vollstaendig (alle Eintraege aus `inv.INVENTAR`)

- [ ] **Schritt 1: Das Inventar korrigieren -- drei Gruppen sind doch fahrbar**

Beim Schreiben der Treiber zeigt sich, dass drei Eintraege aus Task 3 **nicht**
gebaut werden muessen, weil es einen oeffentlichen, synchron fahrbaren Weg gibt.
`weg="gebaut"` ist die Ausnahme und muss so klein bleiben wie moeglich (D1).
In `scripts/prompt_inventar.py` aendern:

- `19-geschichte` -> `weg="abgefangen"`, `grund=""`
  (Weg: `szenenfolge.starte_geschichte` + `thread.join`)
- `20-szenenfelder` -> `weg="abgefangen"`, `grund=""`
  (Weg: `szenenfolge.starte_feldvorschlag` + `thread.join`)
- `36-dramaturgie-a2` bis `41-dramaturgie-c1` -> `weg="abgefangen"`, `grund=""`
  (Weg: `fanout.frage_a2` … `frage_c1`, je ein synchroner Aufruf)

**Gebaut bleiben genau sieben** -- und zwar mit demselben, gemessenen Grund:
`03-kurzgeschichte-phase6`, `04-szene-prosa-phase6`, `28-szene-dialog`,
`29-szene-monolog`, `30-szene-chor`, `31-szene-lied`, `32-szene-rap`.
Der Grund steht im Code (`interview_theater/szene.py:2361-2362`):

```python
system = systemanweisung(form, stil)
nutzer = baue_nutzertext(conn, chat_id, auftrag, ziel, e, system=system)
```

Der live verschickte Prompt **ist** das Ergebnis dieser zwei Aufrufe,
unveraendert. Ein `szene.schreibe` zu fahren hiesse, danach `zerlege` auf die
Mitschnitt-Marke loszulassen, eine Sperre zu nehmen und eine Fassung zu
schreiben -- Aufwand ohne Gewinn an Wahrheit. Dasselbe fuer
`kurzgeschichte.hole_text` (`kurzgeschichte.py:443-453`).

Run: `python3.11 -m pytest -q tests/test_modellaufrufe_inventar.py`
Expected: `7 passed` (`test_gebaute_eintraege_begruenden_sich` prueft weiter,
dass jeder verbleibende `gebaut`-Eintrag einen Grund > 20 Zeichen hat).

- [ ] **Schritt 2: Die Tests fuer Teil 2 schreiben**

In `tests/test_erzeuge_prompts_padua_voll.py` die Liste `TEIL1` **ersetzen**:

```python
#: Alle Dumps des Inventars -- Task 7 hebt die Teilliste aus Task 6 auf.
ALLE = tuple(e.datei for e in inv.INVENTAR)
```

und die parametrisierte Pruefung auf `ALLE` umstellen
(`@pytest.mark.parametrize("name", ALLE)`). Dazu anhaengen:

```python
def test_alle_inventareintraege_haben_einen_treiber():
    fehlend = [e.datei for e in inv.INVENTAR if e.datei not in dump.TREIBER]
    assert not fehlend, fehlend


def test_ein_voller_lauf_schreibt_jede_datei_und_die_uebersicht(tmp_path):
    zeilen = dump.main_fuer_test(tmp_path)
    assert len(zeilen) == len(inv.INVENTAR)
    for eintrag in inv.INVENTAR:
        assert (tmp_path / f"{eintrag.datei}.txt").exists(), eintrag.datei
    kopf = (tmp_path / "uebersicht.tsv").read_text(
        encoding="utf-8").splitlines()[0].split("\t")
    assert kopf == list(dump.TSV_SPALTEN)


def test_die_gespraechsdumps_tragen_blockanteile(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["07-gespraech-phase4"])
    zeile = dict(zip(
        dump.TSV_SPALTEN,
        (tmp_path / "uebersicht.tsv").read_text(
            encoding="utf-8").splitlines()[1].split("\t")))
    for spalte in ("tok_system", "tok_status", "tok_verlauf",
                   "tok_zusammenfassung"):
        assert zeile[spalte] != "", spalte
        assert int(zeile[spalte]) >= 0
    assert int(zeile["tok_verlauf"]) > 0
    assert int(zeile["tok_zusammenfassung"]) > 0


def test_blockgruppen_decken_jeden_block_des_umrisses_ab():
    """Sonst faellt ein Block still aus der Messung -- und genau das war
    Befund C.1 des Audits vom 06.09.2026 (die Systemanweisung fehlte im
    Umriss, also war ein Viertel des Prompts unvermessen)."""
    from interview_theater import kontext

    gruppiert = {name for namen in dump.BLOCKGRUPPEN.values() for name in namen}
    assert set(kontext._REIHENFOLGE) == gruppiert, (
        set(kontext._REIHENFOLGE) ^ gruppiert)


def test_szene_und_kurzgeschichte_sind_als_gebaut_gekennzeichnet(tmp_path):
    dump.main_fuer_test(tmp_path, nur=["28-szene-dialog"])
    kopf = (tmp_path / "28-szene-dialog.txt").read_text(encoding="utf-8")
    assert "quelle=gebaut" in kopf


def test_die_fuenf_formen_liefern_fuenf_verschiedene_systemtexte(tmp_path):
    namen = ["28-szene-dialog", "29-szene-monolog", "30-szene-chor",
             "31-szene-lied", "32-szene-rap"]
    dump.main_fuer_test(tmp_path, nur=namen)
    texte = {
        n: dump_system((tmp_path / f"{n}.txt").read_text(encoding="utf-8"))
        for n in namen
    }
    assert len(set(texte.values())) == 5, "ein Regelblock je Form"


def test_die_richterdumps_laufen_nicht_auf_dem_schreibermodell(tmp_path):
    """Self-Enhancement Bias: der Richter ist nie das schreibende Modell
    (dramaturgie/fanout.waehle_richter)."""
    namen = [e.datei for e in inv.INVENTAR if e.art.startswith("dramaturgie_")]
    dump.main_fuer_test(tmp_path, nur=namen)
    for name in namen:
        kopf = (tmp_path / f"{name}.txt").read_text(encoding="utf-8")
        assert "weg=infomaniak" in kopf, name
        assert "claude" not in kopf.splitlines()[1], name


def test_phase7_szene_sieht_den_sprachstil_der_figuren(tmp_path):
    """Padua M1: figur.sprachstil steht als eigene Zeile im Szenen-Prompt."""
    dump.main_fuer_test(tmp_path, nur=["28-szene-dialog"])
    text = (tmp_path / "28-szene-dialog.txt").read_text(encoding="utf-8")
    assert "questions instead of statements" in text
```

Run: `python3.11 -m pytest -q tests/test_erzeuge_prompts_padua_voll.py`
Expected: FAIL, `test_alle_inventareintraege_haben_einen_treiber` listet die
fehlenden Namen.

- [ ] **Schritt 3: Die Treiber der Phasen 4 und 5 schreiben**

In `scripts/erzeuge_prompts_padua_voll.py`, vor `TREIBER`:

```python
def _joine(faden) -> None:
    """Wartet auf einen Thread, den ein ``starte_*`` aufgemacht hat.

    ``None`` heisst: es gab nichts anzustossen (Sperre, Vorbedingung) -- dann
    faellt ``treibe`` mit ``TreiberFehler`` auf, und das ist richtig: ein
    Dump, der still nicht entsteht, ist ein Loch im Check."""
    if faden is not None and hasattr(faden, "join"):
        faden.join(THREAD_FRIST_S)


def _buehnenkarte(conn, e, tg, klm, chats):
    from interview_theater import buehnenkarte

    buehnenkarte.erzeuge(conn, e, klm, chats[4])
    return None


def _szenenfolge(conn, e, tg, klm, chats):
    from interview_theater import szenenfolge

    _joine(szenenfolge.starte(conn, tg, klm, e, chats[4], anzahl=3))
    return None


def _geschichte(conn, e, tg, klm, chats):
    from interview_theater import szenenfolge

    _joine(szenenfolge.starte_geschichte(conn, tg, klm, e, chats[4], anzahl=3))
    return None


def _szenenfelder(conn, e, tg, klm, chats):
    from interview_theater import szenenfolge

    chat_id = chats[4]
    ziel = repo.hole_szenen(conn, chat_id)[0]
    _joine(szenenfolge.starte_feldvorschlag(conn, tg, klm, e, chat_id, ziel))
    return None


def _schaerfung(conn, e, tg, klm, chats):
    from interview_theater import schaerfung

    chat_id = chats[5]
    schaerfung.mappe(conn, klm, e, chat_id, schaerfung._eintraege(conn, chat_id))
    return None


def _entwurf(conn, e, tg, klm, chats):
    from interview_theater import entwurf

    entwurf.generiere_uebersicht(klm, conn, e, chats[5])
    return None


def _sprachprofil(conn, e, tg, klm, chats):
    from interview_theater import sprachprofil

    chat_id = chats[5]
    aufnahme = repo.transkripte(conn, chat_id)[0]
    figur = repo.figuren(conn, chat_id)[0]
    repo.setze_figur_quelle(conn, figur["id"], aufnahme["id"])
    sprachprofil.erzeuge(conn, klm, e, figur["id"])
    return None


def _kernzitate(conn, e, tg, klm, chats):
    from interview_theater import kernzitate

    chat_id = chats[5]
    repo.setze_arbeitsstand(conn, chat_id, "kernthema", "waiting and belonging")
    repo.setze_arbeitsstand(
        conn, chat_id, "kernfrage",
        "When does a place you only waited in start to be yours?")
    kernzitate.waehle(conn, klm, e, chat_id)
    return None
```

**`ANNAHME:` fuenf Namen in diesem Block sind nicht verifiziert.** Vor dem
Implementieren pruefen, und wenn sie anders heissen, den richtigen Namen nehmen:

```bash
grep -n "^def mappe\|^def _eintraege" interview_theater/schaerfung.py
grep -n "^def erzeuge\|^def starte" interview_theater/sprachprofil.py
grep -n "^def waehle\|^def _eintraege" interview_theater/kernzitate.py
grep -n "^def setze_figur_quelle\|^def hole_szenen\|^def figuren" interview_theater/repo.py
grep -n "^def starte" -A6 interview_theater/szenenfolge.py | head -30
```
Expected: je eine Zeile. Belegt sind `schaerfung._eintraege` und
`kernzitate._eintraege` (beide aus `scripts/erzeuge_prompts.py:211/221`),
`repo.hole_szenen`, `repo.figuren`, `szenenfolge.starte`,
`starte_geschichte`, `starte_feldvorschlag`, `buehnenkarte.erzeuge(conn, e, klm, chat_id)`
(`buehnenkarte.py:103`), `entwurf.generiere_uebersicht(klm, conn, e, chat_id, notiz=None)`
(`entwurf.py:144`). **Nicht** belegt: `schaerfung.mappe`, `sprachprofil.erzeuge`,
`kernzitate.waehle`, `repo.setze_figur_quelle`.

Fuer `24-kernzitate` und `33-sprachstil` gilt zusaetzlich die offene Frage aus
Task 3: ist der Weg in Padua ueberhaupt erreichbar? Ergibt die Pruefung „nein",
wandert der Eintrag nach `NICHT_LIVE_IN_PADUA` (mit genau diesem Grund), der
Treiber entfaellt, und im BEFUND steht ein Satz dazu. **Nicht** heimlich
trotzdem dumpen -- der Check soll zeigen, was live ist.

- [ ] **Schritt 4: Die Treiber der Phasen 6 und 7 schreiben**

```python
#: Die Regie-Notiz, mit der die Szenen- und Prosalaeufe gefahren werden.
#: Erfunden, englisch, und genau der Satz aus dem Fixture-Verlauf der Phase 6
#: -- so steht im Dump dieselbe Bitte, die die Gruppe im Chat geaeussert hat.
NOTIZ_PROSA = "Elena should say something to him, a bit rude at first."
NOTIZ_SZENE = "Rewrite scene 2."


def _kurzgeschichte(conn, e, tg, klm, chats):
    from interview_theater import kurzgeschichte

    chat_id = chats[6]
    system = kurzgeschichte.systemanweisung()
    nutzer = kurzgeschichte.baue_nutzertext(conn, chat_id, NOTIZ_PROSA)
    klm.prosa(chat_id, system, nutzer, "kurzgeschichte")
    return None


def _kurzgeschichte_kuerzer(conn, e, tg, klm, chats):
    from interview_theater import kuerzung, kurzgeschichte

    chat_id = chats[6]
    system = kurzgeschichte.systemanweisung()
    nutzer = kurzgeschichte.baue_nutzertext(
        conn, chat_id, kuerzung.notiz_fuer_prosa(), vorlage=True)
    klm.prosa(chat_id, system, nutzer, "kurzgeschichte")
    return None


def _szene(phase: int, form: str, auftrag: str, datei_art: str = "szene"):
    """Ein Szenen-Dump je Form. ``weg="gebaut"`` (siehe Inventar): der live
    verschickte Prompt IST ``systemanweisung(form, stil)`` plus
    ``baue_nutzertext(..., system=system)`` (szene.py:2361-2362)."""
    def treiber(conn, e, tg, klm, chats):
        from interview_theater import szene as szene_modul

        chat_id = chats[phase]
        ziel = repo.hole_szenen(conn, chat_id)[1]
        system = szene_modul.systemanweisung(form, ziel["stil"] if "stil" in ziel.keys() else None)
        nutzer = szene_modul.baue_nutzertext(
            conn, chat_id, auftrag, ziel, e, system=system)
        klm.prosa(chat_id, system, nutzer, datei_art)
        return None
    return treiber


def _sprechweise(conn, e, tg, klm, chats):
    from interview_theater import sprechweise

    _joine(sprechweise.starte(conn, tg, klm, e, chats[7]))
    return None


def _sprachstil(conn, e, tg, klm, chats):
    from interview_theater import sprachstil

    chat_id = chats[7]
    figur = repo.figuren(conn, chat_id)[0]
    _joine(sprachstil.starte(conn, tg, klm, e, chat_id, figur["name"]))
    return None


def _stueckpruefung(conn, e, tg, klm, chats):
    from interview_theater import stueckpruefung

    _joine(stueckpruefung.starte(conn, tg, klm, e, chats[7]))
    return None


def _richter(e, conn, chat_id):
    """Der Richter, wie ihn der Prueflauf waehlt.

    Kein eigener Code: ``fanout.waehle_richter`` entscheidet, und mit
    ``szene_anbieter="claude"`` ist das Infomaniak-Modell (``e.llm_modell``)
    -- die Gegenmassnahme gegen den Self-Enhancement Bias."""
    from interview_theater.dramaturgie import fanout

    return fanout.waehle_richter(e, conn, chat_id)


def _dramaturgie(frage: str):
    def treiber(conn, e, tg, klm, chats):
        from interview_theater.dramaturgie import fanout, mechanik

        phase = 7 if frage in ("a10", "c1") else 6
        chat_id = chats[phase]
        richter = _richter(e, conn, chat_id)
        szenen = repo.hole_szenen(conn, chat_id)
        if frage == "b1":
            fanout.frage_b1(conn, e, klm, chat_id, richter, szenen[0])
        elif frage == "a9":
            fanout.frage_a9(conn, e, klm, chat_id, richter, szenen[0])
        elif frage == "a10":
            fanout.frage_a10(conn, e, klm, chat_id, richter, szenen[0])
        elif frage == "a11":
            fanout.frage_a11(conn, e, klm, chat_id, richter)
        elif frage == "a2":
            fanout.frage_a2(conn, e, klm, chat_id, richter)
        elif frage == "a6":
            lage = mechanik.lage(conn, chat_id)
            fanout.frage_a6(conn, e, klm, chat_id, richter,
                            mechanik.tschechow_kandidaten(lage))
        elif frage == "c1":
            ziel = szenen[0]
            figuren = [f["name"] for f in repo.figuren(conn, chat_id)]
            repliken = mechanik.repliken(ziel["volltext"] or "", figuren)
            fanout.frage_c1(conn, e, klm, chat_id, richter, ziel["nummer"],
                            repliken)
        return None
    return treiber
```

**`ANNAHME:` drei Namen sind nicht verifiziert** --
`sprachstil.starte(conn, tg, klm, e, chat_id, name)` (belegt:
`knoepfe/figuren.py:395` ruft es mit `offen["name"]`),
`stueckpruefung.starte(conn, tg, klm, e, chat_id, nachbereitung=...)`
(belegt: `ueberarbeitung.py:561`) und `mechanik.lage(conn, chat_id)`.
Letzteres pruefen mit
`grep -n "^def lage\|^class Szenenlage\|def szenenlage" interview_theater/dramaturgie/mechanik.py`
-- `mechanik.tschechow_kandidaten(lage: Szenenlage)` ist belegt
(`mechanik.py:591`), der Weg zur `Szenenlage` nicht.
Liefert `frage_a6` ohne Kandidaten `None` (laut Docstring: „None, wenn es keine
Kandidaten gibt"), dann fehlt dem Dump sein Aufruf und `treibe` meldet das
laut. Loesung: in der Fixture bei der Phase-6-Gruppe ein Tschechow-Objekt
einbauen -- ein Gegenstand, der in Szene 1 auftaucht und spaeter nicht
wiederkommt (die kaputte Tasche steht schon in `_SZENEN`, notfalls einen Satz
ergaenzen). **Nicht** die Frage aus dem Inventar nehmen: sie laeuft im
Prueflauf der Phase 6 (`prueflauf.FRAGEN_GESCHICHTE = ("a2","a6","a9","a11")`).

- [ ] **Schritt 5: `TREIBER` vervollstaendigen**

```python
TREIBER = {
    # Phasen 1-3 (Task 6)
    "01-gespraech-phase1": _gespraech(1),
    "05-gespraech-phase2": _gespraech(2),
    "06-gespraech-phase3": _gespraech(3),
    "10-erkenner-verlauf": _erkenner_verlauf,
    "11-erkenner-aufnahme": _erkenner_aufnahme,
    "12-journal": _journal,
    "13-begriffsboard": _begriffsboard,
    "14-diskussion-verdichtung": _diskussion,
    "15-fragen-ki": _fragen_ki,
    "16-verdichter": _verdichter,
    # Phase 4
    "07-gespraech-phase4": _gespraech(4),
    "17-buehnenkarte": _buehnenkarte,
    "18-szenenfolge": _szenenfolge,
    "19-geschichte": _geschichte,
    "20-szenenfelder": _szenenfelder,
    # Phase 5
    "08-gespraech-phase5": _gespraech(5),
    "21-schaerfung": _schaerfung,
    "22-entwurf-uebersicht": _entwurf,
    "23-sprachprofil": _sprachprofil,
    "24-kernzitate": _kernzitate,
    # Phase 6
    "02-gespraech-phase6": _gespraech(6),
    "25-kurzgeschichte": _kurzgeschichte,
    "03-kurzgeschichte-phase6": _kurzgeschichte_kuerzer,
    "04-szene-prosa-phase6": _szene(6, "prosa", NOTIZ_SZENE),
    # Phase 7
    "09-gespraech-phase7": _gespraech(7),
    "27-sprechweise": _sprechweise,
    "28-szene-dialog": _szene(7, "dialog", "Write scene 2."),
    "29-szene-monolog": _szene(7, "monolog", "Write scene 2."),
    "30-szene-chor": _szene(7, "chor", "Write scene 2."),
    "31-szene-lied": _szene(7, "lied", "Write scene 2."),
    "32-szene-rap": _szene(7, "rap", "Write scene 2."),
    "33-sprachstil": _sprachstil,
    "34-stueckpruefung": _stueckpruefung,
    # Die Richterfragen des Prueflaufs
    "35-dramaturgie-b1": _dramaturgie("b1"),
    "36-dramaturgie-a2": _dramaturgie("a2"),
    "37-dramaturgie-a6": _dramaturgie("a6"),
    "38-dramaturgie-a9": _dramaturgie("a9"),
    "39-dramaturgie-a10": _dramaturgie("a10"),
    "40-dramaturgie-a11": _dramaturgie("a11"),
    "41-dramaturgie-c1": _dramaturgie("c1"),
}
```

`38-dramaturgie-a9` und `35-dramaturgie-b1` fehlen in der `INVENTAR`-Liste aus
Task 3 nicht -- `a9` steht dort als `38-dramaturgie-a9`; falls beim Abschreiben
etwas fehlt, ergaenzen (`prueflauf.FRAGEN_GESCHICHTE` nennt a2, a6, a9, a11;
`FRAGEN_PROSASZENE` b1, a10; `FRAGEN_BUEHNENSZENE` a10, c1 -- **gemessen**,
`prueflauf.py:50-55`). Sieben Fragen, sieben Dumps.

- [ ] **Schritt 6: Tests laufen lassen**

Run: `python3.11 -m pytest -q tests/test_erzeuge_prompts_padua_voll.py`
Expected: alle gruen; die parametrisierte Pruefung laeuft ueber alle
Inventareintraege (Stand Plan: 39 Dumps, abzueglich dessen, was nach
`NICHT_LIVE_IN_PADUA` gewandert ist).

Wenn `test_blockgruppen_decken_jeden_block_des_umrisses_ab` rot ist: ein
Blockname aus `kontext._REIHENFOLGE` fehlt in `BLOCKGRUPPEN`. Ihn der Gruppe
zuordnen, die seiner Rolle entspricht (Daten der Gruppe -> `tok_status`,
Gespraechsverlauf -> `tok_verlauf`, Verdichtetes/Material -> `tok_zusammenfassung`)
-- **nicht** den Test lockern.

- [ ] **Schritt 7: Commit**

```bash
git add scripts/erzeuge_prompts_padua_voll.py scripts/prompt_inventar.py \
        tests/test_erzeuge_prompts_padua_voll.py
git commit -m "Prompt-Check Padua: Dump-Lauf Teil 2 -- Phasen 4-7 und Blockanteile"
```

---

## Task 8: Die UX-Regeln im Repo und die Opus-Lesung

**Files:**
- Create: `docs/prompt-audit/ux-regeln-participatory-bot-ux.md`
- Create: `scripts/pruefe_prompts_lesung.py`
- Test: `tests/test_prompt_lesung.py`

**Interfaces:**
- Consumes: `simulation.claude.Claude` (Opus ueber den lokalen Proxy, Abo,
  0 CHF je Aufruf), `interview_theater.zitat.pruefe`,
  `scripts.prompt_inventar.INVENTAR`
- Produces:
  ```python
  REGELN: Path    # docs/prompt-audit/ux-regeln-participatory-bot-ux.md
  RUBRIK: Path    # simulation/ux_rubrik.md
  ANWEISUNG: str                 # Modulkonstante, keine Prompt-Datei
  KAPPE_ABC: int = 10
  KAPPE_D: int = 5
  FENSTER_ZEILEN: int = 2
  ZEICHEN_MAX: int = 240_000
  KATEGORIEN: tuple[str, ...] = ("a", "b", "c", "d")

  def nummeriere(text: str) -> str
  def zeilenfenster(text: str, zeile: int, fenster: int = FENSTER_ZEILEN) -> str
  def nutzertext(phase: int, dumps: dict[str, str], regeln: str,
                 rubrik: str) -> tuple[str, bool]     # (Text, gekappt?)
  def pruefe_befund(befund: dict, dumps: dict[str, str]) -> bool
  def kappe(befunde: list[dict]) -> list[dict]
  def lies_phase(klient, phase: int, dumps: dict[str, str], regeln: str,
                 rubrik: str) -> tuple[list[dict], list[dict]]
                 # (geprueft, unsicher)
  def main() -> None   # argv: <audit-ordner> [--phase N] [--trocken]
  ```

**Warum die Regeln ins Repo kopiert werden** (D6): die Quelle liegt ausserhalb
(`~/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md`, 264
Zeilen, **gemessen** mit dem Read-Werkzeug lesbar). Ein Audit, dessen Maßstab
nicht im Repository liegt, ist in sechs Monaten nicht nachvollziehbar.
**Kopiert wird mit dem Read/Write-Werkzeug, nicht mit `cp`:** die Sandbox dieser
Session verweigert Shell-Zugriff ausserhalb des Worktrees (gemessen: `ls` auf
den Skill-Pfad wurde geblockt, `Read` lief).

**Warum jedes Zitat mechanisch geprueft wird:** dieselbe Begruendung wie bei der
Dramaturgie-Pruefung -- ein Judge kann jede Note begruenden, auch eine falsche,
weil die Begruendung nach dem Urteil entsteht. Geprueft wird mit
`zitat.pruefe`, **derselben** Funktion wie bei Verdichter, Kernzitaten,
Sprachprofil, Schaerfung und Dramaturgie; **keine zweite, groesszuegigere
Normalisierung**. Ein Retry mit dem Hinweis „dein Zitat kam nicht vor", danach
faellt der Befund als `unsicher` heraus und wird geloggt.

**Zwei Auslegungen, die der Plan entscheidet** (im Zweifel wie die Karte
geschrieben ist):
1. **Die Kappe 10 gilt fuer (a), (b) und (c) ZUSAMMEN**, 5 fuer (d) -- so ist
   der Kartentext gebaut („separated into (a),(b),(c), max 10 per phase; PLUS
   (d) …, max 5"). Gekappt wird **nach** der Zitatpruefung, sonst verdraengt ein
   unbelegter Befund einen belegten.
2. **Das Zitat darf ueber Zeilengrenzen gehen**: geprueft wird gegen ein Fenster
   von `FENSTER_ZEILEN = 2` Zeilen um die genannte Nummer. Ohne das Fenster
   faellt jedes Zitat durch, das ueber einen Umbruch laeuft -- und die
   Prompt-Dateien sind auf 80 Zeichen umbrochen.

- [ ] **Schritt 1: Die UX-Regeln ins Repo kopieren**

Mit dem **Read**-Werkzeug
`/home/birk/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md`
lesen und mit dem **Write**-Werkzeug nach
`docs/prompt-audit/ux-regeln-participatory-bot-ux.md` schreiben -- woertlich,
mit diesem Kopf davor (und ohne den YAML-Frontmatter des Skills):

```markdown
<!--
Woertliche Kopie von
~/.hermes/profiles/birk/skills/creative/participatory-bot-ux/SKILL.md
(Version 1.0.0), kopiert am 05.10.2026 fuer die Karte t_1dcf3864.

**Warum im Repository:** die Opus-Lesung des Prompt-Checks
(scripts/pruefe_prompts_lesung.py) liest diese Regeln als Massstab. Ein
Massstab, der ausserhalb des Repositories liegt, ist in sechs Monaten nicht
mehr nachvollziehbar -- und die Befunde im BEFUND.md zeigen auf
Regelnummern aus dieser Datei.

**Die Quelle bleibt die Quelle.** Eine neue Korrektur von Birk gehoert in den
Skill; diese Kopie wird dann neu gezogen (Datum im Kopf aktualisieren), nicht
hier gepflegt.
-->
```

- [ ] **Schritt 2: Die Kopie pruefen**

Run:
```bash
head -12 docs/prompt-audit/ux-regeln-participatory-bot-ux.md
grep -c "^## " docs/prompt-audit/ux-regeln-participatory-bot-ux.md
grep -n "Checklist before proposing a design" docs/prompt-audit/ux-regeln-participatory-bot-ux.md
```
Expected: der Kommentarkopf mit „kopiert am 05.10.2026"; `9` Abschnitte
(1. The group authors … 8. Model choice … How Birk decides … Checklist);
eine Trefferzeile fuer die Checkliste. **Gemessen** an der Quelle: 264 Zeilen,
Abschnitte „1. The group authors, the bot assists" bis „Checklist before
proposing a design".

- [ ] **Schritt 3: Den fehlschlagenden Test schreiben**

`tests/test_prompt_lesung.py`:

```python
"""Die Opus-Lesung: Nummerierung, Zitatwache, Kappung -- alles offline.

Der echte Lauf kostet 0 CHF (Abo-Proxy) und wird vom Controller gefahren
(Task 9). Hier laeuft nur ein Fake-Klient: kein Netz, keine Zufaelligkeit.
"""
from pathlib import Path

import pytest

from scripts import pruefe_prompts_lesung as lesung

DUMP = """# 07-gespraech-phase4
# art=gespraech phase=4 weg=claude modell=claude-opus-5 quelle=abgefangen
=== SYSTEM (10 Zeichen, ~3 Token) ===
Every suggestion message ends with an open question to the group.
At most ONE question per message -- and that one at the end.

=== NUTZER (5 Zeichen, ~2 Token) ===
Member 1: ok
"""


class KlientAttrappe:
    """Liefert vorbereitete Antworten in Reihenfolge und zaehlt die Aufrufe."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def json_objekt(self, system, nutzer, art="sim", max_tokens=None,
                    bilder=None):
        self.aufrufe.append((system, nutzer))
        return self._antworten.pop(0)


def test_nummeriere_setzt_eins_basierte_nummern_vor_jede_zeile():
    text = lesung.nummeriere("eins\nzwei\n")
    assert text.splitlines()[0].startswith("1| eins")
    assert text.splitlines()[1].startswith("2| zwei")


def test_zeilenfenster_nimmt_nachbarzeilen_mit():
    fenster = lesung.zeilenfenster(DUMP, 4, fenster=1)
    assert "Every suggestion message" in fenster
    assert "At most ONE question" in fenster


def test_pruefe_befund_nimmt_ein_woertliches_zitat_an():
    befund = {"kategorie": "a", "datei": "07-gespraech-phase4", "zeile": 4,
              "zitat": "ends with an open question", "regel": "4",
              "vorschlag": "weg damit"}
    assert lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_pruefe_befund_lehnt_ein_erfundenes_zitat_ab():
    befund = {"kategorie": "a", "datei": "07-gespraech-phase4", "zeile": 4,
              "zitat": "always end with three questions", "regel": "4",
              "vorschlag": "x"}
    assert not lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_pruefe_befund_lehnt_eine_unbekannte_datei_ab():
    befund = {"kategorie": "a", "datei": "gibt-es-nicht", "zeile": 1,
              "zitat": "x", "regel": "4", "vorschlag": "x"}
    assert not lesung.pruefe_befund(befund, {"07-gespraech-phase4": DUMP})


def test_kappe_nimmt_zehn_aus_abc_und_fuenf_aus_d():
    befunde = (
        [{"kategorie": "a", "zitat": f"a{i}"} for i in range(8)]
        + [{"kategorie": "b", "zitat": f"b{i}"} for i in range(8)]
        + [{"kategorie": "d", "zitat": f"d{i}"} for i in range(9)]
    )
    gekappt = lesung.kappe(befunde)
    assert sum(1 for b in gekappt if b["kategorie"] in "abc") == 10
    assert sum(1 for b in gekappt if b["kategorie"] == "d") == 5


def test_lies_phase_prueft_zitate_und_wiederholt_genau_einmal():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "erfunden", "regel": "4",
                      "vorschlag": "x"}]},
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "ends with an open question",
                      "regel": "4", "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert len(klient.aufrufe) == 2, "genau ein Retry"
    assert len(geprueft) == 1
    assert not unsicher
    assert "did not appear" in klient.aufrufe[1][1]


def test_lies_phase_verwirft_nach_dem_retry():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "erfunden", "regel": "4",
                      "vorschlag": "x"}]},
        {"befunde": [{"kategorie": "a", "datei": "07-gespraech-phase4",
                      "zeile": 4, "zitat": "auch erfunden", "regel": "4",
                      "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert geprueft == []
    assert len(unsicher) == 1


def test_lies_phase_fragt_nicht_nach_wenn_alles_belegt_ist():
    klient = KlientAttrappe([
        {"befunde": [{"kategorie": "c", "datei": "07-gespraech-phase4",
                      "zeile": 5, "zitat": "At most ONE question",
                      "regel": "veraltet", "vorschlag": "x"}]},
    ])
    geprueft, unsicher = lesung.lies_phase(
        klient, 4, {"07-gespraech-phase4": DUMP}, "REGELN", "RUBRIK")
    assert len(klient.aufrufe) == 1
    assert len(geprueft) == 1


def test_nutzertext_nennt_die_nummerierten_dumps_regeln_und_rubrik():
    text, gekappt = lesung.nutzertext(
        4, {"07-gespraech-phase4": DUMP}, "DIE-REGELN", "DIE-RUBRIK")
    assert "DIE-REGELN" in text and "DIE-RUBRIK" in text
    assert "07-gespraech-phase4" in text
    assert "4| Every suggestion message" in text
    assert gekappt is False


def test_nutzertext_kappt_und_sagt_es(monkeypatch):
    monkeypatch.setattr(lesung, "ZEICHEN_MAX", 200)
    text, gekappt = lesung.nutzertext(
        4, {"a": DUMP, "b": DUMP, "c": DUMP}, "R", "U")
    assert gekappt is True
    assert "truncated" in text


def test_die_anweisung_ist_eine_modulkonstante_und_keine_prompt_datei():
    """Kein neuer Prompt unter interview_theater/prompts/ -- diese Lesung ist
    ein Werkzeug des Audits, kein Bot-Verhalten."""
    assert len(lesung.ANWEISUNG) > 400
    assert not Path("interview_theater/prompts/lesung.md").exists()
```

- [ ] **Schritt 4: Test laufen lassen, Fehlschlag sehen**

Run: `python3.11 -m pytest -q tests/test_prompt_lesung.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'scripts.pruefe_prompts_lesung'`.

- [ ] **Schritt 5: Das Lesungsskript schreiben**

`scripts/pruefe_prompts_lesung.py`:

```python
"""Opus liest die Prompt-Dumps einer Phase gegen Birks UX-Regeln.

Aufruf (Karte t_1dcf3864, 05.10.2026)::

    python3.11 -m scripts.pruefe_prompts_lesung \\
        docs/prompt-audit/2026-10-05-padua-voll

**Kein Test, laeuft nie automatisch** -- aber es kostet **nichts**: der Lauf
geht ueber ``simulation/claude.py`` an den lokalen Proxy, und der laeuft auf
einem Abonnement (dieselbe Trennlinie wie in der Simulation: der Pruefling
laeuft bei Infomaniak, die Pruefinstanz bei Opus). Sieben Aufrufe, einer je
Phase, **seriell**.

**Jedes Zitat wird mechanisch geprueft** (``zitat.pruefe``, dieselbe Funktion
wie bei Verdichter, Kernzitaten, Sprachprofil, Schaerfung und Dramaturgie --
keine zweite, groesszuegigere Normalisierung). Ein Judge kann jede Note
begruenden, auch eine falsche: die Begruendung entsteht nach dem Urteil, und
die Zitatpflicht ist das einzige mechanische Gegenmittel. Faellt ein Zitat
durch, gibt es **einen** Retry mit dem Hinweis; danach ist der Befund
``unsicher``, landet in ``lesung-unsicher.jsonl`` und geht nicht in den BEFUND.
"""

from __future__ import annotations

import json
from pathlib import Path

from interview_theater import zitat
from scripts import prompt_inventar as inv

REGELN = Path("docs/prompt-audit/ux-regeln-participatory-bot-ux.md")
RUBRIK = Path("simulation/ux_rubrik.md")

#: Kappe fuer (a), (b) und (c) ZUSAMMEN, und fuer (d) eigens. So ist der
#: Kartentext gebaut; gekappt wird NACH der Zitatpruefung, sonst verdraengt ein
#: unbelegter Befund einen belegten.
KAPPE_ABC = 10
KAPPE_D = 5

#: Ein Zitat darf ueber einen Zeilenumbruch gehen -- die Prompt-Dateien sind
#: auf 80 Zeichen umbrochen. Geprueft wird gegen ein Fenster um die genannte
#: Zeile.
FENSTER_ZEILEN = 2

#: Obergrenze des Nutzertexts je Phase. Phase 7 traegt rund zwoelf Dumps;
#: 240.000 Zeichen sind grob 80.000 Token und passen ins Opus-Fenster.
#: ANNAHME: ungemessen -- ``nutzertext`` sagt im Text, wenn es gekappt hat,
#: und der BEFUND nennt jede gekappte Phase.
ZEICHEN_MAX = 240_000

KATEGORIEN = ("a", "b", "c", "d")

#: Die Leseanweisung. **Modulkonstante und keine Prompt-Datei**: das ist ein
#: Werkzeug des Audits, kein Bot-Verhalten -- eine Datei unter
#: ``interview_theater/prompts/`` wuerde vom Profil-Lader, vom
#: Platzhalter-Check und vom Dortmund-Schnappschuss mitgezogen.
ANWEISUNG = """You read the actual prompts of a theatre workshop bot and look
for contradictions. You are given, for ONE workshop phase: the bot's UX rules,
a UX rubric, and every prompt the bot really sends in that phase (system part
and user part), with 1-based line numbers.

Report findings in four categories:
  a = prompt contradicts a UX rule
  b = prompt contradicts another prompt (or itself)
  c = dead or outdated text (names a button, phase, command or mechanic that
      no longer exists in the prompts you were given)
  d = context structure: how the USER part is built -- chat history (how many
      turns, cut where, who speaks, do bot lines, system lines and transcript
      echoes go along, duplicates), the saved work status (complete?
      unambiguously named? saved vs. only proposed? counters phrased as a
      quota?), summaries (do they duplicate the history? outdated? order and
      weight sensible?), sections and order (context -> status -> history ->
      "Now"), reminder lines in the right place.

Rules you must follow:
- Every finding quotes the prompt VERBATIM, and names the file and the line
  number the quote starts on. A quote that is not literally in the dump is
  worthless; do not paraphrase, do not fix spelling, do not translate.
- At most 10 findings across a, b and c together, and at most 5 for d. Rank by
  how much the group would notice.
- No finding without a concrete proposal. "Improve the wording" is not a
  proposal; "delete line 146, it contradicts line 151" is.
- Judge only what you were given. Do not assume code, buttons or phases that
  are not in these dumps.

Answer with JSON only, no prose around it:
{"befunde": [{"kategorie": "a"|"b"|"c"|"d", "datei": "<dump name without
.txt>", "zeile": <int>, "zitat": "<verbatim>", "regel": "<rule or the other
place>", "vorschlag": "<what to change>"}]}
"""

_HINWEIS_RETRY = (
    "Your quote did not appear at the line you named. These findings are "
    "dropped unless you quote the dump verbatim. Here they are again -- give "
    "the same findings with the exact wording from the numbered lines, or "
    "leave them out:\n"
)


def nummeriere(text: str) -> str:
    """1-basierte Zeilennummern vor jede Zeile -- ``N| <zeile>``.

    Dieselbe Zaehlung wie ``pruefe_prompt_dumps.inhaltszeilen``: so zeigt ein
    Befund auf dieselbe Zeile, die der mechanische Pruefer meldet."""
    return "\n".join(
        f"{nummer}| {zeile}"
        for nummer, zeile in enumerate(text.splitlines(), start=1)
    )


def zeilenfenster(text: str, zeile: int, fenster: int = FENSTER_ZEILEN) -> str:
    alle = text.splitlines()
    von = max(0, int(zeile) - 1 - fenster)
    bis = min(len(alle), int(zeile) + fenster)
    return "\n".join(alle[von:bis])


def nutzertext(phase: int, dumps: dict[str, str], regeln: str,
               rubrik: str) -> tuple[str, bool]:
    kopf = [
        f"# UX RULES\n{regeln}",
        f"# UX RUBRIC\n{rubrik}",
        f"# PHASE {phase} -- every prompt the bot sends here",
    ]
    teile = []
    gekappt = False
    rest = ZEICHEN_MAX
    for name in sorted(dumps):
        stueck = f"\n## FILE {name}\n{nummeriere(dumps[name])}\n"
        if len(stueck) > rest:
            gekappt = True
            continue
        rest -= len(stueck)
        teile.append(stueck)
    if gekappt:
        teile.append(
            "\n(NOTE: some dumps of this phase were truncated for length. "
            "Judge only what is above.)\n"
        )
    return "\n".join(kopf + teile), gekappt


def pruefe_befund(befund: dict, dumps: dict[str, str]) -> bool:
    """Steht das Zitat woertlich an der genannten Stelle?

    ``zitat.pruefe`` -- keine zweite Normalisierung. Fehlt die Datei oder die
    Zeile, ist der Befund nicht pruefbar und damit nicht verwendbar."""
    text = dumps.get(str(befund.get("datei") or ""))
    if not text:
        return False
    try:
        zeile = int(befund.get("zeile") or 0)
    except (TypeError, ValueError):
        return False
    if zeile <= 0:
        return False
    wortlaut = str(befund.get("zitat") or "").strip()
    if not wortlaut:
        return False
    return zitat.pruefe(wortlaut, zeilenfenster(text, zeile))


def kappe(befunde: list[dict]) -> list[dict]:
    abc = [b for b in befunde if b.get("kategorie") in ("a", "b", "c")]
    d = [b for b in befunde if b.get("kategorie") == "d"]
    return abc[:KAPPE_ABC] + d[:KAPPE_D]


def lies_phase(klient, phase: int, dumps: dict[str, str], regeln: str,
               rubrik: str) -> tuple[list[dict], list[dict]]:
    """Ein Aufruf, hoechstens ein Retry. Liefert ``(geprueft, unsicher)``."""
    text, _gekappt = nutzertext(phase, dumps, regeln, rubrik)
    antwort = klient.json_objekt(ANWEISUNG, text, art=f"lesung-phase{phase}")
    befunde = list((antwort or {}).get("befunde") or [])
    geprueft = [b for b in befunde if pruefe_befund(b, dumps)]
    offen = [b for b in befunde if b not in geprueft]
    if offen:
        nach = klient.json_objekt(
            ANWEISUNG,
            f"{text}\n\n{_HINWEIS_RETRY}{json.dumps(offen, ensure_ascii=False)}",
            art=f"lesung-phase{phase}-retry",
        )
        zweite = list((nach or {}).get("befunde") or [])
        neu = [b for b in zweite if pruefe_befund(b, dumps)]
        geprueft = geprueft + neu
        # ``unsicher`` ist, was nach dem Retry noch unbelegt ist -- es geht ins
        # Log und nie in den BEFUND. Ein verworfener Befund ist kein
        # schwaecherer Befund, sondern keiner (dieselbe Regel wie bei
        # dramaturgie/beleg.py).
        offen = [b for b in zweite if b not in neu] or offen
    return kappe(geprueft), offen


def _dumps_je_phase(ordner: Path) -> dict[int, dict[str, str]]:
    je_phase: dict[int, dict[str, str]] = {}
    for eintrag in inv.INVENTAR:
        pfad = ordner / f"{eintrag.datei}.txt"
        if not pfad.exists():
            continue
        je_phase.setdefault(eintrag.phase, {})[eintrag.datei] = pfad.read_text(
            encoding="utf-8")
    return je_phase


def main() -> None:
    import argparse

    zerleger = argparse.ArgumentParser(description="Opus-Lesung der Dumps")
    zerleger.add_argument("ordner")
    zerleger.add_argument("--phase", type=int, default=None)
    zerleger.add_argument(
        "--trocken", action="store_true",
        help="nur zaehlen, was gelesen WUERDE -- kein Modellaufruf",
    )
    argumente = zerleger.parse_args()

    ordner = Path(argumente.ordner)
    je_phase = _dumps_je_phase(ordner)
    regeln = REGELN.read_text(encoding="utf-8")
    rubrik = RUBRIK.read_text(encoding="utf-8")
    phasen = ([argumente.phase] if argumente.phase
              else sorted(je_phase))

    if argumente.trocken:
        for phase in phasen:
            text, gekappt = nutzertext(phase, je_phase.get(phase, {}),
                                       regeln, rubrik)
            print(f"phase={phase} dumps={len(je_phase.get(phase, {}))} "
                  f"zeichen={len(text)} gekappt={'ja' if gekappt else 'nein'}")
        return

    from simulation.claude import Claude

    klient = Claude()
    alle: list[dict] = []
    unsicher: list[dict] = []
    try:
        for phase in phasen:
            geprueft, offen = lies_phase(
                klient, phase, je_phase.get(phase, {}), regeln, rubrik)
            for befund in geprueft:
                befund["phase"] = phase
            for befund in offen:
                befund["phase"] = phase
            alle.extend(geprueft)
            unsicher.extend(offen)
            print(f"phase={phase} befunde={len(geprueft)} "
                  f"unsicher={len(offen)}")
    finally:
        klient.schliesse()

    (ordner / "lesung.json").write_text(
        json.dumps(alle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (ordner / "lesung-unsicher.jsonl").write_text(
        "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in unsicher),
        encoding="utf-8")
    print(f"gesamt: {len(alle)} Befunde, {len(unsicher)} unsicher")


if __name__ == "__main__":
    main()
```

- [ ] **Schritt 6: Tests laufen lassen**

Run: `python3.11 -m pytest -q tests/test_prompt_lesung.py`
Expected: `12 passed`.

Haengt `test_lies_phase_prueft_zitate_und_wiederholt_genau_einmal` an
`b not in geprueft` (Dict-Vergleich): das ist bewusst Wert- und nicht
Identitaetsvergleich -- zwei gleiche Dicts gelten als derselbe Befund, und das
ist richtig, ein doppelter Befund ist einer.

- [ ] **Schritt 7: Trockenlauf gegen die alten Dumps -- ohne Modell, ohne Kosten**

Run: `python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-02-padua-p2 --trocken`
Expected: Zeilen der Form `phase=1 dumps=1 zeichen=… gekappt=nein` und
`phase=6 dumps=3 zeichen=… gekappt=nein` (die vier alten Dumps liegen in den
Phasen 1 und 6). Kein Netzaufruf, Exit 0.

- [ ] **Schritt 8: Commit**

```bash
git add docs/prompt-audit/ux-regeln-participatory-bot-ux.md \
        scripts/pruefe_prompts_lesung.py tests/test_prompt_lesung.py
git commit -m "Prompt-Check Padua: UX-Regeln im Repo und die Opus-Lesung mit Zitatwache"
```

---

## Task 9: Der Lauf -- Dumps, Mechanik, Opus-Lesung, BEFUND.md

> **Diese Aufgabe fuehrt der Controller selbst aus, nicht ein Subagent.** Sie
> faehrt einen echten Modellaufruf (sieben, ueber das Abo) und schreibt das
> Artefakt, das die Karte abliefert. Ein Subagent kann hier nicht blocken und
> nachfragen, und genau das ist noetig, wenn der Proxy nicht erreichbar ist.

**Files:**
- Create: `docs/prompt-audit/2026-10-05-padua-voll/` (Dumps, `uebersicht.tsv`,
  `mechanik.md`, `lesung.json`, `lesung-unsicher.jsonl`, `BEFUND.md`)

**Interfaces:** nur Aufrufe der Tasks 1-8, kein neuer Code.

- [ ] **Schritt 1: Die Dumps erzeugen**

Run: `python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-voll`
Expected: eine TSV-Kopfzeile mit genau den Spalten aus `TSV_SPALTEN` und eine
Zeile je Inventareintrag; danach
`ls docs/prompt-audit/2026-10-05-padua-voll/*.txt | wc -l` = Zahl der
Inventareintraege. Bricht es mit `TreiberFehler` ab, wird **der Treiber**
geflickt (Task 6/7, Schritt „bis gruen nacharbeiten") -- nicht der Eintrag
entfernt.

- [ ] **Schritt 2: Die gemessenen Fensterschnitte festhalten**

Run:
```bash
python3.11 - <<'PY'
import os, tempfile
from interview_theater import db
from scripts import fixture_padua_voll as fix
with tempfile.TemporaryDirectory() as tmp:
    pfad = os.path.join(tmp, "m.db")
    os.environ["IT_DB"] = pfad
    conn = db.verbinde(pfad); db.initialisiere(conn)
    fix.baue_alle(conn)
    for phase in fix.PHASEN:
        b = fix.fensterbefund(conn, fix.chat_id_fuer(phase))
        print(f"phase={phase} gesamt={b['nachrichten_gesamt']} "
              f"im_fenster={b['im_fenster']} zeichen={b['zeichen_im_fenster']} "
              f"grund={b['grund']}")
    conn.close()
PY
```
Expected: sieben Zeilen, jede mit `im_fenster < gesamt`, und unter den
`grund`-Werten mindestens einmal `zeichen` und einmal `minuten`. Die Ausgabe
geht woertlich in den BEFUND-Abschnitt „Gemessene Fenstergrenzen".

- [ ] **Schritt 3: Den mechanischen Pruefer fahren**

Run:
```bash
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-voll \
  --basis docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv
echo "exit=$?"
```
Expected: `exit=0`; `mechanik.md` liegt im Auditordner; die vier Dumps
`01`, `02`, `03`, `04` tragen ein `(gegen Basis: +N)` bzw. `-N`, alle anderen
`neu`. **Gemessener Anker fuer den BEFUND:** am 05.10.2026 lieferte das alte
Skript bereits `01-gespraech-phase1: system=28705` gegen die Basiszeile
`26943` -- also rund **+1 762 Zeichen** Drift seit dem 02.10.2026, ohne dass
jemand sie benannt hat. Genau diese Drift ist eine Zeile im BEFUND.

- [ ] **Schritt 4: Die Opus-Lesung trocken pruefen**

Run: `python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-voll --trocken`
Expected: sieben Zeilen `phase=N dumps=… zeichen=… gekappt=…`. Steht irgendwo
`gekappt=ja`, wird das im BEFUND benannt (welche Phase, wie viele Dumps fielen
weg) -- **nicht** stillschweigend hingenommen.

- [ ] **Schritt 5: Die Opus-Lesung wirklich fahren**

Run: `python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/2026-10-05-padua-voll`
Expected: sieben Zeilen `phase=N befunde=… unsicher=…` und eine Schlusszeile
`gesamt: …`; danach liegen `lesung.json` und `lesung-unsicher.jsonl` im
Auditordner.

**Ist der Proxy nicht erreichbar** (`ClaudeFehler: Simulationsmodell nach 4
Versuchen nicht erreichbar`, Vorgabe-URL `http://127.0.0.1:28764/v1/messages`):
**hier wird blockiert und gesagt, dass es blockiert** -- Dumps und Mechanik
sind fertig und werden committet, der BEFUND traegt den Abschnitt
„Ausstehend: die Opus-Lesung" mit dem Fehlerbild und dem Befehl zum Nachholen.
**Keine erfundenen Befunde, keine geschaetzte Lesung.** Dieselbe Haltung wie
bei `docs/begriffsboard-resonanz/BERICHT.md`, Abschnitt „Ausstehend".

- [ ] **Schritt 6: `BEFUND.md` schreiben**

`docs/prompt-audit/2026-10-05-padua-voll/BEFUND.md` mit genau diesen
Abschnitten, in dieser Reihenfolge:

1. **Kopf.** Datum, Karte (`t_1dcf3864`), Branch, Profil (`padua-2026`),
   Umgebung (`szene_anbieter=claude`, `szene_modell=claude-opus-5`,
   `llm_modell=moonshotai/Kimi-K2.6`, `erkenner_modell=google/gemma-4-31B-it`),
   die drei Befehle dieses Laufs und was jeder kostet (Dump 0, Mechanik 0,
   Lesung 0 CHF ueber das Abo).
2. **Inventartabelle** `art -> Datei -> Phase -> weg/Modell -> quelle`, aus
   `uebersicht.tsv` erzeugt:
   ```bash
   python3.11 -c "
   import pathlib
   zeilen = pathlib.Path('docs/prompt-audit/2026-10-05-padua-voll/uebersicht.tsv').read_text(encoding='utf-8').splitlines()
   kopf = zeilen[0].split('\t')
   spalten = ['art','pfad','phase','weg','modell','quelle','system_zeichen','nutzer_zeichen']
   print('| ' + ' | '.join(spalten) + ' |')
   print('|' + '---|' * len(spalten))
   for z in zeilen[1:]:
       d = dict(zip(kopf, z.split('\t')))
       print('| ' + ' | '.join(d.get(s,'') for s in spalten) + ' |')
   "
   ```
   Darunter die Liste aus `prompt_inventar.NICHT_LIVE_IN_PADUA` mit Grund.
3. **Groessen gegen die Basis vom 02.10.2026.** Die vier vergleichbaren Dumps
   mit Delta, alles andere als „neu". Mit dem Satz zur gemessenen Drift von
   rund +1 762 Zeichen bei `01-gespraech-phase1`.
4. **Token-Anteil je Blockgruppe** (die vier `tok_*`-Spalten je
   Gespraechs-Dump, als Tabelle) und ein Satz, welche Gruppe den Prompt
   dominiert.
5. **Gemessene Fenstergrenzen** -- die sieben Zeilen aus Schritt 2, woertlich,
   plus ein Satz: welche Regel in welcher Phase geschnitten hat.
6. **Mechanische Treffer** je Dump, verdichtet aus `mechanik.md`: deutsche
   Reste (Soll 0), UX-Muster mit Zeilennummer, die Frageregel-Zeilen
   nebeneinander, Quotenzaehler, Dubletten.
7. **Opus-Befunde je Phase**, getrennt nach (a) Prompt<->Regel,
   (b) Prompt<->Prompt, (c) tot/veraltet, (d) Kontextstruktur -- je Befund
   Datei, Zeile, Zitat, Regel/Gegenstelle, Vorschlag. Plus die Zahl der als
   `unsicher` verworfenen Befunde je Phase (aus `lesung-unsicher.jsonl`), mit
   dem Satz, dass ein verworfener Befund keiner ist.
8. **Behoben in diesem Lauf** -- wird in Task 10 gefuellt.
9. **Liegt bei t_0b702d1d** -- jeder Befund in `system.md`, in
   `prompts/phasen/1.md`/`2.md`, in `workshop/padua-2026/phasentexte.toml`,
   `workshop/padua-2026/prompts/phasen/2.md` oder
   `interview_theater/sprachen/en/texte.toml`. Mit Datei, Zeile, Zitat.
10. **Fuer Birk, hoechstens fuenf** -- je Punkt: Befund mit Zitat, warum er
    nicht eindeutig ist, **Empfehlung**, und was sie kostet. Reserviert fuer:
    die „Yes, save"/„No, change it again"-Zeremonie (Knopfnamen stehen
    wirklich im Code), jede Aenderung an `erkenner.md` (bezahlter Korpuslauf),
    und alles, wo mehr als eine Loesung sinnvoll ist.
11. **Grenzen dieses Laufs.** Mindestens: die Dumps entstehen gegen eine
    erfundene Fixture, nicht gegen eine echte Gruppe; `weg="gebaut"` bei den
    sieben Szenen-/Prosa-Dumps; kein bezahlter Infomaniak-Lauf; `ZEICHEN_MAX`
    der Lesung ist ungemessen; `ANNAHME:` die Live-Envs setzen
    `IT_SZENE_ANBIETER=claude` (nicht im Code gelesen).

- [ ] **Schritt 7: Commit**

```bash
git add docs/prompt-audit/2026-10-05-padua-voll
git commit -m "Prompt-Check Padua: Lauf vom 05.10.2026 -- Dumps, Mechanik, Opus-Lesung, BEFUND"
```

Der Ordner ist **nicht** gitignored (anders als `korpus/berichte/` und
`docs/dramaturgie-berichte/`): die Dumps enthalten nur erfundenes Material --
die Fixture ist erfunden, das Interview kommt aus `simulation/interviews/set1`
(frei erfunden, im Repository). **Vor dem Commit einmal gegenpruefen:**

```bash
grep -rl "Birk\|@\|http" docs/prompt-audit/2026-10-05-padua-voll/*.txt | head
```
Expected: keine Treffer ausser der Abnahme-Markierung
`<!-- Profil-Anweisung, abgenommen Birk 01.10.2026 -->` (sie steht so schon im
Vorgaengerdump) und etwaigen URLs aus dem Prompt selbst. Ein Treffer, der wie
echte Daten aussieht, stoppt den Commit.

---

## Task 10: Die Fixes in den Phasen 3-7

**Files:**
- Modify: `interview_theater/sprachen/en/prompts/phasen/{3,4,5,6,7}.md` und/oder
  andere EN-Prompt-Dateien unter `interview_theater/sprachen/en/prompts/`
  (**nicht** `erkenner.md`, **nicht** `system.md`, **nicht** `phasen/1.md`,
  **nicht** `phasen/2.md`)
- Modify: `tests/test_phasen_prompts_teil2.py` (Wortlaut-Nagel je Fix)
- Modify: `docs/prompt-audit/2026-10-05-padua-voll/BEFUND.md`

**Interfaces:** keine neuen. Jeder Fix ist eine Textaenderung plus ein Test,
der den neuen Wortlaut nagelt.

**Die Entscheidungsregel, bevor eine Prompt-Datei angefasst wird** (D7) -- in
dieser Reihenfolge, je Befund:

1. **Besitzt die Parallelkarte die Datei?**
   ```bash
   git log --oneline main..padua-workshop/t_0b702d1d-padua-abnahmelauf-phase-1-2-im-browser-s -- <datei>
   git log -3 --oneline -- <datei>
   ```
   Eine Ausgabe in der ersten Zeile heisst: **nicht anfassen**, Befund nach
   BEFUND-Abschnitt 9. **Gemessen** (05.10.2026): die Karte besitzt
   `workshop/padua-2026/phasentexte.toml`,
   `workshop/padua-2026/prompts/phasen/2.md`,
   `interview_theater/sprachen/en/texte.toml`, `simulation/ux_rubrik.md`,
   `simulation/README.md`, `tests/test_sprache_prompts.py`.
2. **Ist es `system.md` oder eine Phase-1/2-Datei?** Dann ebenfalls nicht
   anfassen (Abschnitt 9), auch wenn `git log` nichts zeigt: die Karte besitzt
   diesen Bereich laut Kartentext.
3. **Ist es `erkenner.md`?** Nicht anfassen -- eine Aenderung verlangt den
   bezahlten Korpuslauf mit FP = 0. Befund nach Abschnitt 10 (Birk-Liste).
4. **Ist es eine deutsche Prompt-Datei oder etwas unter
   `workshop/dortmund-2026/`?** Nicht anfassen (Dortmund eingefroren).
5. **Beschreibt der Prompt einen Knopf, den es im Code wirklich gibt?**
   Pruefen:
   ```bash
   grep -rn "<der Wortlaut>" interview_theater/sprachen/en/texte.toml \
        interview_theater/knoepfe/
   ```
   Ein Treffer heisst: **nicht eindeutig** -- nur den Prompt zu aendern
   erzeugte einen Prompt<->Code-Widerspruch. Befund nach Abschnitt 10, mit
   Empfehlung. **Gemessen**: „Yes, save" steht als `_TEXT_SPEICHERN_KNOPF` /
   `TEXT_WEITER_KNOPF`, „No, change it again" als `_TEXT_ANDERS_KNOPF` /
   `TEXT_ANDERS_KNOPF` in `sprachen/en/texte.toml:18-19` und `:120-121`, und
   `phasen/5.md:57,60`, `6.md:95`, `7.md:101` nennen sie.
6. **Alles andere mit genau einer sinnvollen Loesung** wird behoben.

- [ ] **Schritt 1: Die Befundliste sortieren**

Aus `lesung.json` und `mechanik.md` eine Arbeitsliste bauen und jeden Befund
einer der sechs Klassen oben zuordnen. Das Ergebnis geht sofort in den BEFUND
(Abschnitte 8, 9, 10) -- **vor** dem ersten Fix, damit nichts verloren geht,
wenn ein Fix laenger dauert als gedacht.

Run:
```bash
python3.11 -c "
import collections, json, pathlib
befunde = json.loads(pathlib.Path('docs/prompt-audit/2026-10-05-padua-voll/lesung.json').read_text(encoding='utf-8'))
je = collections.Counter((b['phase'], b['kategorie']) for b in befunde)
for (phase, kat), n in sorted(je.items()):
    print(f'phase={phase} kategorie={kat} befunde={n}')
print('gesamt', len(befunde))
"
```
Expected: eine Zeile je (Phase, Kategorie) -- die Zahl, gegen die am Ende
gerechnet wird: behoben + bei t_0b702d1d + Birk-Liste = gesamt.

- [ ] **Schritt 2: Je Fix zuerst den Nagel schreiben**

Muster (das Beispiel ist der Flow-Audit-Befund B3, der laut AGENTS.md in der
englischen Fassung **schon** behoben ist -- ein echter Fix dieser Karte sieht
genauso aus). An `tests/test_phasen_prompts_teil2.py` anhaengen:

```python
def test_phase5_en_nennt_keinen_bestaetigungsknopf_mehr():
    """Fix aus dem Prompt-Check 05.10.2026, Befund <a/b-Nummer>.

    Der alte Wortlaut stand in Zeile <N>; der neue sagt, dass gespeichert wird
    und wie man es zurueckdreht -- die UX-Regel 3 ("save automatically, always
    undoable")."""
    text = (EN / "phasen" / "5.md").read_text(encoding="utf-8")
    assert "<der alte Wortlaut>" not in text
    assert "<der neue Wortlaut>" in text
```

Run: `python3.11 -m pytest -q tests/test_phasen_prompts_teil2.py -k <name>`
Expected: FAIL mit `assert '<der neue Wortlaut>' in text`.

- [ ] **Schritt 3: Den Fix machen und den Nagel gruen bekommen**

Nur die Zeile aendern, auf die der Befund zeigt. Kein Umbau danebenliegender
Abschnitte: ein Prompt-Fix, der mehr anfasst als der Befund nennt, ist beim
naechsten Audit nicht mehr zuzuordnen.

Run: `python3.11 -m pytest -q tests/test_phasen_prompts_teil2.py`
Expected: alle gruen.

- [ ] **Schritt 4: Nach jedem Fix das Profil pruefen**

Run: `python3.11 -m scripts.pruefe_profil padua-2026`
Expected: `padua-2026: in Ordnung`. Ein Fix, der einen Platzhalter zerstoert
(`{{zielgruppe}}` & Co.), faellt genau hier auf -- und das ist der Grund, warum
`scripts/betrieb-start.sh` dieses Skript vor dem Bot ruft.

- [ ] **Schritt 5: Neu dumpen und nachweisen, dass die Zeile weg ist**

Run:
```bash
python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/2026-10-05-padua-voll
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/2026-10-05-padua-voll \
  --basis docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv > /dev/null
grep -c "<der alte Wortlaut>" docs/prompt-audit/2026-10-05-padua-voll/*.txt || true
```
Expected: `0` Treffer fuer jeden behobenen Wortlaut; `mechanik.md` ist neu
geschrieben und zeigt den zugehoerigen UX-Treffer nicht mehr.

**Die Opus-Lesung wird NICHT wiederholt** -- sie kostet nichts, aber sie wuerde
andere Befunde liefern, und der BEFUND waere dann eine Mischung aus zwei
Laeufen. Der Nachweis je Fix ist der Nagel plus die verschwundene Zeile im
Dump.

- [ ] **Schritt 6: BEFUND-Abschnitte 8-10 fuellen**

Abschnitt 8 je Fix: Datei, alte Zeile mit Zitat, neuer Wortlaut, der Testname,
der ihn nagelt. Abschnitt 9 je Befund mit Datei/Zeile/Zitat und dem Satz
„liegt bei t_0b702d1d". Abschnitt 10 mit **hoechstens fuenf** Punkten, je mit
Empfehlung. Die Rechnung aus Schritt 1 muss aufgehen; stimmt sie nicht, fehlt
ein Befund.

- [ ] **Schritt 7: Commit**

```bash
git add interview_theater/sprachen/en/prompts tests/test_phasen_prompts_teil2.py \
        docs/prompt-audit/2026-10-05-padua-voll
git commit -m "Prompt-Check Padua: eindeutige Widersprueche in den Phasen 3-7 behoben"
```

Sind **keine** eindeutigen Fixes uebrig (alles liegt bei t_0b702d1d oder auf der
Birk-Liste), gibt es keinen leeren Commit: dann bleibt Task 10 bei den
Schritten 1 und 6, und der BEFUND sagt in einem Satz, warum Abschnitt 8 leer
ist.

---

## Task 11: Die Doku und der Abnahmeschritt

**Files:**
- Modify: `simulation/README.md` (neuer Abschnitt „Der Prompt-Check")
- Modify: `docs/flow-audit/vorlagen.md` (neuer Abschnitt „Abnahme- und
  END-Schritt: Prompt-Check")
- Modify: `AGENTS.md` (der Skript-Absatz)
- Test: `tests/test_prompt_check_doku.py`

**Interfaces:** keine neuen.

**Warum `docs/flow-audit/vorlagen.md`** (D9): **gemessen** am 05.10.2026 ist
diese Datei heute **nur** eine Liste von Klasse-B-Befunden (50 Zeilen,
Ueberschriften „Flow-Audit -- Klasse-B-Befunde" und „Hinweis zur
Audit-Methode"); ein Abnahme- oder END-Template gibt es im Repository
**nirgends**. Statt eines neuen Dokuments bekommt diese Datei den Abschnitt --
sie ist der Ort, an dem schon heute steht, was ein Audit gefunden hat und wer
es entscheidet. `ANNAHME:` ausserhalb des Repositories gibt es kein weiteres
END-Template, das mitgezogen werden muesste (der Architekt hat keines
gefunden); der BEFUND nennt diese Annahme.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

`tests/test_prompt_check_doku.py`:

```python
"""Die drei Dokustellen des Prompt-Checks nennen die echten Befehle.

Eine Doku, die einen Befehl nennt, den es nicht gibt, ist schlimmer als keine:
sie kostet am Workshoptag die Zeit, die man braucht, um ihr nicht zu glauben.
"""
from pathlib import Path

README = Path("simulation/README.md")
VORLAGEN = Path("docs/flow-audit/vorlagen.md")
AGENTS = Path("AGENTS.md")

BEFEHLE = (
    "scripts.erzeuge_prompts_padua_voll",
    "scripts.pruefe_prompt_dumps",
    "scripts.pruefe_prompts_lesung",
)


def test_readme_hat_den_abschnitt_und_alle_drei_befehle():
    text = README.read_text(encoding="utf-8")
    assert "## Der Prompt-Check" in text
    for befehl in BEFEHLE:
        assert befehl in text, befehl
    assert "0 CHF" in text


def test_vorlagen_haben_den_abnahmeschritt_mit_passregel():
    text = VORLAGEN.read_text(encoding="utf-8")
    assert "## Abnahme- und END-Schritt: Prompt-Check" in text
    for befehl in BEFEHLE:
        assert befehl in text, befehl
    assert "t_0b702d1d" in text or "Eigentuemer" in text
    assert "docs/prompt-audit/" in text


def test_agents_nennt_die_drei_neuen_skripte():
    text = AGENTS.read_text(encoding="utf-8")
    for skript in ("scripts/erzeuge_prompts_padua_voll.py",
                   "scripts/pruefe_prompts_lesung.py",
                   "scripts/prompt_inventar.py"):
        assert skript in text, skript


def test_jeder_genannte_skriptpfad_existiert():
    for datei in (README, VORLAGEN, AGENTS):
        text = datei.read_text(encoding="utf-8")
        for befehl in BEFEHLE:
            if befehl in text:
                pfad = Path(befehl.replace(".", "/") + ".py")
                assert pfad.exists(), (datei.name, pfad)
```

Run: `python3.11 -m pytest -q tests/test_prompt_check_doku.py`
Expected: FAIL, `assert '## Der Prompt-Check' in text`.

- [ ] **Schritt 2: `simulation/README.md` ergaenzen**

Neuer Abschnitt **am Ende** der Datei (nicht in bestehende Abschnitte hinein:
`simulation/README.md` wird von der Parallelkarte t_0b702d1d ebenfalls
geaendert, und ein Anhang kollidiert am wenigsten):

```markdown
## Der Prompt-Check (05.10.2026, Karte t_1dcf3864)

Der Korpus misst einzelne Prompts an einzelnen Faellen, die Simulation den
Zusammenhang. Was beide nicht zeigen: **was im Prompt wirklich steht** -- in
jeder Phase, in jedem Aufruf, System- und Nutzerteil. Dafuer gibt es drei
Befehle. Sie kosten zusammen **0 CHF**: der Dump faengt an der
Transportgrenze ab (kein Modellaufruf), der Pruefer liest Dateien, und die
Lesung laeuft ueber den Abo-Proxy (dieselbe Trennlinie wie bei Richter und
Stimmen der Simulation).

```
python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/<datum>-padua-voll
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/<datum>-padua-voll \
    --basis docs/prompt-audit/2026-10-02-padua-p2/uebersicht.tsv
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/<datum>-padua-voll
```

1. **Dump** (0 CHF, kein Netz): sieben erfundene Gruppen, eine je Phase
   (`scripts/fixture_padua_voll.py`), eine Wegwerf-Datenbank, und ein
   mitschreibendes Double an der Stelle, an der sonst das Modell steht
   (`scripts/mitschnitt.py`). Je Aufruf eine Datei mit Kopfzeile (art, phase,
   weg, modell, quelle), `=== SYSTEM ===` und `=== NUTZER ===`, dazu
   `uebersicht.tsv` mit den Groessen und dem Token-Anteil je Blockgruppe.
   **Welche Aufrufe gedumpt werden, steht in `scripts/prompt_inventar.py`** --
   und `tests/test_modellaufrufe_inventar.py` liest den Quelltext aller
   Modellaufrufe und macht die Suite rot, sobald einer fehlt. Das ist der
   Grund, warum dieser Check nicht veraltet.
2. **Pruefer** (0 CHF, kein Modell): deutsche Reste in englischen Prompts
   (Soll 0), verbotene UX-Muster mit Zeilennummer, die Frageregel-Zeilen
   nebeneinander, Quotenzaehler, Dubletten, Groesse gegen den letzten Stand,
   und der Verlaufsbefund (wie viele Zuege, wer spricht, gehen Bot- und
   Systemzeilen und Transkript-Echos mit). Schreibt `mechanik.md`. **Exit
   immer 0** -- er ist ein Bericht, kein Gate.
3. **Lesung** (0 CHF ueber das Abo, sieben Aufrufe, seriell): Opus liest je
   Phase alle Dumps dieser Phase gegen `docs/prompt-audit/ux-regeln-participatory-bot-ux.md`
   und `simulation/ux_rubrik.md` und meldet Widersprueche mit Zeilennummer und
   woertlichem Zitat. **Jedes Zitat wird mechanisch gegen die genannte Zeile
   geprueft** (`zitat.pruefe`, ein Retry, dann `unsicher`) -- ein Judge
   begruendet jede Note, auch eine falsche. Schreibt `lesung.json` und
   `lesung-unsicher.jsonl`.

Ergebnisse liegen unter `docs/prompt-audit/<datum>-padua-voll/`, der Bericht
heisst `BEFUND.md`. Der letzte Lauf: `docs/prompt-audit/2026-10-05-padua-voll/`.
```

- [ ] **Schritt 3: `docs/flow-audit/vorlagen.md` ergaenzen**

Neuer Abschnitt am Ende:

```markdown
## Abnahme- und END-Schritt: Prompt-Check

Der Prompt-Check ist seit dem 05.10.2026 (Karte t_1dcf3864) ein **fester
Schritt** jeder Abnahme und jedes END -- nicht, weil Prompts huebsch sein
sollen, sondern weil sie heiss nachgeladen werden und sich deshalb zwischen
zwei Abnahmen aendern, ohne dass jemand es sieht. Gemessen: zwischen dem
02.10. und dem 05.10.2026 wuchs der Systemprompt der Phase 1 um rund 1 762
Zeichen, und niemand hatte diese Drift benannt.

Die Befehlsfolge (alle drei kosten 0 CHF, Details in
`simulation/README.md`, Abschnitt „Der Prompt-Check"):

```
python3.11 -m pytest -q -m "not dortmund" tests/test_modellaufrufe_inventar.py
python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/<datum>-padua-voll
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/<datum>-padua-voll \
    --basis <letzter-audit>/uebersicht.tsv
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/<datum>-padua-voll
python3.11 -m scripts.pruefe_profil padua-2026
```

**Die Pass-Regel:** abgenommen ist, wenn **kein Befund der Klassen (a)
Prompt<->Regel und (b) Prompt<->Prompt ohne Eigentuemer dasteht**. Ein Befund
hat einen Eigentuemer, wenn er entweder behoben (mit einem Test, der den
Wortlaut nagelt) oder einer anderen Karte zugeschrieben (z. B. „liegt bei
t_0b702d1d") oder mit Empfehlung auf der Birk-Liste des BEFUND steht. Die
Klassen (c) tot/veraltet und (d) Kontextstruktur sind Arbeitsvorrat und
blockieren keine Abnahme.

**Was NICHT blockiert:** ein Treffer im mechanischen Pruefer allein (er ist ein
Bericht, Exit immer 0) und ein als `unsicher` verworfener Opus-Befund (ein
verworfener Befund ist keiner).

**Was sehr wohl blockiert:** ein rotes
`tests/test_modellaufrufe_inventar.py` -- dann gibt es einen Modellaufruf, den
der Check nicht sieht, und jede Aussage „wir haben alle Prompts geprueft" waere
falsch.
```

- [ ] **Schritt 4: Den AGENTS.md-Skriptabsatz ergaenzen**

Im Absatz, der mit `scripts/loeschen.py erfüllt die Löschzusage` beginnt,
**einen Satz je Skript** anhaengen (die drei Pruefskripte in einem Zug, damit
sie zusammen stehen):

```
`scripts/erzeuge_prompts_padua_voll.py` dumpt JEDEN Modellaufruf, der in Padua
live vorkommt, als Volltext (System- und Nutzerteil, mit dem Modell, das ihn
bedient) gegen eine erfundene Fixture und eine Wegwerf-Datenbank — kein
Modellaufruf, kein Netz; `scripts/prompt_inventar.py` ist die Liste dazu, und
`tests/test_modellaufrufe_inventar.py` macht die Suite rot, sobald ein neuer
Modellaufruf fehlt. `scripts/pruefe_prompts_lesung.py` laesst Opus (Abo, 0 CHF)
diese Dumps je Phase gegen `docs/prompt-audit/ux-regeln-participatory-bot-ux.md`
lesen, mit mechanisch geprueftem Zitat je Befund — **kein Test, laeuft nie
automatisch**; die Befehlsfolge steht in `docs/flow-audit/vorlagen.md`,
Abschnitt „Abnahme- und END-Schritt: Prompt-Check".
```

- [ ] **Schritt 5: Doku-Test gruen bekommen**

Run: `python3.11 -m pytest -q tests/test_prompt_check_doku.py`
Expected: `4 passed`.

- [ ] **Schritt 6: Die volle Suite -- genau einmal, im Hintergrund**

Run:
```bash
python3.11 -m pytest -m "not dortmund" -q > .suite.log 2>&1
tail -5 .suite.log
```
Expected: die Schlusszeile nennt keine Fehler, z. B.
`7650 passed, 4 deselected in …`. **Auf das Ergebnis wird gewartet.** Ein Test,
der **nur** wegen Dortmund-Verhalten rot ist, bekommt
`@pytest.mark.dortmund` (AGENTS.md ganz oben) -- jeder andere rote Test wird
behoben.

`.suite.log` wird **nicht** committet (falls `.gitignore` sie nicht fuehrt:
`rm .suite.log` nach dem Lesen).

- [ ] **Schritt 7: Commit**

```bash
git add simulation/README.md docs/flow-audit/vorlagen.md AGENTS.md \
        tests/test_prompt_check_doku.py
git commit -m "Prompt-Check Padua: Doku und fester Abnahmeschritt"
```

- [ ] **Schritt 8: Abschluss melden, nicht mergen**

Kein Merge, kein Push nach `main` (Global Constraints). Gemeldet wird:
- Zahl der Dumps, Zahl der behobenen Befunde, Zahl der Befunde bei t_0b702d1d,
  die Birk-Liste (hoechstens fuenf, je mit Empfehlung).
- Was **nicht** gelaufen ist, mit Grund -- insbesondere, wenn der Opus-Proxy
  nicht erreichbar war (dann ist `lesung.json` leer und der BEFUND sagt es).
- Der Pfad `docs/prompt-audit/2026-10-05-padua-voll/BEFUND.md`.

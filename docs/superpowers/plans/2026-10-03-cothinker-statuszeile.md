# CoThinker-Tab: animierte Statuszeile (Kanban-Karte t_802caa2c)

Diese Plandatei wurde vom Controller selbst geschrieben (kein Brainstorming
mit dem Menschen -- das war fuer diese Karte bewusst uebersprungen, die
Kanban-Karte IST die Spezifikation). Sie dient nur dazu,
`subagent-driven-development` Aufgaben geben zu koennen.

## Ziel

Im CoThinker-Tab (Phase 4, nur Web-Kanal) erscheint ueber `#buehne-panel`
eine Statuszeile `{zustand, text, seit}`, serverseitig deterministisch aus
vorhandenen DB-Fakten abgeleitet (kein Modellaufruf), mit sekuendlich im
Browser tickender Dauer. Vorlage: CoThinker `stage.py` (nur Inspiration,
nicht kopieren).

## Architektur-Entscheidung (vom Controller getroffen, nicht delegierbar)

**Der Webserver (`web.py`/`web_daten.py`) und der Bot-Prozess
(`bot.py`/`aufnahme.py`/`brainstorm.py`) sind ZWEI GETRENNTE OS-Prozesse**
(siehe AGENTS.md "Weboberflaeche": "Ein einziger Prozess fuer alle Gruppen,
NEBEN den Bots"). `brainstorm._LAEUFT` ist In-Prozess-Speicher des
Bot-Prozesses und vom Webserver-Prozess strukturell NICHT lesbar (anders als
in einem Test, der beide im selben Python-Prozess importiert -- dort faellt
der Unterschied nicht auf, in echtem Betrieb schon).

Deshalb zwei Mechanismen nebeneinander:

1. **`brainstorm.laeuft(chat_id) -> bool`** wird trotzdem gebaut, wortgleich
   zur Kartenbeschreibung (`_LAEUFT` wird `dict[int, str]`,
   chat_id -> ISO-Start) -- fuer Konsistenz innerhalb des Bot-Prozesses und
   weil die Karte es ausdruecklich verlangt.
2. **Zusaetzlich** (das ist die Korrektur, die die Karte nicht explizit
   nennt, aber fuer echten Betrieb notwendig ist): eine neue, additive Spalte
   `arbeitsstand.brainstorm_lauf_seit TEXT` wird vom BOT-Prozess gesetzt
   (`aufnahme._starte_buehnenkarte`, direkt neben
   `brainstorm.versuche_start`/`beende`) und vom WEBSERVER gelesen
   (`web_daten.py`, read-only). Das ist keine neue Infrastruktur im Sinne
   der Karte (kein neuer Poll-Endpunkt, kein Modellaufruf) -- es ist derselbe
   Kommunikationsweg, den die ganze App sonst auch nutzt: Fakten gehen nur
   über die Datenbank von einem Prozess zum anderen (vgl.
   `brainstorm_markierung_id`, `web_strom`-Tabelle fuer den Strom).

   `web_daten.cothinker_status()` liest NUR die DB-Spalte (nie
   `brainstorm.laeuft()` direkt) -- `web_daten.py` bleibt dadurch bei seinem
   dokumentierten Vertrag "liest nur `conn`, kein Projektimport von
   Bot-Prozess-Zustand".

## Zustaende (Prioritaet in dieser Reihenfolge, erster Treffer gewinnt)

1. **`denkt`**: `arbeitsstand.brainstorm_lauf_seit` gesetzt UND nicht aelter
   als `DENKT_TIMEOUT_S` (180s, Sicherheitsnetz falls der Bot abstuerzt,
   ohne die Spalte zu leeren). `seit` = dieser Zeitstempel. Tickt.
2. **`transkribiert`**: die juengste (nicht entfernte) `aufnahme`-Zeile
   dieser Gruppe mit `brainstorm = 1` hat `status IN ('empfangen', 'laeuft')`.
   `seit` = ihr `empfangen_am`. Tickt.
3. **`hoert`**: dieselbe juengste Zeile hat `status = 'fertig'`,
   `schnittgrund != 'ende'` (die Aufnahme ist nicht abgeschlossen) UND ihr
   `empfangen_am` liegt nicht laenger als `HOERT_FRISCH_S` (60s) zurueck.
   `seit` = ihr `empfangen_am`. Tickt.
4. **`schweigt`**: die NEUESTE `buehnenkarte`-Zeile dieser Gruppe hat
   `schweigen = 1`. `seit` = ihr `erstellt_am`. Tickt NICHT (die Karte gibt
   dafuer keinen Dauer-Text vor).
5. **sonst**: kein Status -- die Zeile wird gar nicht gerendert (bevorzugte
   Variante laut Kartentext).

Nur berechnet, wenn `arbeitsstand.phase == 4` (sonst `None`, kein Panel ohne
Phase 4 ohnehin sichtbar).

## Global Constraints (fuer alle Tasks bindend)

- Branch bleibt `wt/t_802caa2c`. Kein Merge, kein Push.
- `IT_LLM_URL`/API-Keys/`.env` nie anfassen oder lesen.
- Kein neuer Modellaufruf. Keine Aenderung an Phasenlogik/Knopfstruktur
  ausser dem fuer die Statuszeile Noetigen.
- Kein neuer Poll-Endpunkt: die Statuszeile wird Teil der HTML-Ausgabe von
  `web._buehne_html(daten)`, die bereits ueber `GET /g/<token>/teil/buehne`
  (Funktion `web_vereint.sende_teil`) UND beim initialen Seitenaufbau
  (`web_daten.gruppe_nach_token` -> `web_vereint.seite`) ausgeliefert wird.
  Die ZAHL der tickenden Sekunden steht NIE im servergerenderten HTML (sonst
  aendert sich der String jeden Poll und `ladeBuehne()`s Diff tauscht den
  ganzen Panel-Block aus) -- nur `data-zustand`/`data-seit` als Attribute,
  die Dauer wird rein clientseitig berechnet und in ein eigenes, leeres
  `<span class="co-dauer">` geschrieben.
- `@keyframes`-Bloecke duerfen NICHT durch `web_vereint.scope_css()` laufen
  (dessen Regex zerlegt `0% { ... }` als falschen verschachtelten Selektor,
  siehe AGENTS.md "`@keyframes` und `@media` nur in `css_rahmen()`" -- das
  gilt analog hier). Die neuen Keyframes kommen als eigene, UNGESCOPTE
  Konstante, roh an `_CSS_VEREINT` angehaengt (das wird schon unscoped
  eingefuegt, siehe `web_vereint.seite()`).
- `prefers-reduced-motion: reduce` schaltet jede neue Animation ab
  (`animation: none !important` reicht, wie bei bestehenden Animationen in
  `web_gestalt.py`).
- Texte: deutsche Konstante ist die Wahrheit (`web.py`, Prefix
  `_TEXT_COTHINKER_*`), englische Fassung in
  `interview_theater/sprachen/en/texte.toml` unter `[web]`, gelesen ueber
  `T._TEXT_COTHINKER_*` (`T = sprache.Texte(__name__)`, existiert in
  `web.py` bereits).
- Commit nach jedem abgeschlossenen Task.
- Volle Suite (`pytest`, ohne das e2e-Verzeichnis zwingend, aber neue
  Unit-/e2e-Tests MUESSEN mitlaufen) muss gruen bleiben.
- `python -m scripts.pruefe_profil dortmund-2026` und
  `python -m scripts.pruefe_profil padua-2026` muessen am Ende "in Ordnung"
  melden.
- PY = `/home/birk/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/bin/python3`

## Task 1: DB-Spalte + Bot-seitiger Schreibpfad + `brainstorm.laeuft()`

**Dateien:** `interview_theater/db.py`, `interview_theater/repo.py`,
`interview_theater/brainstorm.py`, `interview_theater/aufnahme.py`,
`tests/test_brainstorm.py`, `tests/test_repo_brainstorm.py`.

1. `db.py`: In der `CREATE TABLE arbeitsstand`-Definition, direkt nach
   `brainstorm_reaktion_am TEXT,` (siehe Zeile ~471), eine neue Spalte
   ergaenzen:
   ```sql
   -- Wann der aktuell laufende Buehnenkarten-Lauf gestartet ist (ISO,
   -- CoThinker-Statuszeile, 03.10.2026) -- NULL = kein Lauf aktiv. Vom
   -- BOT-Prozess gesetzt (aufnahme._starte_buehnenkarte) und geleert, wenn
   -- der Lauf endet; vom WEBSERVER-Prozess gelesen (web_daten.py), weil
   -- beide Prozesse sich nur ueber die Datenbank verstaendigen koennen --
   -- brainstorm._LAEUFT ist In-Prozess-Speicher des Bots und fuer den
   -- separaten Webserver-Prozess nicht sichtbar.
   brainstorm_lauf_seit TEXT,
   ```
   Additiv, wird automatisch ueber `_migriere_fehlende_spalten` erfasst
   (kein weiterer Code noetig, das Verfahren ist generisch).

2. `repo.py`: neue Funktion, nach `markiere_brainstorm_reaktion` einordnen:
   ```python
   @_gesperrt
   def markiere_buehnenkarten_lauf(
       conn: sqlite3.Connection, chat_id: int, seit: str | None,
   ) -> None:
       """Haelt fest, seit wann ein Buehnenkarten-Lauf dieser Gruppe aktiv
       ist (CoThinker-Statuszeile) -- ``seit=None`` loescht die Markierung,
       wenn der Lauf endet. Eigene Spalte statt Wiederverwendung von
       ``brainstorm_reaktion_am``: die Zeile hier beschreibt einen LAUFENDEN
       Vorgang, nicht eine abgeschlossene Reaktion."""
       conn.execute(
           """
           INSERT INTO arbeitsstand (chat_id, brainstorm_lauf_seit, geaendert_am)
           VALUES (?, ?, ?)
           ON CONFLICT(chat_id) DO UPDATE SET
               brainstorm_lauf_seit = excluded.brainstorm_lauf_seit,
               geaendert_am = excluded.geaendert_am
           """,
           (chat_id, seit, _jetzt()),
       )
       conn.commit()
   ```
   Tests in `tests/test_repo_brainstorm.py` (Muster: siehe bestehende Tests
   in derselben Datei, Fixture `conn`): setzen, lesen (z. B. per
   `conn.execute("SELECT brainstorm_lauf_seit FROM arbeitsstand WHERE
   chat_id = ?", (CHAT,)).fetchone()[0]`), wieder auf `None` setzen, und ein
   Test, dass eine andere Gruppe nichts sieht.

3. `brainstorm.py`: `_LAEUFT` von `set[int]` zu `dict[int, str]` aendern
   (chat_id -> ISO-Start-Zeitstempel, `datetime.now(timezone.utc).isoformat()`
   -- `import` von `datetime`/`timezone` ergaenzen). `versuche_start`
   schreibt den Zeitstempel beim Eintragen; `beende` entfernt den Eintrag
   (`_LAEUFT.pop(chat_id, None)` statt `discard`). Neue Funktion:
   ```python
   def laeuft(chat_id: int) -> bool:
       """Oeffentliche Lesefunktion: laeuft fuer diese Gruppe gerade ein
       Buehnenkarten-Versuch (innerhalb DIESES Prozesses)? Siehe
       cothinker-Statuszeile -- im echten Betrieb (Bot und Webserver als
       getrennte Prozesse) ist das NICHT der Kanal, ueber den der Webserver
       das erfaehrt (siehe arbeitsstand.brainstorm_lauf_seit in db.py/repo.py
       fuer den Prozess-uebergreifenden Weg)."""
       with _LAEUFT_LOCK:
           return chat_id in _LAEUFT
   ```
   Pruefe alle Aufrufer von `_LAEUFT`/`versuche_start`/`beende` in
   `brainstorm.py` und `aufnahme.py` (nur `_starte_buehnenkarte` ruft
   `versuche_start`/`beende`, siehe Zeilen ~989/~1021) und passe sie an die
   neue Typisierung an -- es gibt keine direkten `_LAEUFT`-Zugriffe
   ausserhalb von `brainstorm.py` selbst (gegenpruefen mit
   `grep -rn "_LAEUFT" interview_theater/`).

   Tests in `tests/test_brainstorm.py`: `test_versuche_start_lehnt_einen_
   zweiten_lauf_ab` und `test_verschiedene_gruppen_stoeren_sich_nicht`
   bleiben wie sie sind (pruefen nur das True/False-Verhalten). Neue Tests:
   `laeuft()` ist False vor `versuche_start`, True danach, False nach
   `beende`.

4. `aufnahme.py`, Funktion `_starte_buehnenkarte`: direkt nach dem
   erfolgreichen `brainstorm.versuche_start(chat_id)` (vor der Zeile mit
   `markierung_id = ...`) die DB-Markierung setzen:
   ```python
   repo.markiere_buehnenkarten_lauf(conn, chat_id, repo._jetzt())
   ```
   Im `finally`-Block von `_lauf()`, NACH `brainstorm.beende(chat_id)` (oder
   davor, Reihenfolge ist egal, beide muessen in jedem Fall laufen):
   ```python
   repo.markiere_buehnenkarten_lauf(conn, chat_id, None)
   ```
   Kein neuer Test fuer `aufnahme.py` zwingend (die Verkabelung ist trivial
   und wird durch Task 3/4s Integrationstests indirekt mitgeprueft) -- wenn
   es schnell geht, ein Test, der `_starte_buehnenkarte` mit einer
   Attrappen-`klm` aufruft und prueft, dass die Spalte gesetzt und nach
   Threadende wieder NULL ist, ist ein Plus, aber kein Muss (Threads sind
   asynchron -- ggf. mit `threading.Event`/`join`-Attrappe arbeiten wie in
   bestehenden `aufnahme`-Tests, falls es dort ein Muster dafuer gibt; wenn
   nicht, lieber weglassen als instabil machen).

**Nicht tun:** `brainstorm.soll_reagieren` oder die Buehnenkarten-Erzeugung
selbst anfassen -- diese Karte aendert nur, WER WANN erfaehrt, nicht WAS
entschieden wird.

## Task 2: Reine Zustandsableitung + Unit-Tests + Mutant-Test

**Neue Datei:** `interview_theater/cothinker_status.py`
**Neue Testdatei:** `tests/test_cothinker_status.py`

Reine Funktion(en), kein SQL, kein Modellaufruf -- Vorbild im Stil:
`fehlstellen.aus_daten`/`roadmap.aus_daten` (Dicts rein, Dict/Tuple raus,
`datetime` als Parameter statt `datetime.now()` innen, damit die Funktion
ohne Mocking testbar ist).

```python
"""Die CoThinker-Statuszeile (Phase 4, nur Web, 03.10.2026): aus
vorhandenen Fakten abgeleitet, kein Modellaufruf, keine Datenbank -- reine
Funktion wie fehlstellen.aus_daten/roadmap.aus_daten.

Zustaende, erster Treffer gewinnt: denkt > transkribiert > hoert > schweigt
> kein Status. Siehe Plan docs/superpowers/plans/2026-10-03-cothinker-
statuszeile.md fuer die Herleitung der Schwellenwerte."""

from datetime import datetime, timezone

DENKT_TIMEOUT_S = 180
HOERT_FRISCH_S = 60

ZUSTAND_DENKT = "denkt"
ZUSTAND_TRANSKRIBIERT = "transkribiert"
ZUSTAND_HOERT = "hoert"
ZUSTAND_SCHWEIGT = "schweigt"

#: Zustaende, deren Dauer im Browser sekuendlich tickt (siehe web.py:
#: nur diese bekommen die ``data-tickt``-Markierung im HTML).
TICKT = frozenset({ZUSTAND_DENKT, ZUSTAND_TRANSKRIBIERT, ZUSTAND_HOERT})


def _sekunden_her(jetzt: datetime, zeitpunkt: str | None) -> float | None:
    if not zeitpunkt:
        return None
    try:
        wert = datetime.fromisoformat(zeitpunkt)
    except ValueError:
        return None
    if wert.tzinfo is None:
        wert = wert.replace(tzinfo=timezone.utc)
    return (jetzt - wert).total_seconds()


def leite_ab(
    *,
    jetzt: datetime,
    lauf_seit: str | None,
    segment_status: str | None,
    segment_schnittgrund: str | None,
    segment_empfangen_am: str | None,
    neueste_karte_schweigen: bool,
    neueste_karte_seit: str | None,
) -> tuple[str, str] | None:
    """Liefert ``(zustand, seit)`` oder ``None`` (kein Status -- die Zeile
    wird dann gar nicht gerendert). ``segment_*`` beschreibt die JUENGSTE
    nicht entfernte Brainstorm-``aufnahme``-Zeile dieser Gruppe (oder
    durchgehend ``None``, wenn es noch keine gibt)."""
    lauf_alter = _sekunden_her(jetzt, lauf_seit)
    if lauf_seit and lauf_alter is not None and lauf_alter < DENKT_TIMEOUT_S:
        return ZUSTAND_DENKT, lauf_seit

    if segment_status in ("empfangen", "laeuft"):
        return ZUSTAND_TRANSKRIBIERT, segment_empfangen_am

    segment_alter = _sekunden_her(jetzt, segment_empfangen_am)
    if (
        segment_status == "fertig"
        and segment_schnittgrund != "ende"
        and segment_alter is not None
        and segment_alter < HOERT_FRISCH_S
    ):
        return ZUSTAND_HOERT, segment_empfangen_am

    if neueste_karte_schweigen:
        return ZUSTAND_SCHWEIGT, neueste_karte_seit

    return None
```

(Die obige Fassung ist eine Arbeitsvorlage, keine Pflichtkopie -- der
Implementierer darf Namen/Struktur leicht anpassen, solange Verhalten und
Prioritaet exakt den fuenf Faellen oben entsprechen und die Funktion pure
bleibt.)

**Tests** (ein Fall je Zustand + Mutant-Test, siehe
`superpowers:verifying-code-changes` falls hilfreich):

- `test_denkt_wenn_lauf_seit_frisch_ist`
- `test_denkt_faellt_weg_nach_timeout` (lauf_seit aelter als
  `DENKT_TIMEOUT_S` -> kein `denkt`, faellt durch zu den naechsten Pruefungen)
- `test_transkribiert_wenn_segment_noch_nicht_fertig` (status='laeuft' bzw.
  'empfangen', je ein Fall)
- `test_hoert_wenn_segment_fertig_und_frisch`
- `test_hoert_faellt_weg_wenn_schnittgrund_ende_ist` (Abschluss-Segment ist
  kein "noch am Reden")
- `test_hoert_faellt_weg_wenn_zu_alt`
- `test_schweigt_wenn_neueste_karte_schweigen_traegt`
- `test_kein_status_ohne_jeden_hinweis` (alles None/False -> `None`)
- `test_denkt_hat_vorrang_vor_hoert` (beide Bedingungen gleichzeitig erfuellt
  -> `denkt` gewinnt) -- das ist der Prioritaetstest, der am ehesten einen
  Mutanten faengt, der die Reihenfolge der Checks vertauscht.
- **Mutant-Test**: vertausche testweise (nur zur Verifikation, nicht
  committen) z. B. `segment_schnittgrund != "ende"` zu `==` oder
  `segment_alter < HOERT_FRISCH_S` zu `<=`/`>` und bestaetige, dass
  mindestens ein Test rot wird -- dokumentiere das Ergebnis im Abschlussbericht
  (welcher Test hat den Mutanten gefangen), committe aber nur die
  korrekte Fassung.

## Task 3: `web_daten.py` -- Fakten lesen, Status zusammenbauen, in `daten` haengen

**Dateien:** `interview_theater/web_daten.py`,
`tests/test_web_daten.py` (oder neue Datei `tests/test_web_daten_
cothinker_status.py`, je nachdem was uebersichtlicher ist).

Hintergrund (bereits erkundet): `web_daten.gruppe_nach_token(conn, token)`
baut das `daten`-Dict, das SOWOHL beim initialen Seitenaufbau als auch bei
jedem `/g/<token>/teil/buehne`-Poll verwendet wird (`web_vereint.sende_teil`
-> `handler._gruppe(token)` -> genau diese Funktion). Es gibt daher KEINEN
Grund, `web_chatzustand` anzufassen -- `gruppe_nach_token` ist der einzige
Ort, an dem der Wert ankommen muss.

1. Neue Funktion `web_daten.cothinker_status(conn, chat_id, phase) -> dict
   | None`:
   - Liefert sofort `None`, wenn `phase != 4`.
   - Liest die juengste nicht entfernte `aufnahme`-Zeile mit
     `chat_id = ? AND brainstorm = 1 AND entfernt_am IS NULL ORDER BY id DESC
     LIMIT 1` (Spalten `status`, `schnittgrund`, `empfangen_am`) --
     `None`-Werte, wenn es keine gibt.
   - Liest `brainstorm_lauf_seit` aus `arbeitsstand` (wie andere Funktionen
     in dieser Datei: `SELECT ... FROM arbeitsstand WHERE chat_id = ?`,
     fehlende Spalte -> `None`, wie beim Muster mit `sqlite3.OperationalError`
     in `buehnenkarten()` weiter oben in derselben Datei).
   - Liest die NEUESTE `buehnenkarte`-Zeile (`schweigen`, `erstellt_am`),
     `None`, wenn es keine gibt (dasselbe `try/except
     sqlite3.OperationalError`-Muster wie bei `buehnenkarten()`, Zeile
     ~1341, falls die Tabelle in einer alten DB noch fehlt).
   - Ruft `cothinker_status.leite_ab(jetzt=datetime.now(timezone.utc), ...)`
     mit den gelesenen Werten.
   - Liefert bei einem Treffer `{"zustand": zustand, "seit": seit}` (ein
     einfaches Dict, JSON-faehig -- NICHT die rohen `sqlite3.Row`-Objekte),
     sonst `None`.
   - Import von `cothinker_status` lokal in der Funktion ODER am Dateikopf,
     je nachdem wie `web_daten.py` das sonst handhabt (schau nach, ob am
     Dateikopf bereits ein Modulimport-Block existiert und ob lokale
     Importe dort ueblich sind, z. B. `from interview_theater import
     fragen_auswertung as _fragen_auswertung_modul` lokal in
     `gruppe_nach_token` -- folge demselben Stil).

2. In `gruppe_nach_token`, direkt bei der Zeile mit
   `"buehnenkarten": buehnenkarten(conn, chat_id),` (am Ende der
   zurueckgegebenen Dict-Literal, um Zeile ~1330) eine neue Zeile ergaenzen:
   ```python
   "cothinker_status": cothinker_status(
       conn, chat_id, _feld(stand, "phase")
   ),
   ```
   (`_feld` ist die bestehende Hilfsfunktion fuer fehlende Spalten, siehe
   ihre Verwendung an anderen Stellen in dieser Datei, z. B. in
   `web_chatzustand`.) Falls `stand` in `gruppe_nach_token` ein `dict` ODER
   eine `sqlite3.Row` sein kann, pruefe wie andere Stellen im selben
   Funktionskoerper darauf zugreifen (`stand["rahmen"]` wird z. B. schon
   verwendet) und bleib konsistent -- `stand["phase"]` direkt ist ggf.
   einfacher als `_feld`, wenn die Spalte garantiert existiert (pruefe, ob
   `phase` schon zum Grundschema gehoert oder ueber Migration kam).

**Tests**: Fixture-Muster wie `tests/test_repo_brainstorm.py` (echte
In-Memory-/Temp-Datei-DB ueber `db.verbinde`/`db.initialisiere`,
`repo.sichere_gruppe`, dann direkt `repo.*`-Funktionen zum Praeparieren,
danach `web_daten.cothinker_status(conn, chat_id, 4)` aufrufen und das
Ergebnis pruefen). Je ein Test fuer: kein Status ausserhalb Phase 4 (liefert
`None` selbst wenn sonst `denkt` gelten wuerde), `denkt` via
`repo.markiere_buehnenkarten_lauf`, `transkribiert`/`hoert` via
`repo.lege_aufnahme_an(..., brainstorm=True, status=...)`, `schweigt` via
`repo.lege_buehnenkarte_an(..., schweigen=True)`, und `None` ohne jeden
Hinweis. Mindestens ein Test, dass `gruppe_nach_token(...)["cothinker_
status"]` den Schluessel traegt (Integrationscheck fuer die Verkabelung).

## Task 4: Rendering (`web.py`) + Keyframes/Ticking-JS (`web_vereint.py`) + Texte

**Dateien:** `interview_theater/web.py`, `interview_theater/web_vereint.py`,
`interview_theater/sprachen/en/texte.toml`,
`tests/test_web_buehne_html.py` (neu oder passende bestehende Datei suchen,
z. B. gibt es schon Tests fuer `_buehne_html`? Pruefen mit
`grep -rln "_buehne_html" tests/`), `tests/test_sprache_texte.py`
(bestehende Pruefung, dass jede deutsche `_TEXT_*`-Konstante eine englische
Entsprechung hat -- falls diese Datei automatisch alle `_TEXT_*`-Konstanten
in `web.py` erfasst, braucht es dort ggf. keine manuelle Ergaenzung, aber
UNBEDINGT laufen lassen und pruefen).

1. In `web.py`, direkt bei den bestehenden `_TEXT_BUEHNE_*`-Konstanten
   (Zeilen ~933-939), neue Konstanten (deutsche Wahrheit):
   ```python
   _TEXT_COTHINKER_HOERT = "hört zu"
   _TEXT_COTHINKER_TRANSKRIBIERT = "verschriftlicht"
   _TEXT_COTHINKER_DENKT = "denkt nach"
   _TEXT_COTHINKER_SCHWEIGT = "zugehört, gerade nichts hinzuzufügen"
   ```
   Mapping Zustand -> Text (orientiere dich an `cothinker_status.ZUSTAND_*`
   aus Task 2, importiere das Modul):
   ```python
   _COTHINKER_TEXTE = {
       cothinker_status.ZUSTAND_DENKT: _TEXT_COTHINKER_DENKT,
       cothinker_status.ZUSTAND_TRANSKRIBIERT: _TEXT_COTHINKER_TRANSKRIBIERT,
       cothinker_status.ZUSTAND_HOERT: _TEXT_COTHINKER_HOERT,
       cothinker_status.ZUSTAND_SCHWEIGT: _TEXT_COTHINKER_SCHWEIGT,
   }
   ```

2. Neue Funktion `_cothinker_status_html(status: dict | None) -> str`
   (leerer String, wenn `status` falsy):
   ```python
   def _cothinker_status_html(status: dict | None) -> str:
       if not status:
           return ""
       zustand = status["zustand"]
       tickt = zustand in cothinker_status.TICKT
       text = _t(_COTHINKER_TEXTE.get(zustand, zustand))
       return (
           f'<div id="cothinker-status" class="co-status co-{html.escape(zustand)}" '
           f'data-zustand="{html.escape(zustand)}" '
           f'data-seit="{html.escape(status["seit"] or "")}">'
           f'<span class="co-icon" aria-hidden="true"></span>'
           f'<span class="co-text">{text}</span>'
           f'<span class="co-dauer"{" data-tickt=\"1\"" if tickt else ""}></span>'
           f'</div>'
       )
   ```
   (Pass genau auf bestehende Hilfsfunktionen an -- `html.escape` und `_t`
   werden in `web.py` bereits verwendet, siehe `_stueckkarte_streifen_html`
   weiter oben in derselben Datei. Attribut-Quoting innerhalb einer
   f-String-Zeile mit `\"` vorsichtig pruefen/testen, ggf. einfacher mit
   `.format()` oder separatem String-Aufbau loesen, wenn das sauberer ist.)

3. In `_buehne_html(daten)` (Zeile ~2767) die Statuszeile VOR dem
   bestehenden `return` einfuegen, als Geschwister-Element VOR
   `#buehne-panel` (nicht darin, die Karte verlangt "eine Zeile UEBER dem
   #buehne-panel"):
   ```python
   status_html = _cothinker_status_html(daten.get("cothinker_status"))
   ...
   return f'{status_html}<div id="buehne-panel">{streifen}{"".join(teile)}</div>'
   ```

4. CSS in `_CSS_BUEHNE` (Zeile ~674, geht durch `scope_css`, KEINE
   `@keyframes` hier): Layout/Farben je Zustand, z. B.
   ```css
   #cothinker-status { display: flex; align-items: center; gap: .5rem;
                        margin: 0 0 .6rem; padding: .4rem .6rem;
                        border-radius: .5rem; background: #f2ede1;
                        font-size: .9rem; }
   #cothinker-status .co-icon { width: .6rem; height: .6rem;
                                 border-radius: 50%; background: currentColor;
                                 flex: 0 0 auto; }
   #cothinker-status.co-hoert, #cothinker-status.co-transkribiert { color: #2f6f4f; }
   #cothinker-status.co-denkt { color: #8a5a00; }
   #cothinker-status.co-schweigt { color: #777; opacity: .75; }
   #cothinker-status .co-icon.co-hoert-icon { animation: co-atmen 1.8s ease-in-out infinite; }
   #cothinker-status.co-hoert .co-icon { animation: co-atmen 1.8s ease-in-out infinite; }
   #cothinker-status.co-denkt .co-icon { animation: co-punkte 1.2s steps(3, end) infinite; }
   ```
   (Werte/Selektoren sind eine Vorlage, kein Pflichtzeichensatz -- der
   Implementierer darf sie sinnvoll anpassen, solange: kein `@keyframes`
   hier, `prefers-reduced-motion` greift, und die Klassen zu den unten
   definierten Keyframe-Namen passen.)

5. Neue, UNGESCOPTE CSS-Konstante (z. B. direkt unter `_CSS_BUEHNE` in
   `web.py`, oder falls das uebersichtlicher ist, in `web_vereint.py` neben
   `_CSS_VEREINT` -- Implementierer entscheidet, Hauptsache sie wird NIE
   durch `scope_css()` geschickt):
   ```python
   _CSS_COTHINKER_KEYFRAMES = """
   @keyframes co-atmen { 0%, 100% { opacity: .4; transform: scale(.85); }
                          50% { opacity: 1; transform: scale(1); } }
   @keyframes co-punkte { 0% { opacity: .25; } 50% { opacity: 1; }
                           100% { opacity: .25; } }
   @media (prefers-reduced-motion: reduce) {
     #cothinker-status .co-icon { animation: none !important; }
   }
   """
   ```
   In `web_vereint.seite()` dort einfuegen, wo `_CSS_VEREINT` roh (ohne
   `scope_css`) in das Gesamt-CSS eingeht (Zeile ~1300) -- direkt danach
   anhaengen, UNSCOPED:
   ```python
   _CSS_VEREINT
   + web.CSS_COTHINKER_KEYFRAMES  # Name ggf. anpassen, oeffentlich machen
   + scope_css(web._CSS_GRUPPE, ".panel-stand")
   ...
   ```
   Nur einfuegen, wenn Phase 4 ueberhaupt erreichbar ist, ODER immer
   (unschaedlich, falls das Panel nie sichtbar wird) -- schau dir an, wie
   `_CSS_BUEHNE` selbst bedingt/unbedingt eingebunden wird (Zeile ~1303,
   scheint IMMER eingebunden zu werden, nicht nur bei `phase4`) und bleib
   konsistent.

6. Ticking-JS in `_VEREINT_JS` (`web_vereint.py`): EIN globaler
   `setInterval(..., 1000)`, der bei jedem Tick alle Elemente mit
   `[data-tickt="1"]` sucht (`document.querySelectorAll`), vom
   ELTERNELEMENT (`#cothinker-status`, via `.closest('#cothinker-status')`
   oder `.parentElement`) `data-seit` liest, die Differenz zu `Date.now()`
   in Sekunden berechnet, als `M:SS` formatiert (Vorlage `mmss()` aus
   `stage.py`, NUR als Formel-Inspiration, nicht kopieren -- `Math.floor`,
   Minuten/Sekunden mit `padStart(2, '0')`), und `textContent = ' · ' +
   formatiert` setzt. Lies `data-seit` als ISO-String, `new Date(dataSeit).
   getTime()`. Elemente ohne `#cothinker-status` im DOM (Panel gerade nicht
   gerendert) werden von `querySelectorAll` einfach nicht gefunden -- kein
   Fehlerfall, kein Try/Catch noetig. Platziere den `setInterval`-Aufruf
   einmal am Ende der IIFE in `_VEREINT_JS`, neben den bestehenden
   `setInterval`-Aufrufen (`ladeBuehne` etc., Zeile ~1042) -- NICHT jedes Mal
   neu registrieren bei jedem `ladeBuehne()`-Lauf (globaler Intervall reicht,
   er sucht bei jedem Tick frisch im DOM).

7. Englische Texte in `interview_theater/sprachen/en/texte.toml` unter
   `[web]` ergaenzen (schau dir das bestehende Format fuer
   `_TEXT_BUEHNE_HOERT_ZU` o.ae. dort an und folge demselben
   Schluessel-Schema -- Konstantenname als TOML-Schluessel):
   ```toml
   _TEXT_COTHINKER_HOERT = "listening"
   _TEXT_COTHINKER_TRANSKRIBIERT = "transcribing"
   _TEXT_COTHINKER_DENKT = "thinking it over"
   _TEXT_COTHINKER_SCHWEIGT = "listened, nothing to add right now"
   ```

**Tests**:
- `_cothinker_status_html(None)` == `""`.
- `_cothinker_status_html({"zustand": "denkt", "seit": "..."})` enthaelt
  `id="cothinker-status"`, `class="co-status co-denkt"`,
  `data-zustand="denkt"`, `data-seit="..."`, den deutschen Text, und
  `data-tickt="1"` (weil `denkt` in `TICKT` ist).
- `_cothinker_status_html({"zustand": "schweigt", "seit": "..."})` enthaelt
  KEIN `data-tickt="1"`.
- `_buehne_html(daten)` mit `daten["cothinker_status"]` gesetzt enthaelt die
  Statuszeile VOR `id="buehne-panel"` (String-Index-Vergleich oder Regex);
  ohne den Schluessel (oder mit `None`) bleibt die Ausgabe wie vorher (Test
  gegen eine bestehende Baseline, falls es schon einen Snapshot-Test fuer
  `_buehne_html` gibt -- sonst einen String-Vergleich schreiben, der
  `cothinker-status` NICHT enthaelt).
- `tests/test_sprache_texte.py` (oder wie die Datei heisst, die prueft, dass
  jede `_TEXT_*`-Konstante eine englische Entsprechung hat) muss weiter
  gruen sein -- das ist der Beleg, dass Schritt 7 vollstaendig war.

## Task 5: e2e-Nachweis + Screenshot + Abschlusspruefung

**Ziel:** zeigen, dass die Statuszeile im CoThinker-Tab sichtbar ist und
zwischen Zustaenden wechselt -- UND die volle Suite + beide Profile gruen
bestaetigen.

**Entscheidung ueber den e2e-Weg** (vom Controller vorgegeben, nicht vom
Implementierer neu zu verhandeln): ein echter Playwright-Browserlauf mit
einem echten Bot-Thread (wie `tests/e2e/test_web_chat_e2e.py`) waere fuer
eine reine Statuszeile unverhaeltnismaessig aufwendig (Fake-Mikrofon, VAD,
echte Segmentuebertragung) und sprengt den 2h-Deckel. Stattdessen:

1. Ein Test `tests/test_web_vereint_cothinker_status.py` (oder passender
   Name), der OHNE Browser arbeitet: praeparierte DB (wie Task 3s Tests),
   `web_daten.gruppe_nach_token(conn, token)` aufrufen, das Ergebnis durch
   `web._buehne_html(daten)` UND/ODER `web_vereint.seite(...)` schicken
   (schau nach der Signatur von `seite()`, was sie minimal braucht) und
   pruefen, dass sich die gerenderte HTML-Ausgabe zwischen drei
   praeparierten DB-Zustaenden (hoert -> denkt -> schweigt) unterscheidet,
   insbesondere dass `data-zustand="..."` jeweils den erwarteten Wert
   traegt. Das ist der im Kartentext ausdruecklich erlaubte Ersatz fuer
   einen echten Browserlauf ("ein e2e-Test mit gemocktem/gestelltem
   Server-Zustand ... ausreichend").
   Dokumentiere diese Entscheidung als Docstring-Kopf der Testdatei (ein
   Satz: warum kein echter Playwright-Lauf, Verweis auf diese Plandatei).

2. **Versuche zusaetzlich** einen Screenshot zu erzeugen, nach dem Muster
   von `docs/web-chat/handy-2026-09-30.png`
   (`IT_SCHUSS_AKTUALISIEREN=1`-Muster, siehe `tests/e2e/test_web_chat_e2e.py`
   Zeile ~83/524 fuer das genaue Vorgehen). Pruefe ZUERST, ob Playwright im
   Sandbox-Umfeld ueberhaupt nutzbar ist:
   ```
   $PY -c "import playwright.sync_api; print('ok')"
   ```
   Falls das scheitert ODER Chromium nicht installiert ist (haeufiger
   Sandbox-Fall), **nicht erzwingen** -- stattdessen im Abschlussbericht
   EHRLICH vermerken: "Screenshot nicht erzeugt, Grund: <...>". Falls es
   funktioniert: eine minimal praeparierte Gruppe im Zustand "denkt" oder
   "hoert" anzeigen, Screenshot 390x844 nach
   `docs/web-cothinker-status-2026-10-03.png` schreiben (NUR mit
   `IT_SCHUSS_AKTUALISIEREN=1`, sonst nur pruefen/ueberspringen, exakt wie
   im bestehenden Testmuster).

3. **Abschlusspruefung, im Vordergrund, zitiert im Bericht:**
   ```
   $PY -m pytest -q
   $PY -m scripts.pruefe_profil dortmund-2026
   $PY -m scripts.pruefe_profil padua-2026
   ```
   Alle drei muessen "in Ordnung"/gruen sein, BEVOR der Task als fertig
   gemeldet wird. Bei einem roten Testlauf: Ursache beheben, nicht
   uebergehen.

**Nicht tun:** keine neue Playwright-Infrastruktur bauen, keinen Bot-Thread
fuer diesen Test starten, keine Aenderung an bestehenden e2e-Dateien ausser
ggf. einer neuen, eigenstaendigen Datei.

## Reihenfolge

Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 (sequentiell, jede Aufgabe
baut auf der vorigen auf: Task 3 braucht `cothinker_status.leite_ab` aus
Task 2 UND `repo.markiere_buehnenkarten_lauf`/die neue Spalte aus Task 1;
Task 4 braucht `daten["cothinker_status"]` aus Task 3; Task 5 braucht alles
vorige).

## Aufwand-Deckel

~2h Gesamtbudget fuer die Karte. Wird es nicht fertig: letzten
abgeschlossenen und reviewten Task committen lassen, im Abschlussbericht
exakt sagen, welcher Task fehlt und warum.

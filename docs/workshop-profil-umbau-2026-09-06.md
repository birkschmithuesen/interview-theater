# Der Workshop-Profil-Umbau — was gebaut ist, was fehlt, wie man ein Profil anlegt

**Datum:** 06.09.2026 · **Branch:** `feat/workshop-profil`
**Grundlage:** [`workshop-profil-analyse-2026-09-06.md`](workshop-profil-analyse-2026-09-06.md)
(1217 gemessene Fundstellen, acht Kategorien, Teil E mit den entschiedenen
Empfehlungen)

Alles Workshop-Individuelle liegt in `workshop/<name>/` und wird über
`IT_WORKSHOP` je Prozess eingehängt — **und Dortmund ist bitgleich
geblieben**, mit und ohne Variable.

---

## 1. Der Beweis zuerst

Das Abnahmekriterium war nicht „es sieht gut aus", sondern: nach dem Umbau
erzeugen `IT_WORKSHOP=dortmund-2026` **und** „gar keine Variable gesetzt"
exakt dieselben Prompts wie vorher. Gemessen am 06.09.2026 auf dem fertigen
Stand:

```
1. Prompts OHNE IT_WORKSHOP gegen MIT IT_WORKSHOP=dortmund-2026
   ohne Variable : 114 Abschnitte, sha256 eb8dfd3f6d00…
   dortmund-2026 : 114 Abschnitte, sha256 eb8dfd3f6d00…
   -> IDENTISCH

2. Beide gegen den Massstab von VOR dem Umbau
   ohne Variable : 0 verschwunden, 0 abweichend
   dortmund-2026 : 0 verschwunden, 0 abweichend
```

Die 114 Abschnitte sind jede Prompt-Datei, jede zusammengesetzte
Systemanweisung (je Phase, je Form, je Stil, je Szenenzahl), die Formenliste
in beiden Modulen, die Phasen mit Namen und Stichwörtern, die sieben
Einleitungen einzeln, die Leitfaden-Bausteine und die Auftrags-Anweisungen
aus `knoepfe.py`.

**Der Massstab** ist `docs/prompt-audit/schnappschuss-vor-profilumbau.txt` —
je Abschnitt ein SHA-256 mit Länge, erzeugt mit
`scripts/prompt_schnappschuss.py` **vor** dem ersten Umbauschritt.
`tests/test_profil_bitgleich.py` vergleicht ihn bei jedem Testlauf, in beiden
Richtungen. Neue Abschnitte dürfen dazukommen (eine zusätzliche Prompt-Datei
ist eine gewöhnliche Repo-Änderung); ein verschwundener oder veränderter
Abschnitt ist immer ein Befund.

### Warum nicht direkt gegen die 21 Dumps

Die Analyse (D.3) nennt `docs/prompt-audit/2026-09-06/` den fertigen
Beweisapparat. Er taugt dafür nur zur Hälfte, und das ist gemessen:

- `scripts/erzeuge_prompts.py` braucht eine **Kopie der Betriebsdatenbank**
  (`IT_DB`). Die liegt nicht im Arbeitsbaum und darf da auch nicht liegen.
  Der Nutzertext-Teil jedes Dumps hängt an echten Interviews.
- Der **SYSTEM-Teil** dagegen ist rein aus Dateien und Konstanten gebaut —
  und genau dort, und nur dort, wirkt ein Profil.
- Von den Dumps, deren SYSTEM-Teil sich ohne Datenbank nachbauen lässt (15),
  stimmten am 06.09.2026 **sechs** noch mit dem Code überein: `04-erkenner`,
  `06-verdichter`, `07-journal`, `08-sprachprofil`, `09-kernzitate`,
  `10-schaerfung`. Die übrigen neun waren **schon vor dem ersten Umbauschritt
  überholt** — die Dumps stammen von `main @ f908b68`, und seither hat der
  Feinschliff-Umbau (Phase 8 → 7, Stil-Block, Prosa-Fassung) den
  Gesprächs-, Szenenfolge- und Szenen-Prompt bewegt. Nachgemessen auf dem
  unveränderten Ausgangsstand.

Die sechs noch gültigen prüft `tests/test_profil_bitgleich.py` mit — mit und
ohne Variable. Die neun veralteten weichen **mit und ohne Variable gleich**
ab, also nicht durch das Profil.

**Falle aus D.3, umgangen:** `erzeuge_prompts._entschaerfe()` läuft im Dump
zwischen Prompt und Datei. Der Vergleich hier findet auf der Stufe *vor*
`_entschaerfe` statt und betrifft nur den SYSTEM-Teil, in dem
`_entschaerfe` nichts zu tun hat (dort steht kein Transkript und kein
Belegzitat). Deshalb rauscht der Diff nicht.

---

## 2. Wo der Code jetzt abweicht von dem, was die Analyse beschreibt

Die Analyse ist vom Morgen des 06.09.2026, `main` hat sich seither bewegt.
Was im Code steht, gilt:

| Analyse sagt | Der Code sagt |
|---|---|
| „acht Phasen" (A.5, B.2, C) | **sieben**: 1 Begriffe · 2 Fragen · 3 Interviews · 4 Setting, Figuren & Geschichte · 5 Schaerfung · 6 Szenen als Geschichte · 7 Feinschliff |
| `prompts/phasen/1..8.md` | `1.md` … `7.md` |
| `prompts/formen/` = fünf Dateien | **sechs**: dazu `prosa.md`, die Fassung der Phase 6. Sie steht bewusst nicht in `FORMEN` — die Gruppe wählt sie nie, der Code setzt sie |
| `szene.py` 229–237 `FORM_STICHWOERTER` | steht dort, aber die Formenliste ist inzwischen auch in `prompts/stile/` gespiegelt (drei Stile, eigener Block) |
| A.2: „Bushaltestelle, Kiosk, Schulhof" als Ortsliste in `system.md` 32–37 | die Positivliste ist längst ersetzt durch „altersgerechte, lebensnahe Orte … **keine Beispielorte aus dieser Anweisung**". Die Beispielorte stehen nur noch als Beispiele *im Fließtext* — sechs Stellen, nicht dreißig |
| A.5: Rahmenblock „6× dupliziert" | **5×**, in drei verschiedenen Fassungen (lang: `system.md` = `szene.md`; kurz: `phasen/4.md` = `phasen/6.md`; knapp: `phasen/5.md`) |
| A.1: „`phasentexte.py` 55–58, alle 8 Einleitungen" | sieben Einleitungen, dazu eine Ersatzfassung für die letzte Phase |

**Abweichung vom Format:** die Analyse schlägt `profil.yaml` vor. PyYAML ist
keine Abhängigkeit dieses Projekts, und eine neue Abhängigkeit für eine
Konfigurationsdatei ist der falsche Preis. Es ist **TOML** geworden —
`tomllib` steht seit Python 3.11 in der Standardbibliothek, und das Projekt
verlangt ohnehin 3.11. Ohne Python lesen und ändern lässt sich TOML genauso;
mehrzeilige Texte (`"""…"""` mit `\` am Zeilenende) schreiben sich darin
sogar geradliniger als in YAML-Blockskalaren.

---

## 3. Was gebaut ist

### 3.1 Der Lader — `interview_theater/workshop.py`

Liest `IT_WORKSHOP`, lädt `workshop/<name>/profil.toml` (plus `formen.toml`,
`phasen.toml`, `phasentexte.toml`), prüft Pflichtfelder und liefert ein
eingefrorenes Objekt (`MappingProxyType`, Listen als Tupel). Ohne Variable
gilt das **eingebaute Vorgabeprofil** `VORGABE_WERTE` / `VORGABE_FORMEN` /
`VORGABE_PHASEN` / `VORGABE_PHASENTEXTE` mit exakt den Werten, die vor dem
Umbau im Code standen.

Fehlt ein Profil oder ist es kaputt, wirft der Lader `ProfilFehler` mit einer
Meldung, die sagt, was zu tun ist. `bot.main` ruft ihn **als Erstes** auf —
bevor eine Datenbank geöffnet und ein Long-Poll begonnen wird.

Ein Profil wird je Prozess **einmal** gelesen. Anders als die Prompts ist es
kein Hot-Reload-Kandidat: eine halb gespeicherte `profil.toml` mitten im
Workshop wäre genau der Halbstart, den der Lader verhindern soll.

### 3.2 Der Einhängepunkt — `interview_theater/anweisungen.py`

`anweisungen` ist die einzige Stelle, an der Prompt-Text entsteht, deshalb
hängt das Profil hier ein und nirgends sonst. Drei Zugänge:

- **Platzhalter** (der Normalfall). `{{zielgruppe}}`, `{{rahmen}}`,
  `{{formen_liste}}` werden aus dem aktiven Profil gefüllt. Ein Text ohne
  `{{` geht unverändert zurück.
- **Dateiersatz** (erlaubt, nicht der Normalfall). Eine gleichnamige Datei
  in `workshop/<name>/prompts/` gewinnt gegen die Repo-Datei.
- **Profil-Anweisung.** `workshop/<name>/prompts/anweisung.md` hängt in
  `system()` zwischen Phasenanweisung und Regie-Zettel.

Reihenfolge im Gesprächs-Prompt:

```
Basis (prompts/system.md)
  → Phase (prompts/phasen/N.md)
    → PROFIL (workshop/<name>/prompts/anweisung.md)
      → zusatz.md            (Regie-Zettel, alle Bots)
        → zusatz.<bot>.md    (Regie-Zettel, ein Bot)
```

Der Regie-Zettel bleibt hinten, weil das Ende des Prompts am schwersten wiegt
(SPEC § 6.1): eine spontane Regieanweisung soll Basis, Phase **und** Profil
überstimmen können.

**Der Zwischenspeicher trägt das Profil im Schlüssel** — `(Profilname,
Herkunft, Prompt-Name)` statt nur des Namens (D.5 der Analyse). Solange ein
Prozess ein Profil hat, fällt das alte Verhalten nicht auf; sobald zwei
Profile in **einem** Prozess laufen — der Web-Dienst läuft einmal für alle
Gruppen — lieferte der Cache den Text des falschen Workshops.

### 3.3 Was aus dem Code ins Profil gewandert ist

| Was | Vorher | Jetzt |
|---|---|---|
| Rahmenblock, 3 Fassungen, 5 Vorkommen | in `system.md`, `szene.md`, `phasen/4,5,6.md` ausgeschrieben | `prompts/rahmen*.md`, eingesetzt als `{{rahmen}}`, `{{rahmen_kurz}}`, `{{rahmen_knapp}}` |
| Zielgruppe und Träger | sechsmal wortgleich im Prompt | `profil.toml → zielgruppe`, im langen Rahmenblock als Platzhalter |
| Beispielorte, 6 Vorkommen | `Bushaltestelle`, `Schulhof`, `Kiosk`, `Bahnhof` im Prompt | `profil.toml → orte.beispiele`, als `{{ort_beispiel_1..4}}` |
| Projektbeschreibung | `phasen/2.md` und `knoepfe.ANWEISUNG_EROEFFNUNG` | `prompts/projekt.md` (`{{projekt}}`) und `profil.toml → projekt.kurzbeschreibung` (`{{projekt_kurz}}`) |
| Formen-Katalog | `szene.FORMEN`, `web_schreiben.FORMEN`, `szene.FORM_STICHWOERTER`, `szenenfolge.FORM_VORGABE`, 4× im Prompt | `formen.toml`; Code liest `workshop.formen()` |
| Phasen | `phasen.PHASEN/STICHWOERTER/MEHRDEUTIG/MELDUNG/ERSTE` | `phasen.toml` |
| Phasentexte | `phasentexte.EINLEITUNGEN` (7 Stück) | `phasentexte.toml` |

Die alten Namen (`szene.FORMEN`, `phasen.PHASEN`, …) gibt es weiter: die
Module beantworten sie über ein Modul-`__getattr__` (PEP 562) bei **jedem**
Zugriff frisch aus dem aktiven Profil. Die rund zwanzig Leser im Code und in
den Tests lesen unverändert weiter, und zwei Profile in einem Prozess
bekommen nicht dieselbe Liste.

### 3.4 Die Prüfung — `scripts/pruefe_profil.py`

Läuft in `scripts/betrieb-start.sh` **vor** dem Bot und bricht den Start mit
Rückgabewert 3 ab, wenn etwas nicht stimmt. Ohne Datenbank, ohne Telegram,
ohne Netz. Geprüft wird: lädt das Profil, hat jede Form einen Regelblock,
jede Phase eine Anweisung und eine Einleitung, löst sich jeder Platzhalter
auf (in jeder Prompt-Datei des Repos, jeder des Profils und in den
Prompt-Konstanten aus `szenenfolge.py` und `knoepfe.py`), passt das Zahlwort
zur Zahl der Formen, nennt der Rahmenblock die Zielgruppe aus `profil.toml`,
und — nur bei eigenem Korpus — die Mindestzahlen aus `test_korpus.py`.

Unterschieden wird zwischen **FEHLER** (der Bot startet falsch) und
**Hinweis** (das sollte sich jemand ansehen). Nur ein Fehler bricht ab.

### 3.5 Die Tests, zweistufig

- **generisch** (`tests/test_rahmen.py`, `test_formen_katalog.py`,
  `test_phasen_profil.py`, `test_orte_beispiele.py`,
  `test_anweisungen_profil.py`, `test_workshop.py`,
  `test_pruefe_profil.py`, `test_profile_geruest.py`): der Rahmen ist da und
  nicht leer, Chat und Weboberfläche zeigen dieselbe Formenliste, die
  Phasennummern sind lückenlos, ein anderes Profil ergibt wirklich andere
  Texte. Gilt für **jedes** Profil.
- **profil-spezifisch** (`tests/profile/test_dortmund.py`): die Kopie der
  heutigen Assertions — „15 und 18", der Träger, die Herkules-Zahlen, die
  Negativliste der Choreografin, die fünf Formen, die sieben Phasen, die
  sieben Einleitungen als Literal. Läuft ausdrücklich mit
  `IT_WORKSHOP=dortmund-2026`.

So geht keine Zusicherung verloren (D.1 der Analyse): wer die Literale durch
Profil-Lookups ersetzt, prüft am Ende nur noch, dass zwei Stellen dasselbe
sagen.

---

## 4. Ein neues Profil anlegen — Schritt für Schritt

Für jemanden ohne Python-Kenntnisse. Alles hier sind Textdateien.

**1. Verzeichnis anlegen.** Unter `workshop/` einen Ordner mit dem Namen des
Einsatzortes und dem Jahr: `workshop/padua-2026/`. Der Name darf keine
Schrägstriche enthalten und nicht mit einem Punkt anfangen.

**2. `profil.toml` anlegen.** Am einfachsten: `workshop/padua-2026/profil.toml`
kopieren — sie liegt als ausgefülltes Gerüst schon da und erklärt jedes Feld
in einem Kommentar. Solange die Zeile `geruest = true` darin steht, startet
**kein Bot** mit diesem Profil; das ist die Sicherung dagegen, versehentlich
mit einem halben Profil in einen Workshoptag zu gehen. Wer fertig ist,
streicht die Zeile.

Pflichtfelder sind `beschreibung`, `sprache.code`, `sprache.anrede` und
`zielgruppe.beschreibung`. Alles, was leer bleibt, fällt auf die eingebaute
Vorgabe zurück — also auf Dortmund, auf Deutsch. Das ist beim Anfangen
praktisch und im Betrieb gefährlich, deshalb `geruest`.

**3. Den Rahmenblock schreiben.** Drei Dateien unter
`workshop/<name>/prompts/`:

| Datei | Landet in |
|---|---|
| `rahmen.md` | `system.md` und `szene.md` (lange Fassung) |
| `rahmen-kurz.md` | `phasen/4.md` und `phasen/6.md` |
| `rahmen-knapp.md` | `phasen/5.md` |

Vorlage sind die drei gleichnamigen Dateien unter
`workshop/dortmund-2026/prompts/`. **Neu schreiben, nicht übersetzen** — ein
Prompt in einer anderen Sprache ist ein eigener Text; die Idiomatik steckt
genau in dem, was zählt (Duktus, Anrede, kurze Sätze).

**4. Die Formen festlegen** (nur, wenn sie andere sein sollen).
`formen.toml` anlegen, Vorlage `workshop/padua-2026/formen.toml` — sie zeigt
einen fertigen Eintrag und nennt die drei Regeln. Zu jeder Form gehört ein
Regelblock als `prompts/formen/<name>.md`; ohne eigene Datei gilt die des
Repos.

**5. Phasen und Einleitungen** (nur, wenn sie andere sein sollen).
`phasen.toml` und `phasentexte.toml`, Vorlagen wieder in `padua-2026/`. Der
Ablauf selbst ist meistens nicht workshop-spezifisch — oft reichen andere
Namen und Stichwörter.

**6. Prüfen.**

```
python -m scripts.pruefe_profil <name>
```

Meldet jeden Platzhalter ohne Wert, jede Form ohne Regelblock, jede Phase
ohne Einleitung. Läuft auch vor jedem Bot-Start automatisch.

**7. Einhängen.** In `betrieb/gruppeN.env` die Zeile

```
IT_WORKSHOP=<name>
```

Je Prozess, nicht global. Zwei Workshops können damit parallel auf einem
Server laufen — jede Gruppe hat ohnehin schon eigenen Bot-Token, eigene DB
und eigene Unit-Instanz.

**8. `LIESMICH.md` schreiben.** Ein Absatz, was dieses Profil eigenständig
macht und was noch fehlt. Klingt nach Bürokratie, ist aber das Erste, was
jemand liest, der drei Monate später hineinschaut.

### Am Workshoptag

Die Markdown-Dateien unter `workshop/<name>/prompts/` werden **heiß
nachgeladen**: eine Änderung an `rahmen.md` wirkt beim nächsten
Gesprächszug, ohne Neustart. Die TOML-Dateien nicht — dort braucht es einen
Neustart des Bots.

**Verhaltensänderung gegenüber vorher** (D.10 der Analyse): wer bisher am
Workshoptag `interview_theater/prompts/system.md` bearbeitet hat, um den
Rahmen zu ändern, bearbeitet jetzt `workshop/dortmund-2026/prompts/rahmen.md`.
Der Rahmenblock steht nicht mehr in `system.md`, dort steht `{{rahmen}}`.

---

## 5. Was noch fehlt

**Sprache ist der nächste Schritt** — und er ist bewusst nicht gebaut.

- **`stt.py` liest `sprache.code` noch nicht.** Zeile 129 trägt
  `"language": "de"` hart. Ein Parameter, eine halbe Stunde; er gehört in
  denselben Schritt wie die Chat-Texte, weil er allein nichts nützt.
- **Die rund 111 `_TEXT_*`-Konstanten in `knoepfe.py`** (dazu `befehle.py`,
  `leitfaden.py`) stehen weiter im Code. Die Analyse empfiehlt in E.1
  Frage 5 ausdrücklich, sie **nicht** im ersten Anlauf anzufassen: deutsche
  Knopftexte sind ein Sprachproblem, kein Dortmund-Problem, und für einen
  zweiten deutschsprachigen Workshop irrelevant. Dazu kommt ein praktischer
  Grund vom selben Tag: `knoepfe.py` wurde parallel refaktoriert, und ein
  gleichzeitiger Umbau derselben Konstanten hätte einen Merge-Konflikt
  erzeugt, den niemand auflösen will. Wenn Padua konkret wird: `texte.toml`
  mit Schlüsseln, in einem Rutsch.
- **Die Auftragsmuster in `ablauf.py`** (`_AUFTRAGSFORMEN`) sind deutsche
  Regex.
- **Die Anti-Nachplapper-Wortlisten** in `tests/test_anweisungen.py` und
  `tests/test_prompt_audit.py` (`FREMDE_NAMEN = ("Kessel", "Mira", "Pola",
  "Pal ")`) sind Dortmunder Historie und gehören ins Profil.
- **Korpus und Simulations-Personas je Profil** (E.3 Schritt 10). Der Lader
  und `pruefe_profil.py` kennen `workshop/<name>/korpus/` schon und prüfen
  dort die Mindestzahlen; der *Betriebscode* liest ihn noch nicht — nur der
  Repo-Korpus wird verwendet.
- **Zweite Web-Instanz je Workshop** (E.3 Schritt 11). Der Cache-Schlüssel
  ist umgestellt, die Formenliste kommt aus dem Profil; was fehlt, ist eine
  Web-Instanz mit eigenem Präfix und eigener DB.
- **Betriebsnamen entdortmunden** (E.3 Schritt 8): `einstellungen.py` 19,
  `web.py` 62 und `scripts/web_links.py` 25 tragen weiterhin
  `lab.artesmobiles.art/theatersoap` als Vorgabewert. Billig und
  risikoarm — stand nicht in der Schrittliste dieses Auftrags.
- **Einwilligung/Recht** (E.3 Schritt 9): `szene._TEXT_*USA*` steht
  unverändert im Code.

### Kleinere offene Punkte aus dem Bau

- **Die Zielgruppe steht in den kurzen Rahmenfassungen ausgeschrieben.** In
  `rahmen-kurz.md` und `rahmen-knapp.md` fällt der Zeilenumbruch mitten in
  den Satz („Die Gruppe sind junge / Frauen zwischen 15 und 18 Jahren"), und
  ein eingesetzter Wert wird nicht neu umbrochen — ein Platzhalter hätte den
  Umbruch verschoben und damit die Bitgleichheit gekostet. Dasselbe gilt für
  die Formenliste an einer Stelle in `system.md`.
  `scripts/pruefe_profil.py` prüft gegen, ob beide dasselbe sagen; ein Test
  (`tests/test_formen_katalog.py`) hält die Formenliste in `system.md` gegen
  den Katalog. Beim nächsten echten Umformulieren lässt sich das sauber
  auflösen.
- **`prompts/erkenner.md`, `journal.md`, `theater-tells.md`,
  `formen/lied.md`, `formen/monolog.md`** tragen weiter Beispielnamen und
  Beispielgegenstände (Koffer, Kiosk, Maria, Elif). A.6 der Analyse ordnet
  sie „Profil je Sprache" zu; die Erkenner-Few-Shots sind ausserdem gemessen
  (FP = 0), ein Umbau ohne Neumessung wäre ein Rückschritt. Ein Profil, das
  sie braucht, ersetzt die Datei als Ganzes — der Weg dafür steht.
- **`anweisungen.UEBERSCHRIFT`** lautet weiter „Zusaetzliche Anweisung fuer
  diesen Workshop:". D.7 der Analyse schlägt „Anweisung für heute:" vor,
  weil das Profil jetzt „dieser Workshop" ist. Nicht geändert: es ist eine
  Verhaltensänderung am Prompt und stand nicht im Auftrag.

---

## 6. Die neun Schritte, wie sie gelaufen sind

Ein Commit je Schritt, jeder für sich grün.

| # | Commit | Testzahl danach |
|---:|---|---|
| 1 | Profil-Lader `workshop.py`, eingehängt über `IT_WORKSHOP` | 1868 |
| 2 | Platzhalter im Prompt, Profil im Cache-Schlüssel | 1882 |
| 3 | Rahmenblock und Zielgruppe ins Profil | 1896 |
| 4 | Formen-Katalog aus `formen.toml` statt viermal im Code | 1909 |
| 5 | Beispielorte und Projektbeschreibung ins Profil | 1920 |
| 6 | Phasen und Phasentexte ins Profil | 1931 |
| 7 | Test-Zweiteilung, `tests/profile/test_dortmund.py` | 1957 |
| 8 | `scripts/pruefe_profil.py`, vor dem Bot-Start | 1970 |
| 9 | `workshop/padua-2026/` als Gerüst, `LIESMICH` je Profil | 1983 |

Ausgangslage war **1839 passed, 1 skipped**. Kein Test wurde gelöscht; einer
(`tests/test_simulation_skript.py`, „eine Phase testweise umbenennen") hat
seinen Angriffspunkt von `phasen.PHASEN` auf `workshop.phasenliste`
gewechselt — die Zusicherung ist dieselbe geblieben.

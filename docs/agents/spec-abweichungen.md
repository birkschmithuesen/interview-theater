# Wo SPEC und Code auseinanderlaufen

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 2278–2324 und 1366–1394).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Wo SPEC und Code auseinanderlaufen

`SPEC-kontext-architektur.md` § 8 beschreibt ursprünglich vierzehn Befehle
und einen Modus B (`/gruendlich`, freier Prosatext mit
`reasoning_effort: "medium"`, via `LLM.prosa()`). Nach dem ersten
Workshoptag wurde das auf sechs Befehle reduziert (Commit „Sechs Befehle als
Notausgang"): `/merken`, `/verworfen`, `/konflikt`, `/begriffe`, `/name`,
`/material` und `/gruendlich` existieren in der SPEC, aber nicht mehr im
Code. Seitdem sind Befehle wieder dazugekommen; **die Wahrheit ist
`befehle._BEKANNTE_BEFEHLE`, nicht diese Aufzählung und nicht die
SPEC-Tabelle.** Stand 06.09.2026 sind es dreizehn:

| Befehl | Wirkung |
|---|---|
| `/aufnahme` | Interview-Umschalter (an, und nochmal für aus) |
| `/interview` · `/fertig` | dasselbe in zwei Richtungen: nur an, nur aus |
| `/auswerten [N]` | ein Interview unter `aufnahme.MINDEST_WOERTER` doch noch verdichten (N2) |
| `/stand` · `/hilfe` | Arbeitsstand zeigen, Bedienung erklären |
| `/phase [Nummer\|Name]` | Arbeitsphase zeigen oder umschalten, auch zurück |
| `/kernthema <Text>` | Kernthema setzen, `/kernthema aus` nimmt es zurück |
| `/stueck [rahmen <Text>]` | das Setting zeigen oder setzen (`format` bleibt stilles Synonym) |
| `/szene <Auftrag>` | Szene planen, Form setzen, schreiben lassen — mit `/szene` ist `LLM.prosa()` verdrahtet (SPEC § 4.5 Nachtrag) |
| `/figur <Name> entfernen` | weiches Löschen (NACHTRAG N3); `/figur` legt bewusst **nichts** an, das macht weiterhin der Erkenner im Gespräch |
| `/wortlaut [Name\|aus]` | Originaltranskripte im Prompt mitlesen |
| `/leitfaden` | den gebauten Gesprächsleitfaden zeigen (versteckt) |

Im Telegram-Menü (`setMyCommands`, `befehle.BEFEHLE_LISTE`) stehen davon
**acht** — `/interview`, `/fertig`, `/figur`, `/wortlaut` und `/leitfaden`
sind bewusst nicht beworben. Das ist kein Versehen: **Slash-Befehle werden
nicht mehr beworben**, beworben wird der Knopf.

`befehle.behandle()` nimmt seit `/szene` ein optionales `klm` entgegen. Die
alte strukturelle Garantie („behandle bekommt kein LLM-Objekt, also kann ein
Befehl nicht am Modell scheitern") ist damit eine Zusage geworden, die der
Code weiterhin einhält: **kein Befehl ruft synchron ein Modell** — `/szene`,
`/fertig` und `/auswerten` geben sofort an einen eigenen Thread ab. Wer einen
vierzehnten Befehl anhängt, halte sich daran.

**Toter Code, der stehenbleibt:** die Spalte `gruppe.gruendlich_naechster_zug`
gehörte zum gestrichenen `/gruendlich` und wird von keiner Zeile Python mehr
gelesen. Sie bleibt trotzdem im Schema (06.09.2026, Refactoring): sie zu
entfernen hieße, das Schema einer laufenden Datenbank umzubauen — SQLite
braucht dafür je nach Version einen Tabellenneubau, `db.py` migriert
ausschließlich additiv, und im Betrieb laufen vier Bots auf denselben
Dateien. Eine tote Spalte kostet ein Byte je Gruppe; ein misslungener
Schema-Umbau kostet den Workshop.

`einstellungen.py` liest zusätzlich `IT_MODELL_ERKENNER` (Vorgabewert
`google/gemma-4-31B-it`) — diese Variable fehlt noch in
`docs/betrieb-env.beispiel`.

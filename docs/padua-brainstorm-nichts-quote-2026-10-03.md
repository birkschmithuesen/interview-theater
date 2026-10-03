# Padua Brainstorm live: NICHTS-Quote der Buehnenkarte (Punkt 3)

Replay-Methode: `scripts`-Verzeichnis wurde NICHT angefasst (einmaliges
Skript im Scratch-Verzeichnis, nicht Teil des Commits). DB-Kopie via
`VACUUM INTO` aus `betrieb/padua.db` (nur lesend geoeffnet), zwei Varianten:

- **amsterdam**: Kopie, in der nur die drei zusammenhaengenden
  Amsterdam-Aufnahmen (id 17-19, Beerdigung vor der Stadtmauer /
  Gerichtsurteil gegen Johannes Brandt) als `brainstorm=1` markiert sind --
  alle Mikrofontests (id 7-15) auf `brainstorm=0` gesetzt. Nutzertext 1050
  Zeichen.
- **voll**: unveraenderte Kopie, wie live gesehen (Mikrofontests + Amsterdam).
  Nutzertext 1453 Zeichen.

Aufruf: `szene_claude.prosa(conn, e, httpx.Client(), cid,
anweisungen.hole("buehnenkarte"), buehnenkarte._nutzertext(conn, cid),
"brainstorm_karte_replay")`, Modell `claude-opus-5-5` ueber den lokalen Proxy
(Abo, 0 CHF), je 3 Laeufe je Variante -- macht zusammen 6 Aufrufe, innerhalb
des Budgets von 12. Keine Prompt-Variante gemessen (siehe Begruendung unten).

## Ergebnis

| Variante  | Lauf | NICHTS | Antwortlaenge | Dauer |
|-----------|------|--------|----------------|-------|
| amsterdam | 1    | nein   | 931 Zeichen    | 9,2 s |
| amsterdam | 2    | nein   | 854 Zeichen    | 9,3 s |
| amsterdam | 3    | nein   | 1065 Zeichen   | 9,8 s |
| voll      | 1    | **ja** | 6 Zeichen      | 3,1 s |
| voll      | 2    | **ja** | 6 Zeichen      | 3,6 s |
| voll      | 3    | nein   | 694 Zeichen    | 10,2 s |

NICHTS-Quote: amsterdam 0/3 (0 %), voll 2/3 (67 %).

## Befund

Isoliert man den Amsterdam-Teil, schweigt das Modell in keinem der drei
Laeufe -- es erkennt das Stueck zuverlaessig als kartenwuerdig. Im vollen
Transkript (Mikrofontests + Amsterdam) schweigt es in 2 von 3 Laeufen trotz
desselben, eindeutig dichten Materials. Die Mikrofontests allein tragen den
Unterschied: sie verdraengen offenbar keine Information (das Amsterdam-Stueck
bleibt wortgleich im Nutzertext stehen), aber sie scheinen das Modell in
Richtung Zurueckhaltung zu verschieben -- vermutlich weil der Prompt "nur
melden, wenn wirklich etwas Neues da ist" implizit auf "die Mehrheit des
Mitschnitts ist Material, kein neuer Einfall" liest, und das Amsterdam-Stueck
dann als noch nicht abgeschlossen/nicht neu genug bewertet wird (Lauf 3 der
Variante "voll" hat es dennoch erkannt -- die Schwelle liegt nah an 50/50).

**Keine Prompt-Aenderung vorgeschlagen.** Der Befund zeigt Varianz (Opus
antwortet bei identischem Prompt und Nutzertext nicht deterministisch, wie
schon in den drei vorherigen Live-Wiederholungen mit 3x NICHTS gemessen),
aber keinen klaren strukturellen Fehler im Prompt, der eine Variante
rechtfertigen wuerde -- 1/3 Treffer im vollen Transkript ist nicht "schweigt
systematisch auf kartenwuerdigem Material", sondern grenzwertig. Eine
einzelne Mustervariation auf Basis von 6 Aufrufen waere Ratenrauschen als
Befund verkauft. Empfehlung an Birk: falls das Schweigen im Live-Betrieb der
naechsten Workshops weiter auffaellt, mit mehr Laeufen (z. B. 10 je Variante)
nachmessen, bevor am Prompt etwas geaendert wird.

## Aufbewahrung des Audios (siehe Karten-Hinweis)

Geprueft: `audio-padua/<chat_id>/<message_id>.webm` wird je Segment angelegt,
kein Code-Pfad im Repository loescht sie wieder (weder `aufnahme.py` noch
`scripts/loeschen.py` beruehrt einzelne Segmentdateien -- letzteres loescht
nur beim vollstaendigen Gruppen-Loeschweg das ganze Verzeichnis). Es gibt
keine dokumentierte Aufbewahrungsfrist/-regel im Code oder in AGENTS.md fuer
Brainstorm-Audiosegmente speziell. **Offene Frage an Birk:** Soll es eine
Aufbewahrungsregel geben (Alter, Groesse, oder "bleibt wie bisher
unbegrenzt")? Diese Karte aendert daran nichts.

## Whisper-Spracherkennung (Punkt 6, nur Notiz)

Mehrere kurze/leise Segmente wurden von Whisper als "norwegian nynorsk"
erkannt (siehe `padua-gruppe1.log`). Kein Code-Befund -- Whisper rutscht bei
kurzen, leisen oder verrauschten Segmenten in der Spracherkennung ab. Kein
Commit dazu.

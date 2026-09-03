# Nachtrag Birk, 2026-09-03 (nach Baubeginn)

Zwei Ergänzungen, die NACH der Vereinfachungs- und Extraktor-Entscheidung kamen.
Sie gehören in Spec und Plan und werden nach dem Durchstich gebaut.

## N1 — Zwei Arten von Weboberfläche, nicht eine

Bisher war nur EIN Dashboard fürs Workshop-Team vorgesehen. Birk will zusätzlich
eine Seite **pro Gruppe**, die die Frauen neben ihrem Telegram-Fenster offen haben.

**A) Team-Dashboard** (wie bisher): ein Rechner, projiziert, zeigt **alle**
Gruppen nebeneinander. Für die Plenumsrunden und zum Mitverfolgen.

**B) Gruppenseite, je Gruppe eine eigene URL.** Zeigt NUR das Material dieser
einen Gruppe. Zweck: Telegram ist ein schlechter Ort, um einen wachsenden Text zu
lesen — die Gruppenseite ist die Leseansicht dazu. Damit ist auch die alte
Kompromiss-Idee „Telegram schreibt, Web liest" endlich erfüllt.

Inhalt einer Gruppenseite:
- Arbeitsstand: Begriffe, Kernthema, Figuren, Hauptkonflikt
- Verdichtungen je Interview **mit Belegzitaten**
- Szenentexte im Volltext (das ist der Hauptgrund für die Seite)
- Journal (Weg dahin, inkl. Verworfenem) — optional einklappbar

**Beide Seiten sind read-only.** Geschrieben wird ausschließlich über den Chat.
Das bleibt so, weil sonst zwei Schreibwege gegeneinander laufen.

**Sicherheit, bewusst niedrigschwellig:** die Gruppenseiten-URL enthält ein
langes, nicht ratbares Zufalls-Token pro Gruppe (`/g/<token>`), kein Login.
Wer die URL hat, sieht die Gruppe. Das ist angemessen für einen zweitägigen
Workshop und verhindert, dass Gruppe 2 versehentlich Gruppe 1 liest.

**Technisch klein halten:** ein einziger kleiner HTTP-Server im selben Repo,
liest dieselbe SQLite (read-only geöffnet), Seite lädt sich alle paar Sekunden
selbst neu. Kein Frontend-Framework, kein Build-Schritt. Das Team-Dashboard und
die Gruppenseiten sind zwei Routen derselben Anwendung.

## N2 — Eintragen in die DB per normaler Sprache, nicht nur per /Befehl

Ergänzt die Extraktor-Entscheidung. Die Gruppe soll auch **im normalen
Gespräch** etwas festlegen können, ohne einen Slash-Befehl zu tippen:

- „unser Kernthema ist Ankommen"
- „nimm Maria als Figur auf"
- „das mit den Kindheitsfragen lassen wir"

Das ist genau die Aufgabe, die der Extraktor ohnehin hat — er läuft nachgelagert
über alles seit der letzten Bot-Antwort und schreibt Journal **und**
Arbeitsstand. Diese Ergänzung heißt konkret:

1. Der Extraktor-Prompt muss **explizit auf gesprochene Festlegungen achten**,
   nicht nur auf Entscheidungen, die der Bot selbst vorgeschlagen hat.
2. **Auch Sprachnachrichten zählen** — ein Transkript ist Text wie jeder andere
   und geht in dasselbe Extraktionsfenster.
3. Die Meldung an die Gruppe bleibt die Absicherung: „Notiert: Kernthema =
   Ankommen. Falls das nicht stimmt, sagt es mir."
4. Slash-Befehle bleiben nur noch der **Korrekturweg**.

**Risiko, bewusst in Kauf genommen:** ein Modell, das aus dem Gespräch
Festlegungen zieht, wird gelegentlich etwas eintragen, das nur laut gedacht war.
Die Meldung im Chat plus die Gruppenseite (N1-B) sind die Korrekturfläche. Wenn
sich am ersten Workshoptag zeigt, dass zu viel eingetragen wird, ist die
Stellschraube der Extraktor-Prompt (strenger: nur bei klarer Festlegung), nicht
neue Mechanik.

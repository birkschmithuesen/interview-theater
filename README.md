# interview-theater

Ein Werkzeug, mit dem Gruppen aus eigenen Interviews ein Theaterstück
entwickeln — geführt über einen Chat, gebaut für Menschen ohne technische
Vorkenntnisse.

## Worum es geht

Eine Gruppe führt Interviews, schickt sie als Sprachnachricht in einen
Gruppenchat, und arbeitet von dort aus weiter: Das Material wird transkribiert
und verdichtet, aus den Kernthemen entstehen Figuren, aus den Figuren ein
Konflikt, aus dem Konflikt Szenentext. Der Bot moderiert diesen Weg, aber er
entscheidet nichts — die Gruppe kann jederzeit abbiegen.

Die Methode stammt aus einer Theaterproduktion, in der der Stücktext aus
geführten Interviews entstand. Dieses Repository macht daraus ein
wiederverwendbares Werkzeug.

## Haltung

- **Die Kernidee kommt von der Gruppe, nicht vom Modell.** Vorschläge sind
  Andockpunkte zum Reagieren, keine Vorgaben. Jeder Schritt hat die Option
  „wir machen es anders".
- **Vorschläge sind belegt.** Ein Konflikt wird mit dem Zitat aus dem Interview
  ausgeliefert, an dem er festgemacht ist — nachprüfbar, nicht behauptet.
  Findet sich das Zitat nicht wörtlich im Transkript, wird es weggelassen.
- **Europäische Infrastruktur.** Spracherkennung und Sprachmodell laufen über
  Infomaniak in der Schweiz (offene Modelle, kein Training auf Kundendaten).
  Die verbleibende Nicht-EU-Stelle ist Telegram selbst — das wird benannt, nicht
  verschwiegen.
- **Einfach vor elegant.** Nur `httpx` und `sqlite3`, kein Framework. Ein
  Prototyp, der sicher läuft, schlägt einen schönen, der nie unter Last stand.

## Aufbau

```
theatersoap/       Bot: Telegram, Datenbank, Sprachmodell, Spracherkennung
scripts/           Betriebswerkzeuge (u.a. vollständiges Löschen einer Gruppe)
tests/             Testsuite
docs/              Spezifikation und Umsetzungsplan
```

Ein Prozess je Gruppe, gleicher Code, eigener Bot-Token, gemeinsame SQLite.
Der Zustand liegt vollständig in der Datenbank — ein Neustart verliert nichts.

## Vertraulichkeit

**Interviews sind personenbezogene Daten.** In diesem Repository liegt
ausschließlich Code und Dokumentation. Audiodateien, Transkripte,
Verdichtungen, die Datenbank und alle Zugangsdaten sind über `.gitignore`
ausgeschlossen und gehören nicht auf GitHub.

Wer das Werkzeug einsetzt, braucht das Einverständnis der interviewten
Personen und einen Weg, ihre Daten wieder zu löschen. `scripts/loeschen.py`
entfernt alle Daten einer Gruppe vollständig.

## Einrichtung

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -e .
cp betrieb.env.beispiel betrieb/gruppe1.env   # Zugangsdaten eintragen
python -m theatersoap --einstellungen betrieb/gruppe1.env
```

Benötigt: ein Telegram-Bot-Token je Gruppe (bei BotFather, **Privacy Mode
ausschalten**) und einen Infomaniak-API-Schlüssel.

## Herkunft

Entwickelt von [ArtesMobiles](https://artesmobiles.art) für einen Workshop mit
einer Theatergruppe, September 2026. Die Dokumentation im Ordner `docs/` hält
die Entwurfsentscheidungen samt Begründung fest — auch die verworfenen.

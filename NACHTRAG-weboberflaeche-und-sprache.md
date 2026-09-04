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

## N3 — Korrigieren und Löschen muss ebenfalls per Fließtext gehen

Folgt zwingend aus N1 (beide Weboberflächen sind read-only) und N2 (Eintragen per
normaler Sprache). Wenn der Chat der einzige Schreibweg ist, muss er auch der
Rückweg sein — sonst kann die Gruppe nur hinzufügen, nie zurücknehmen.

Der Extraktor muss deshalb drei Operationen erkennen, nicht nur eine:

| Absicht | Beispiel im Gespräch | Wirkung |
|---------|---------------------|---------|
| **Setzen** | „unser Kernthema ist Ankommen" | Feld wird gesetzt |
| **Ändern** | „nee, das Kernthema ist eher Zwei Städte" | Feld wird überschrieben |
| **Entfernen** | „die Figur Peter brauchen wir nicht mehr" | Eintrag wird entfernt |

**Gemeldet wird jede der drei**, gleiche Zeile wie bisher („Notiert: … Falls das
nicht stimmt, sagt es mir."). Bei Entfernen ausdrücklich benennen, WAS entfernt
wurde — sonst merkt es niemand.

### Zwei Klassen, die auseinandergehalten werden müssen

- **Arbeitsstand (Begriffe, Kernthema, Konflikt, Figuren, Szenen): frei
  überschreib- und entfernbar per Fließtext.** Das sind Arbeitsergebnisse, die
  sich im Prozess ändern sollen. Kein Bestätigungsdialog — die Meldung reicht.
  Umgesetzt als **weiches Löschen** (`entfernt_am` gesetzt statt Zeile gelöscht):
  aus dem Prompt und der Weboberfläche verschwindet es, im Journal bleibt eine
  Zeile („Entfernt: Figur Peter"), und ein irrtümliches Entfernen ist heilbar.

- **Material (Audio, Transkripte, Verdichtungen): NICHT per Fließtext löschbar.**
  Ein Interview ist die Aufnahme einer Person; „das können wir löschen" im
  Gespräch ist zu leicht falsch verstanden, und der Schaden ist unumkehrbar.
  Sagt die Gruppe so etwas, antwortet der Bot, dass das Workshop-Team das macht.
  Der Löschweg bleibt das Betreiberskript (SPEC § 8.3) — das erfüllt die
  Löschzusage gegenüber den Teilnehmerinnen, ohne sie in einen Chatbefehl zu legen.

Die Slash-Befehle bleiben als Korrekturweg bestehen und bekommen die entfernende
Form dazu (z.B. `/figur Peter entfernen`), damit es einen deterministischen Weg
gibt, wenn der Extraktor eine Absicht nicht erkennt.

## N4 — Whisper-Latenz gemessen (2026-09-03, 76 Läufe über ~52 Minuten)

Ersetzt die Annahmen zur Sprachverarbeitung durch Zahlen. Rohdaten und
vollständiger Bericht: `/home/birk/tmp_whisper_latenz/BEFUND.md`.

**Ergebnis: 76 Läufe, 76× HTTP 200, null Fehler, null Timeouts.**

| Klasse | n | Median | p90 | max |
|--------|---|--------|-----|-----|
| 7 s (Zuruf) | 9 | 2,91 s | 3,86 s | 3,94 s |
| 30 s | 9 | 2,77 s | 3,88 s | 3,92 s |
| 180 s (Interview) | 9 | 4,84 s | 5,87 s | 5,93 s |

Einziger Ausreißer der gesamten Messung: **8,88 s**. Kein einziger Lauf über 10 s.

- **Der feste Sockel von ~2,5–3 s ist bestätigt.** Erst 180 s Audio kosten
  spürbar mehr (+66 %, rund 11 ms je Sekunde Audio).
- **Chunking bringt nichts:** 6×30 s parallel = 4,22 s gegen 4,84 s am Stück.
  Zerschneiden nur wegen der 25-MB-Grenze (~13 min WAV), nicht für Tempo.
- **Kein Rate-Limiting:** 10 gleichzeitige Uploads, alle 200, max 4,91 s.
  Alle drei Gruppen dürfen gleichzeitig sprechen.

**🔴 Wichtiger Vorbehalt — die Festival-Beobachtung ist NICHT widerlegt.**
30-Sekunden-Wartezeiten und Ausfälle traten heute nicht auf, konnten also auch
nicht erklärt werden. Der Upload-Anteil war hier vernachlässigbar (0,26–0,46 s)
— plausibelste Erklärung für den Festivalbetrieb ist deshalb **die Leitung vor
Ort, nicht der Dienst**. Nachprüfbar nur durch eine Messung am Spielort.
Zusätzlich sind die 180-s-Werte optimistisch, weil das synthetische Audio nur
115 Zeichen Text ergab; echte Rede ist mehr Decoder-Arbeit.

**Konsequenz: die Ausfallbehandlung bleibt vollständig bestehen** — sie ist
gegen das Netz in Dortmund gerichtet, nicht gegen Infomaniak. Nur die
Schwellwerte werden auf die Messung gesetzt:

| Größe | Wert | Begründung |
|-------|------|------------|
| `typing`-Anzeige | ab **5 s** | über jedem gemessenen Maximum |
| Textmeldung an die Gruppe | ab **12 s** | rund 3× p90, feuert im Normalbetrieb nie |
| Zeitbudget kurz (≤45 s Audio) | **45 s** | |
| Zeitbudget lang (Interview) | **90 s** | |
| Wiederholung | **genau 1**, sofort, neuer Upload | |
| danach | Nachreich-Queue (`status='empfangen'`) | heilt sich selbst |

Die frühere Annahme „Zwischenmeldung ab 8 s" war zu früh gegriffen: sie hätte
bei einem einzigen gemessenen Ausreißer (8,88 s) grundlos gefeuert.

## N5 — Technische Klärung der Weboberfläche (gemessen 2026-09-03)

Alles hier ist auf den echten Maschinen gemessen, nicht angenommen.

### Server: stdlib `ThreadingHTTPServer`, kein Framework

Grund ist ein Messbefund: **System-Python auf dem vServer ist 3.9.2** (Debian 11),
3.11 nur über uv. FastAPI/Flask liegen ausschließlich im Hermes-venv und sind für
dieses Projekt nicht nutzbar — ein Framework wäre also neues venv + pip am
Vorabend, kein „ist eh da". Vier read-only-Routen brauchen kein Routing-Framework.

Zwei Pflichtdetails:
- **`ThreadingHTTPServer`**, nicht `HTTPServer` — sonst blockiert ein Handy mit
  schlechtem Empfang die Projektion.
- **Frische SQLite-Verbindung pro Request** (`sqlite3`-Objekte sind nicht
  thread-safe; Aufbau kostet <1 ms).

🔴 **`immutable=1` NIEMALS verwenden** — gemessen: ignoriert das WAL, liefert
`no such table` oder veraltete Daten. Die Seite zeigt dann stundenlang stumm
einen alten Stand, was wie „die Gruppe arbeitet halt langsam" aussieht.
Richtig: `sqlite3.connect("file:<pfad>?mode=ro", uri=True)` + `busy_timeout=5000`.

### Aktualisierung: für die zwei Seiten UNTERSCHIEDLICH

- **Dashboard (Beamer): `<meta http-equiv="refresh" content="15">`.** Null JS,
  kein Zustand, überlebt Netzhänger, kein Speicherleck über Stunden. Auf einer
  Projektion scrollt niemand, der Nachteil entfällt.
- **Gruppenseite: KEIN Meta-Refresh.** Ein Vollreload wirft die Leserin an den
  Seitenanfang — genau das würde die Seite für ihren einzigen Zweck unbrauchbar
  machen. Stattdessen ~15 Zeilen JS: alle 10 s `fetch('/g/<token>/version')`,
  bei Änderung ein Banner **„Neues Material — neu laden"**. Der Mensch entscheidet,
  wann er die Leseposition verliert. Ohne JS bleibt es eine funktionierende
  statische Seite.
- **SSE abgelehnt:** dauerhaft offene Verbindung ist auf Handy-WLAN das
  Fragilste (stirbt bei Displaysperre, WLAN-Wechsel, Proxy-Timeout) und bräuchte
  Reconnect-Logik — mehr bewegliches Teil als der ganze Rest.

### 🔴 Erreichbarkeit: der vServer kann es NICHT selbst

Von einer dritten Maschine gemessen (`curl localhost` beweist nichts):

| Bedingung | vServer 78.47.156.115 |
|---|---|
| Port 80 von außen | **BLOCKED** (Cloud-Firewall) → kein ACME HTTP-01 |
| Port 443 | offen, aber **von Docker belegt** (`office.artesmobiles.art`) |
| 8080 / 8899 | BLOCKED |
| Egress zu Let's Encrypt | **BLOCKED** (github/telegram offen → selektiv gefiltert) |
| Root | **kein sudo**, `/etc/nginx` nicht schreibbar |

**Tailscale Funnel scheitert am Admin-Schritt**, nicht am Konzept: `tailscale
cert` → `Access denied`, verlangt einmalig `sudo tailscale set --operator=$USER`.
(Funnel-URLs sind öffentlich, die Handys bräuchten kein Tailscale — es ist also
eine Option für später, nur nicht für den Vorabend.)

**Lösung: `herkules` (91.98.143.165) als Türsteher.** Dort: nginx 1.24 öffentlich
auf 80+443, certbot 2.9, ACME-Egress offen, zwei laufende LE-Vhosts.
**Beweis erbracht:** ein stdlib-`http.server` an `100.75.24.33:8877` wurde von
herkules aus erfolgreich abgerufen, **16 ms** über den Tailnet.

```
Handy → HTTPS → herkules:443 (nginx, LE-Cert)
                  └─ proxy_pass → http://100.75.24.33:8010 (Tailnet)
                       └─ interview_theater-Web auf dem vServer, liest SQLite lokal (mode=ro)
```

Die Datenbank bleibt beim Bot, nur HTTP wandert. `kg-mirror` ist exakt dieses
Muster und läuft bereits — kopierbare Vorlage vorhanden.
**Server an `100.75.24.33` binden, nicht an `0.0.0.0`.**

**🔴 Der einzige Blocker, den nur Birk lösen kann (root auf herkules):**
- **Plan B, empfohlen:** ein `location /theatersoap/ { proxy_pass ...; }` in den
  **bestehenden** `kollektivgedaechtnis.flashclash.de`-Vhost. Kein DNS, kein
  neues Zertifikat, nur ein Block + `systemctl reload nginx`. ~5 Minuten.
- Plan A (eigene Subdomain + certbot) ist Kosmetik und kostet DNS-Propagation.

### Projektion

- **Heller Hintergrund** (`#f7f5f2`, Text `#1a1a1a`) — Beamer haben in einem
  hellen Raum kein Schwarz, Dunkeldesign wird schmutziggrau.
- Basis `20px`, Fließtext ~24 px, Überschriften 34–42 px bei 1080p. Unter 24 px
  ist aus 4 m nicht lesbar. Systemschriften, keine Webfonts.
- **Drei feste Spalten à 33 vw, kein Scrollen.** Was nicht passt, wird
  abgeschnitten statt scrollbar gemacht.
- 🔴 **Szenen-Volltext gehört NICHT aufs Dashboard** — er sprengt jede Spalte.
  Dashboard: Kernthema, Konflikt, Figurennamen, Szenen als Titel + Nummer, die
  letzten 5 Journaleinträge. Volltext ist der Zweck der Gruppenseite.
- Farbleiste je Gruppe, gleiche Farbe oben auf deren Gruppenseite. Gruppenname
  als große Kopfzeile, damit eine falsch geöffnete URL sofort auffällt.
- **QR-Code je Gruppe auf A5 ausdrucken** (Token ~16 Hex-Zeichen). Keinen
  Online-QR-Dienst benutzen — die URL soll nicht bei Dritten landen.

### Fallstricke

1. **Heimlich veraltete Daten** durch `immutable=1` oder geteilte Connection →
   fällt nicht als Fehler auf. Gegenmaßnahme oben; heute Abend einmal echt
   durchspielen: Bot schreibt, Seite neu laden, Wert muss da sein.
2. **Um 9:00 nicht erreichbar** (Cert/DNS/Vhost) → Plan B heute Abend, und die
   URL **von einem echten Handy über Mobilfunk** testen, nicht aus dem WLAN.
3. **Ein `None` nimmt den ganzen Beamer mit** — Samstagfrüh ist fast jedes Feld
   NULL. Jedes Gruppen-Panel einzeln in `try/except`, im Fehlerfall „—" statt
   weißer Seite. Testlauf gegen eine LEERE DB mit „noch nichts"-Platzhaltern.

### Aufwand und Schnittreihenfolge

Realistisch 3–4 Stunden, ~250 Zeilen Python, zwei HTML-Templates, kein Build.
Wenn die Zeit knapp wird, fällt in dieser Reihenfolge: (1) Journal auf dem
Dashboard, (2) eigene Subdomain, (3) Version-Polling → ersatzweise ein sichtbarer
„Neu laden"-Knopf.
**Nicht verhandelbar:** Szenen-Volltext auf der Gruppenseite, `mode=ro`,
und der Test von einem echten Handy über Mobilfunk.

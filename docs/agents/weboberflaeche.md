# Weboberflaeche

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 2438–3324 und 1505–1599).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Weboberfläche

Ein einziger Prozess für alle Gruppen, neben den Bots:

```
IT_DB=betrieb/soap.db python -m interview_theater.web
```

Unit-Vorlage `docs/interview-theater-web.service` (nach `~/.config/systemd/user/`,
`daemon-reload`, dann `systemctl --user enable --now interview-theater-web`), Log
nach `betrieb/web.log`.

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `IT_DB` | — (Pflicht) | dieselbe SQLite wie die Bots, **read-only** geöffnet |
| `IT_WEB_BIND` | `127.0.0.1:8010` | im Betrieb `100.75.24.33:8010` (Tailnet) |
| `IT_WEB_PREFIX` | `/theatersoap` | Präfix, unter dem nginx den Server durchreicht |
| `IT_WEB_URL` | `https://lab.artesmobiles.art/theatersoap` | nur für `scripts/web_links.py` |

Routen: `/` (Team-Dashboard, projiziert, alle Gruppen), `/g/<token>`
(seit Karte W die **vereinte** Seite mit den drei Tabs Chat · Arbeitsstand ·
Textbuch, siehe „Eine Oberfläche je Gruppe" unten), `/g/<token>/teil/stand`
und `/g/<token>/teil/roadmap` (die beiden Panel-Ausschnitte fürs sanfte
Nachladen, `web_vereint.sende_teil`), `GET /g/<token>/chat/strom` (der
SSE-Kanal des laufenden Texts, siehe „Der Strom"), `POST /g/<token>/chat/phase`
(der Klick auf eine Phase, siehe „Die Phasenübersicht"), `/g/<token>/textbuch`
(Probenansicht, siehe unten) samt `/g/<token>/textbuch.md` und `.txt`,
`/g/<token>/leitfaden` (der Gesprächsleitfaden groß und druckbar, rein
lesend, ohne Nachladen — siehe „Der Leitfaden hat eine eigene Seite"),
`/g/<token>/chat` (seit Karte W ein **302** auf `/g/<token>#chat` — die
Chatansicht des Web-Kanals ist in der vereinten Seite aufgegangen, siehe „Der
Web-Kanal" und „Eine Oberfläche je Gruppe") samt den weiter gültigen
Chat-Endpunkten `chat/zustand`, `chat/datei/<id>` und den POST-Wegen
`chat/senden`, `chat/knopf`, `chat/audio`, `chat/interview` und
`/gesund` (Health-Check, antwortet ohne Datenbankzugriff). Jede Route greift
auch mit vorangestelltem `IT_WEB_PREFIX`, weil erst die nginx-Konfiguration
entscheidet, ob das Präfix beim Server ankommt. Was hinter `/g/<token>/`
nicht in dieser Liste steht, ist 404 und nicht etwa Teil des Tokens
(`web._beantworte_gruppenseite`).

`python scripts/web_links.py` gibt aus, welche Gruppe welchen Link bekommt.
Das Token steht in `gruppe.web_token`, erzeugt wird es beim ersten Kontakt
vom Bot (`repo.stelle_web_token_sicher`, aufgerufen aus `sichere_gruppe`) —
der Webserver kann es nicht anlegen, er liest read-only.

**Drei Grenzen, die nicht verhandelbar sind**, weil beide Seiten ohne Login
erreichbar sind und das Dashboard projiziert wird:

- kein Nachrichtentext und keine Transkripte auf dem Dashboard,
- kein Volltranskript auf der Gruppenseite (dafür gibt es `/wortlaut` im Chat),
- kein Belegzitat ohne `zitat_geprueft = 1`.

`IT_WEB_BIND` lehnt `0.0.0.0` mit einem Fehler ab: ein Tippfehler in einer
Env-Datei soll die Interviews nicht ins offene Netz stellen.

### Die Probenansicht (06.09.2026)

`/g/<token>/textbuch` ist das ganze Stück am Stück — Szene für Szene mit
Nummer, Titel, Form, Ort/Zeit/Anlass, Besetzung und Volltext, eine
ungeschriebene Szene als Platzhalter mit ihrer Planung (dieselbe Entscheidung
wie in `szenenfolge.textbuch`: eine fehlende Szene 4 sieht aus wie ein
Fehler). Anlass ist Birks UX-Frage: bis dahin war Telegram der Arbeitsraum
und das Web die Anzeige, und für die eigentliche Theaterarbeit — Rollen
lesen, laut sprechen — ist ein Chatverlauf das falsche Medium. Der fertige
Text versinkt zwischen hunderten Nachrichten, und in der Probe hält jede
Person ihr eigenes Telefon in der Hand, nicht den Gruppenchat.

**Sie bleibt rein lesend**, und das ist keine Sparmaßnahme: die Gruppenseite
ändert seit dem 05.09. eine feste Liste von Parametern, weil dort *entschieden*
wird. In der Probe wird *gespielt*. Ein Formular unter einem Szenentext, den
man gerade laut liest, wäre eine Einladung zum Vertippen an der einen Stelle,
die ohnehin dem Chat gehört (der Volltext entsteht aus einem Modellauf und
wird dort abgenommen). Also: kein POST auf dieser Route (404), kein Nonce,
keine Zeile in `web_schreiben.FELDER`. Und **kein Nachladen** — weder `meta
refresh` noch das sanfte `fetch` der anderen Seiten: es würde alle zehn
Sekunden Rollenfilter und Schriftgröße zurücksetzen, und ein Textbuch ändert
sich nicht, während man es liest (`web._seite(..., nachladen=False)`).

Die Grenze ist hier **enger als auf der Gruppenseite**: nur Szenentexte und
Szenenplanung. Keine Interviews, kein Journal, keine Verdichtung, kein
Belegzitat — der Link geht in der Probe von Hand zu Hand. Test:
`test_kein_material_in_der_probenansicht`.

**Der Rollenfilter parst defensiv** (`web.sprecher_der_zeile`). Erkannt wird
die Grundform aus `prompts/szene.md` — „Figurennamen in GROSSBUCHSTABEN,
danach ein Doppelpunkt, dann die Replik" — samt der engen Schreibweise aus
`prompts/formen/dialog.md` (`LEYLA:(steht auf)Text`) und `CHOR:`. Dagegen
gesperrt sind: Satzzeichen im Namen, mehr als 30 Zeichen, und die Wörter, die
in echten Texten am Zeilenanfang mit Doppelpunkt stehen, ohne eine Figur zu
sein (`SZENE 1: …` aus dem Szenenkopf, `TITEL:`, `KURZ:` — sonst hätte jedes
Stück eine Figur namens „SZENE 1"). Ein kleingeschriebener Name gilt **nur**,
wenn die Gruppe wirklich eine Figur dieses Namens hat. **Wird keine
Sprecherzeile erkannt, fehlt die Leiste ganz** statt falsch zu markieren —
genau der Fall eines Stücks, das erst als Geschichte dasteht (Phase 6, Prosa).
Hervorgehoben wird gedämpft, nicht gelöscht: die Stichworte muss man
mitlesen können, sonst weiß niemand, wann sein Einsatz kommt.

Rollenfilter, Schriftgröße (drei Stufen) und „Regieanweisungen ausblenden"
laufen clientseitig, ihr Zustand steht im **URL-Fragment**
(`#figur=Leyla&schrift=gross&regie=aus`) und sonst nirgends — kein Cookie,
kein localStorage, kein Server-Roundtrip: der Link soll teilbar sein („so
liest sich das mit meiner Rolle"). Fällt JavaScript aus, bleibt das ganze
Stück lesbar, nur die Leisten wirken nicht.

**„PDF" ist ein Browser-Ausdruck.** Der `@media print`-Block wirft Leisten,
Wege und Farben weg und setzt ein Manuskript: Serifenschrift, Sprecher fett,
je Szene ein Seitenumbruch, und im Ausdruck gilt kein Rollenfilter (gedruckt
wird das ganze Stück, auch wenn am Telefon gerade eine Rolle hervorgehoben
ist). Damit braucht der Weg zum Papier keine Abhängigkeit.

`/g/<token>/textbuch.md` und `.txt` liefern **wörtlich**
`szenenfolge.textbuch(conn, chat_id)` — dieselbe Funktion, die der Knopf
„Textbuch als Datei" im Chat verschickt, gelesen über die read-only geöffnete
Verbindung. Keine zweite Wahrheit: zwei Textbücher, die irgendwann
auseinanderlaufen, wären schlimmer als eines, das nicht jedes Format kennt.
Im Chat steht der Link zur Probenansicht seitdem **neben** dem Datei-Knopf
(`knoepfe.probenansicht_zeile`, an beiden Stellen: `biete_durchlauf` und
`biete_nach_pruefung`) — als Textzeile, weil eine Inline-Tastatur
`callback_data` trägt und keinen Link. Der Knopf bleibt: die Datei nimmt man
mit, die Seite liest man in der Probe.

### Die Gruppenseite ändert Parameter (05.09.2026 abends)

Bis zu diesem Abend war beides read-only, mit der Begründung „sonst laufen
zwei Schreibwege gegeneinander" (N1). Die Begründung gilt weiter — deshalb
gibt es **keinen zweiten Schreibweg, sondern einen zweiten Auslöser für den
vorhandenen**: `web_schreiben.py` ruft ausschließlich `repo`-Funktionen,
dieselben wie `knoepfe._speichere` und `erkenner.wende_an`. In `web_daten.py`
kommt kein einziger Schreibpfad dazu; es bleibt read-only (`mode=ro`), und nur
der POST-Handler öffnet eine schreibende Verbindung (`db.verbinde` — WAL und
`busy_timeout`, wie `scripts/begruessen.py` aus einem fremden Prozess). Zwei
Tests halten das fest: kein `SELECT`/`INSERT`/`UPDATE` in `web_schreiben.py`,
kein Schreibpfad in `web_daten.py`. Änderbar ist **genau** `web_schreiben.FELDER`
und nichts sonst: Setting (`rahmen`), Geschichte, je Figur
Name/Beschreibung/Interview/Entfernen/Hinzufügen und je Szene Titel, Form,
Ort, Zeit, Anlass, was passiert, was anders, Ton und die Besetzung — also
genau das, was die Gruppe hier **fertig entscheiden** kann. Setting und
Geschichte sind dabei **unabhängig voneinander**: ein neues Setting ändert die
Geschichte nicht und stößt auch nichts an, was sie später ändern würde (Birk,
06.09.2026 10:25 — kein Auftragsweg vom Web an den Bot, keine automatische
Geschichte). Nicht änderbar: **nie Material** (Aufnahmen, Transkripte,
Verdichtungen, Belegzitate), nie der Szenen-Volltext, nie das Journal, nie die
USA-Einwilligung, nie der Sprachprofil-Text, nie die Schärfungs-Zuordnungen.
**Was der Chat führt** (`web_schreiben.FUEHRT_DER_CHAT`): Phase, Begriffe,
Fragen und die drei Leitfaden-Felder. Sie stehen auf der Seite an ihrem Platz,
aber als Anzeige — sie entstehen im Gespräch über Knöpfe und Ping-Pong, oft mit
einem Modellaufruf dahinter, und der Webserver hat keinen Modellklienten; sie
hier umtippen zu lassen hieße, denselben Wert auf zwei Wegen zu pflegen, von
denen einer die halbe Kette auslässt. Von den drei Leitfaden-Feldern steht
nicht einmal das Rohfeld da, sondern der **gebaute Leitfaden**
(`leitfaden.aus_feldern`, dieselbe Funktion wie im Chat): das, was die Gruppe
im Interview in der Hand hält. Seit dem Phasen-Umbau fehlen außerdem
**Kernthema, Kernthema-Richtung und Kernfrage**: sie sind keine Station mehr,
`geschichte` hat ihre Rolle übernommen; gesetzte Werte bleiben sichtbar
(`web_schreiben.NUR_ANZEIGE`, nur wenn gesetzt), änderbar sind sie nicht.
Ebenfalls nur Anzeige: der Formvorschlag je Szene (`szene.form_vorschlag` —
bestätigt ist allein `form`, und wer hier wählt, bestätigt gerade selbst) und
die Schärfungen aus Phase 6, als Zähler mit Kurzformen und **ohne Belegzitat**.
Die Dropdowns holen ihre Vorschläge aus der Tabelle `knopf`, zeigen also nur,
was im Chat ohnehin schon zur Auswahl stand. Jede Änderung hängt einen Journaleintrag an, `art
'entschieden'`, **`quelle 'web'`**, mit altem und neuem Wert (120 Zeichen je
Seite) — das ist der einzige Weg, auf dem der Gesprächs-Bot davon erfährt, denn
der Webserver spricht nicht mit Telegram: er liest das Journal bei jedem Zug
frisch (`kontext._baue_journal`). Wie in einem Knopf-Handler fällt hier **kein
Modellaufruf** an; wechselt eine Figur ihr Interview, wird deshalb das alte
Sprachprofil geleert und `geprueft_am` zurückgenommen, `knoepfe.stelle_figur_vor`
holt es im nächsten Zug im eigenen Thread nach. Das **Dashboard bleibt
vollständig read-only** und nimmt gar kein POST an — es hängt am Beamer. CSRF:
das Token in der URL ist das Geheimnis, dazu ein Formular-Nonce aus Token und
Stundenfenster (abgeleitet, nicht gewürfelt — ein zufälliger Nonce ließe das
sanfte Nachladen die Seite alle zehn Sekunden austauschen und risse jedes
offene Eingabefeld mit); aus demselben Grund lädt die Seite gar nicht erst
nach, solange der Fokus in einem Feld steht oder eines ungespeichert geändert
ist. Ein Neustart der Unit `interview-theater-web.service` ist nötig, die Bots
nicht.

### Die Absicherung (30.09.2026, Karte Padua S)

Seit Karte A2 ist die Gruppenseite schreibend und nimmt Audio an. Damit ist
der Link nicht mehr nur eine Anzeige, und die Grenzen mussten mitwachsen.

**Sechs Kopfzeilen an genau einer Stelle** (`web._Basishandler.end_headers`):
`Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Permissions-Policy: microphone=(self)` und eine CSP ohne jede Fremdquelle
(`default-src 'none'`, `frame-ancestors 'none'`, `base-uri 'none'`,
`form-action 'self'`, `connect-src 'self'`, `media-src 'self' blob:`).
In `end_headers` und nicht in `_antworte`, weil `send_error` der
Standardbibliothek (501 bei unbekannter Methode, 400 bei kaputter
Anfragezeile) daran vorbeigeht — und genau diese Antworten testet niemand von
Hand. `sys_version` ist leer: bis dahin stand `Python/3.11.15` im
Server-Header jeder Antwort.

**Der CSP-Nonce ist abgeleitet, nicht gewuerfelt** (`web.csp_nonce`), aus
demselben Stundenfenster wie der Formular-Nonce. Der Grund ist derselbe:
`_SCROLL_JS` vergleicht alle zehn Sekunden `document.body.innerHTML`, und das
`<script>`-Tag steht im Koerper — ein je Antwort neuer Nonce liesse die Seite
alle zehn Sekunden austauschen und risse jedes offene Eingabefeld mit.
`'unsafe-inline'` steht bewusst nicht in der Richtlinie: ein stundenstabiler
HMAC muss geraten werden, `'unsafe-inline'` muss gar nichts. **Wer ein
`style="…"`-Attribut oder ein `onclick=` einbaut, bricht das** — heute ist
beides in `web.py` nicht vorhanden (gemessen).

**Origin und Sec-Fetch-Site vor jeder Wirkung** (`web.eigene_herkunft`, 403).
Der Nonce schuetzt, *weil* eine fremde Seite ihn nicht lesen kann — und beim
Audio-Upload stand er in der Query und damit in der Serverlogzeile. Er ist
nach `X-Nonce` umgezogen, `log_message` maskiert das Token auf vier Zeichen
und wirft die Query weg. **Fehlt `Origin` ganz, entscheidet der Nonce wie
bisher**: `curl` schickt keinen, und das Reviewer-Drehbuch faehrt mit `curl`.

**Rate-Limit je Gruppe** (`web_grenze.py`): 20 Nachrichten je Minute
(Senden, Knopf und Umschalter teilen den Topf — sonst laesst sich abwechseln
und die Rate verdoppeln) und 150 Uploads je Stunde (eigener Topf: 45-s-
Segmente sind 80 je voller Interviewstunde, dazu Push-to-talk). Schluessel ist
die **`chat_id`**, nicht das Token: eine Rotation darf das Limit nicht
zuruecksetzen. Eine abgewiesene Anfrage zaehlt **nicht** mit, sonst wuerde aus
dem Limit eine Dauersperre. 429 mit `Retry-After`, ein Vorfall
`web_rate_limit` je Fenster. **Ein Neustart vergisst die Zaehler** — benannt
und akzeptiert, nginx ist die zweite Schicht (unten).

**Der Upload wird an den Bytes geprueft, nicht am Header**
(`web_chat.endung_aus_bytes`). Der `Content-Type` bleibt billiger Vorfilter
(415 ohne Lesen); entschieden wird an den Magic Bytes (EBML, `OggS`, `ftyp`,
`RIFF/WAVE`, `ID3`/Frame-Sync), und **die Endung, unter der die Datei
abgelegt wird, kommt von dort**. Das ist Falle 3 eine Etage hoeher: ein WebM
als `.ogg` abgelegt laesst den Whisper-Auftrag dauerhaft auf `pending`
stehen. Groesse: `MAX_AUDIO_BYTES` = 8 MiB je Segment — gerechnet gegen Opus
32 kbit/s (45 s ≈ 176 KiB) und Safaris AAC 64 kbit/s (≈ 352 KiB), also rund
zwanzigfache Luft, und klar unter `stt.MAX_UPLOAD_BYTES` (25 MiB): was
Whisper ohnehin ablehnt, soll gar nicht erst ankommen. Ueber der Grenze wird
**nichts gelesen** (413, Verbindung zu). Die **Dauer meldet der Client** und
ist deshalb kein Schutz; sie wird trotzdem geprueft, weil weiter unten
`aufnahme.HINWEIS_AB_S` daran haengt.

**Token-Rotation von Hand** (`scripts/web_token_neu.py`, `repo.erneuere_web_token`):
ohne `--ja` Trockenlauf, mit `--ja` Backup, Journaleintrag (**ohne Token**)
und die neue URL auf stdout. Der alte Link ist **sofort** 404 — der Webserver
haelt kein Token im Speicher, jede Anfrage oeffnet ihre eigene read-only
Verbindung; ein Neustart ist nicht noetig. Der alte Nonce ist an den alten
Token-String gebunden und damit ebenfalls tot. **Kein Chat-Befehl**:
rotieren heisst, dass jedes Telefon im Raum seinen Link verliert, und das ist
eine Betreiberhandlung mit Ansage, wie `scripts/loeschen.py`.

**Fehlerseiten verraten nichts**: ein Catch-all um `do_GET`/`do_POST`
antwortet mit 500 und einem festen Satz, der Traceback geht ins Log.
`send_error` ist ueberschrieben — die Vorlage der Standardbibliothek setzt
`%(message)s` und `%(explain)s` in den Koerper. Vor dieser Karte gab eine
Ausnahme im Handler **gar keine Antwort** (`RemoteDisconnected`), was das
sanfte Nachladen stumm schluckte.

### nginx auf herkules (Admin, NICHT umgesetzt)

Die App-Grenzen sind die erste Schicht; sie leben im Prozess und sind nach
einem Neustart leer. Die zweite gehoert vor den Prozess. **Dieser Block ist
ein Vorschlag fuer den Admin und steht in keiner Datei dieses Repositories** —
er passt zu den Werten oben und muesste mitgezogen werden, wenn die sich
aendern.

**Architekt-Korrektur 30.09.2026** (drei Fehler im ersten Entwurf, selbst geprueft):
(1) `limit_req_zone` kennt nur `r/s` und `r/m` — `rate=200r/h` laesst `nginx -t`
scheitern. Audio je IP deshalb 10r/m: ein laufendes Interview schickt alle 45 s ein
Segment (1,33/min), sechs Gruppen hinter einer IP ≈ 8/min.
(2) Der Webdienst laeuft **nicht** auf herkules, sondern auf dem vServer, im Betrieb
gebunden an `IT_WEB_BIND=100.75.24.33:8010` (Tailnet, AGENTS.md „Weboberflaeche\");
`127.0.0.1` auf herkules waere der falsche Rechner. ANNAHME: herkules erreicht den
vServer ueber diese Tailnet-Adresse und die bestehende `location /theatersoap/` dort
nutzt sie schon — der Admin gleicht `proxy_pass` mit der vorhandenen Konfiguration ab,
statt diesen Block blind einzusetzen.
(3) Im Workshop sitzen alle Gruppen haeufig hinter **einer** IP (Raum-WLAN). Eine
IP-Zone mit 30r/m laege dann **unter** der Summe der App-Grenzen (4 Gruppen × 20/min),
und nginx saehe vor der App ab — genau das, was der Hinweis unten vermeiden will.
Deshalb 120r/m je IP (= 6 Gruppen × 20/min).

```nginx
# http { } -- einmal, ausserhalb des server-Blocks
limit_req_zone  $binary_remote_addr  zone=theatersoap_post:10m  rate=120r/m;
limit_req_zone  $binary_remote_addr  zone=theatersoap_audio:10m rate=10r/m;
limit_conn_zone $binary_remote_addr  zone=theatersoap_conn:10m;

location /theatersoap/ {
    proxy_pass http://100.75.24.33:8010/theatersoap/;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;

    # Etwas ueber der App-Grenze (8 MiB je Segment): nginx soll die
    # Verbindung kappen, bevor die App liest -- aber nicht frueher als sie,
    # sonst diagnostiziert man einen Fehler an der falschen Stelle.
    client_max_body_size 10m;
    client_body_timeout  60s;

    limit_conn theatersoap_conn 20;
}

location ~ ^/theatersoap/g/[^/]+/chat/audio$ {
    proxy_pass http://100.75.24.33:8010;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;
    limit_req  zone=theatersoap_audio burst=20 nodelay;
    client_max_body_size 10m;
}

location ~ ^/theatersoap/g/[^/]+/chat/(senden|knopf|interview)$ {
    proxy_pass http://100.75.24.33:8010;
    proxy_set_header Host             $host;
    proxy_set_header X-Forwarded-Host $host;
    limit_req  zone=theatersoap_post burst=10 nodelay;
}
```

Die zwei `proxy_set_header`-Zeilen stehen in **jedem** `location`-Block (nginx
erbt sie nicht in einen Block, der eigene Direktiven setzt), und sie sind keine
Kür: `web.eigene_herkunft` vergleicht den `Origin` des Browsers mit `Host` oder
dem ersten Wert von `X-Forwarded-Host` — reicht nginx nur den internen Host
weiter (`$proxy_host`, die Vorgabe), wäre jeder echte POST aus dem Browser
ein 403.

Drei Hinweise dazu: die nginx-Zonen zaehlen je **IP**, die App je **Gruppe** —
das ist Absicht, zwei Achsen fangen zwei verschiedene Angriffe. Die
nginx-Raten liegen **ueber** den App-Grenzen, damit die App die Absage gibt
(mit `Retry-After` und einem Satz) und nicht nginx mit einer nackten 503. Und
die Gruppen sitzen im Workshop haeufig hinter **einer** IP (Raum-WLAN) —
deshalb die grosszuegigen `burst`-Werte.

### Der Web-Kanal: derselbe Bot ohne Telegram (30.09.2026, Karte Padua A2)

**Die Idee in einem Satz:** der Webserver ist für den Bot das, was Telegrams
Server heute ist — er nimmt Browser-Ereignisse an und legt sie als
Telegram-förmige Updates in die Tabelle `web_post`; ein normaler Bot-Prozess
liest sie mit `web_kanal.WebKanal` statt mit `telegram.Telegram`. Gewählt
wird der Kanal an genau einer Stelle, `bot.baue_kanal`.

**Was dadurch NICHT passiert ist:** `knoepfe/` (rund 4.500 Zeilen) wurde nicht
angefasst, `bot.schleife` nicht geändert, und der Telegram-Weg ist
unverändert funktionsfähig (E1: Telegram bleibt Plan B). Ohne `IT_KANAL`
verhält sich alles wie vorher — `tests/test_kanal_wahl.py` hält das fest.
Ein Tippfehler in `IT_KANAL` fällt **nicht** still auf Telegram zurück, der
Start bricht ab (`einstellungen.laden`).

**Warum die Naht trägt, ist gemessen und nicht geraten.** Die ganze
Kanalfläche sind zwölf Methoden, und `interview_theater/` ruft sie
ausnahmslos über das durchgereichte `tg`-Objekt (kein `httpx` gegen
`api.telegram.org`, `from.first_name` an genau einer Stelle,
`telegram.lies_nachricht`). `simulation/attrappe.py` beweist es seit dem
06.09.2026 empirisch: sie ersetzt `Telegram` und fährt einen ganzen Workshop
durch. `tests/test_web_kanal_naht.py` liest das Paket per AST und hält es am
Quelltext fest — **wer eine dreizehnte Kanalmethode benutzt, merkt es dort**,
nicht im Betrieb.

**EINE message_id-Folge für Gruppe UND Bot.** `web_post.id` ist zugleich
`message_id` und `update_id`. Das ist kein Detail: der Bot merkt sich seinen
Stand als `gruppe.letzte_beantwortete_message_id` und liest danach nur, was
größer ist. Zählten Gruppe und Bot in getrennten Folgen, läge jede
Gruppennachricht ab dem zweiten Zug unter dem Wasserzeichen — der Bot
beantwortete sie nie (gemessen in `simulation.attrappe.naechste_message_id`).
Telegram vergibt seine ids ebenfalls fortlaufend je Chat, über alle Absender.

**Die Tippanzeige ist keine Nachricht** und steht deshalb in
`gruppe.web_tippt_bis`, acht Sekunden gültig (`web_kanal.TIPPT_GUELTIG_S` = 8):
`arbeitszeilen.TIPP_S` ist 4,0 s, und ein vierminütiger Szenenlauf gäbe 60
Zeilen, die je eine `message_id` aus der gemeinsamen Folge verbrauchen.

**Web-Gruppen haben positive, synthetische chat_ids** ab
`repo.WEB_CHAT_ID_BASIS` (7 000 000 000 000) — weit oberhalb aller
Telegram-Bereiche, und im ganzen Repo leitet keine Stelle aus dem Vorzeichen
einer chat_id etwas ab (Test). Angelegt werden sie mit
`python -m scripts.web_gruppe anlegen <bot_name>` (Datei
`scripts/web_gruppe.py`); das Skript gibt den Link, die chat_id und die zwei
Env-Zeilen aus und **liest nie `betrieb/`**. Der Webserver könnte es nicht:
er öffnet die Datenbank read-only. `gruppe.kanal` hält fest, welcher Kanal
eine Gruppe bedient. Eine `IT_WEB_CHAT_ID`, die die Datenbank nicht kennt,
bricht den Start ab — ein Bot, der auf eine nicht vorhandene Gruppe hört,
sähe sonst aus wie ein hängender.

**E8 im Web:** Nachrichten tragen keinen Vornamen. `nachricht.absender` trägt
das Rollenwort `web_kanal.ABSENDER` (`"Gruppe"`) — nicht `None`, weil
`kontext.sprecherzeile` sonst wörtlich `"None:"` in jeden Gesprächs-Prompt
schriebe.

**Drei Dinge, die der Web-Kanal anders macht als Telegram** (alle drei
absichtlich):
1. **Kein Teilen bei 4.000 Zeichen.** Der Browser hat keine Längengrenze, und
   ein Text, der in vier Stücke zerfällt, macht aus einer Bot-Antwort vier
   Blasen, unter deren letzter dann die Knöpfe hängen.
2. **`setze_befehle` ist ein No-Op.** Im Browser gibt es kein Slash-Menü, und
   Slash-Befehle werden nicht beworben — beworben wird der Knopf.
3. **`loesche_nachrichten` löscht weich** (`web_post.geloescht_am`), wie alles
   Entfernte in diesem Projekt.

**Die Chatansicht** (`/g/<token>/chat`, Modul `web_chat.py`, Handy zuerst,
390×844) ist rein Vanilla-JS, ohne Build, ohne WebSocket, ohne Cookie, ohne
localStorage: sie pollt `chat/zustand?nach=<id>&seit=<aenderung>` alle zwei
Sekunden (sichtbar, `POLL_MS`) bzw. alle zehn (Hintergrund), und nie zwei
Polls gleichzeitig. `nach` holt neue Zeilen, `seit` holt **geänderte** —
`aendere_text`, `entferne_knoepfe` und `loesche_nachrichten` zählen die
additive Spalte `web_post.aenderung` hoch (ein Zähler, keine Uhrzeit: SQLite
serialisiert die Schreiber, also ist er monoton in Commit-Reihenfolge), und
die Blase wird ohne Neuladen ersetzt oder entfernt. Der Poll liefert außerdem
den aktuellen Formular-Nonce; ein POST mit 403 holt ihn einmal nach und
versucht es erneut. **Kein sanftes Nachladen** wie auf der Gruppenseite —
`web._seite(..., nachladen=False)`: das tauscht den `<body>` aus, und mitten in
einer laufenden Aufnahme risse das Recorder, Timer und Warteschlange mit.
Jeder Chat-Pfad mit Schrägstrich am Ende (`/chat/`) ist 404, und das JS baut
alle Wege absolut aus `location.pathname` — sonst zeigten die relativen
Verweise ins Leere, und `IT_WEB_PREFIX` bleibt dabei erhalten. Die Gruppenseite
verlinkt den Chat („Chat mit dem Bot") — **nur bei `gruppe.kanal = 'web'`**,
und alle Wege unter `/chat` (GET und POST) sind für jede andere Gruppe 404
(`web_daten.web_chat_id_nach_token`, Abschlussreview I3). Der Plan
(Aufgabe 6) schrieb den Link für jede Gruppe vor; **E1 geht vor**: eine
Telegram-Gruppe hat keinen Bot, der `web_post` liest, und was sie im Browser
schriebe, ginge still verloren. Gruppenseite, Probenansicht und Leitfaden
bleiben für alle Gruppen.

**Der Eingang wird als lückenloses Präfix geliefert** (Abschlussreview C1,
I1, `WebKanal._lieferbar`). `bot.schleife` rückt den Offset je Update vor —
eine zurückgehaltene Zeile mit etwas Späterem dahinter wäre danach für immer
übersprungen. Zurückgehalten wird an zwei Stellen, beide mit Frist und Log:
(1) eine **Sprachzeile ohne `datei`** — der Webserver legt erst die Zeile an,
schreibt dann die Datei und setzt danach den Verweis (`DATEI_FRIST_S` = 30);
(2) **jeder Nicht-Segment-Post** (Text, Knopf, Befehl) hinter einem Segment,
das beim Bot noch nicht angekommen ist — angekommen heißt: es gibt die
`aufnahme`-Zeile mit dieser `message_id`, oder `aufnahme.empfange` hat den
Vorfall `download_fehlgeschlagen` geschrieben (`repo.web_segmente_unterwegs`,
`ANKUNFT_FRIST_S` = 60). Ohne (2) lief /fertig im Pool (`bot.POOL_GROESSE`)
parallel zum letzten Segment und konnte es überholen: `aufnahme.klasse_fuer`
liest den Modus erst bei der Verarbeitung, das Segment wurde ein
Gesprächsbeitrag. Die Endung im Update kommt aus der Spalte `mime`
(`web_kanal.MIME_ERLAUBT`, die eine Tabelle, die auch der Webserver nimmt).
Telegram ist davon nicht berührt — es liefert seine Updates selbst.

**Keine Nachzügler im Web** (Abschlussreview I4): `aufnahme.stelle_interview_sicher`
sammelt beim Anlegen eines Kopfes die `kurz`-Aufnahmen der letzten zehn
Minuten nur bei `kanal != 'web'` ein. Im Browser ist eine PTT-Nachricht
ausdrücklich „an den Bot", und Segmente gehen erst raus, wenn der Poll den
Modus meldet. Telegram bitgleich (Test).

**Ein Interview ist im Web EINE Blase** (04.10.2026, Karte t_ea994c7f,
nur mit `[interview] fliesstext = true` — gesetzt allein in
`workshop/padua-2026/profil.toml`, Zugriff `workshop.interview_fliesstext()`).
Statt „Interview N, Teil K:" je Sprachnachricht schreibt jeder fertige Teil
dieselbe Blase weiter: `aufnahme._sende_transkript_blase` baut den Text
bei **jedem** Teil neu aus `repo.hole_teile` (Kopfzeile `🎙 Interview N`,
dann alle Teile mit Transkript, je durch eine Leerzeile), legt die Blase
beim ersten Teil mit `tg.sende(..., transkript=True)` an
(`web_post.typ = 'transkript'`, kursiv in der Chatansicht) und merkt ihre
id am Kopf (`aufnahme.echo_message_id`, ueberlebt einen Neustart); danach
nur noch `tg.aendere_text`. Eine Sperre je Kopf
(`aufnahme._blasen_sperre`) verhindert zwei Blasen, wenn zwei Teile im Pool
gleichzeitig fertig werden. In `nachricht` steht die Blase einmal, beim
Anlegen — spaetere Aenderungen ziehen dort nichts nach (die Wahrheit ist
`aufnahme.transkript`). Mit demselben Schalter gehen „Aufnahme beendet.",
die Abschlusszeile und „… war sehr kurz …" als Systemzeilen raus
(`system=True` an `knoepfe.biete_aufnahme`/`biete_nach_aufnahme`).
**Telegram bleibt beim Echo je Teil samt Leiste, auch mit Schalter**
(`aufnahme.fliesstext_aktiv` = Schalter **und** `ist_web_gruppe`). Nicht
gebaut: einen Teil loeschen und die Blase neu aufbauen (es gibt keinen
Loeschweg; der Neuaufbau aus `hole_teile` machte ihn spaeter einfach),
Telegram-Folgeblasen ueber 4096 Zeichen, eine „…"-Zeile waehrend der
Transkription. Unabhaengig vom Schalter laeuft die Abschlusszeile im Web
seither ueber die Sprachschicht (`_TEXT_GESPEICHERT_WEB` & Co.) — Padua
liest sie englisch, Deutsch ist zeichengleich.

**Der Offset hängt am `bot_name`, nicht am Kanal** (Abschlussreview I2). Ein
Bot, der vorher Telegram fuhr, bringt eine getUpdates-Position um 10^8 mit
und hörte im Web nie etwas. `scripts/web_gruppe.py` setzt den Offset deshalb
auf 0, und `bot.baue_kanal` setzt ihn im Web-Kanal laut geloggt zurück, wenn
er hinter `repo.hoechste_web_post_id` liegt (bereits Gesehenes fängt die
Duplikatprüfung). `web_post.id` trägt `AUTOINCREMENT`, damit der Löschweg
einer Gruppe keine ids zur Wiedervergabe freigibt; eine schon angelegte
Entwicklungs-DB behält ihre Tabelle (`CREATE TABLE IF NOT EXISTS`),
`hoechste_web_post_id` fällt dort auf `MAX(id)` zurück.

**Bot-Ausgaben tragen Telegram-HTML** (`parse_mode="HTML"`, u. a.
`vorschlag.menuetext`). `web_chat.sichere_html` maskiert deshalb **alles** und
lässt dann eine geschlossene Liste wieder zu — `b i u s code pre blockquote`
und `a` mit `http`/`https`. In dieser Richtung, nicht in der anderen: ein
Filter, der `<script>` entfernt, ist eine Liste von Dingen, an die jemand
gedacht hat. Gefiltert wird **serverseitig** (auch im Poll); ein Filter im
JavaScript läge auf der Seite, die er schützen soll.

**Ein Knopfdruck wird gegen die hängende Leiste geprüft**
(`web_chat.knopf_erlaubt`), nicht gegen `knopf.message_id`: die ist nur
gesetzt, wenn ein Aufrufer `repo.merke_knopf_nachricht` ruft, und das tut nur
ein Teil der Sendestellen — `knoepfe.biete_einstieg` zum Beispiel nicht.
Geprüft wird gegen `web_post.knoepfe`, das `WebKanal.sende_mit_knoepfen`
selbst schreibt; es **ist** per Konstruktion, was gerade hängt. Steht `data`
dort nicht, gibt es 400 und **keinen Eingang** — sonst wäre jeder Knopf jeder
Gruppe per `curl` drückbar, sobald jemand einen Link hat, und die `k:<id>`
sind fortlaufende Zahlen. Die Wirkung macht danach `knoepfe.behandle` im
Bot-Prozess, unverändert: **kein zweiter Knopf-Handler**, und die Idempotenz
bleibt `repo.beanspruche_knopf` (Zusage 3).

**Audio im Browser sind ZWEI getrennte Knöpfe** (Birk, 30.09.2026,
verbindlich — **kein** Schieben-zum-Sperren, ein Test sucht das Wort im JS):

1. **Interview-Aufnahme**, ein Umschalter: einmal tippen = läuft, erneut
   tippen = Stopp, mit Timer, Pegel (`AnalyserNode`) und großem Stopp-Knopf.
   Er schaltet den Interviewmodus über die vorhandenen Befehlswege
   `/interview` und `/fertig` (POST `chat/interview`) — **keine zweite
   Moduslogik**, denn die Klasse einer Aufnahme hängt allein am Modus
   (`aufnahme.klasse_fuer`). Hochgeladen wird in **Segmenten von 45 Sekunden**
   (`IT_WEB_SEGMENT_MS`, Vorgabe `einstellungen.VORGABE_SEGMENT_MS`): Netz weg
   oder Tab zu verliert höchstens das letzte Segment, nie das ganze Interview.
   **Jedes Segment ist ein eigener MediaRecorder-Lauf** (`stop()` +
   `start()`), nicht eine Zeitscheibe: `start(timeslice)`-Stücke sind einzeln
   nicht dekodierbar, nur das erste trägt den Container-Kopf.
2. **Push-to-Talk** für Sprachnavigation, neben dem Textfeld: halten =
   sprechen, loslassen = senden, Klasse `kurz` (der Modus wird nicht
   geschaltet). Pointer Events mit `setPointerCapture`, je Druck ein eigenes
   Objekt; **unter 500 ms Haltezeit (`web_chat.PTT_MIN_MS`) wird verworfen**,
   und `pointercancel`, `lostpointercapture` oder Loslassen außerhalb des
   Knopfs senden **nichts**. Wird losgelassen, bevor `getUserMedia` das
   Mikrofon liefert, startet gar kein Recorder. Während eine
   Interview-Aufnahme läuft, ist PTT ausgeblendet, und ein Interviewstart
   verwirft einen gerade gehaltenen PTT-Druck — zwei Mikrofone gleichzeitig
   sind keine Bedienung.

**Die Warteschlange im JS ist der Kern der Audio-Seite** (Aufgabe 11 samt drei
Review-Runden). **Eine** sequentielle Schlange für Befehle (`/interview`,
`/fertig`) **und** Audio (Segmente, PTT): die Reihenfolge beim Bot ist die
Reihenfolge der Aufnahme. Ein Auftrag bleibt vorn, bis er 2xx bekommt;
Netzfehler, 5xx, 408, 429 und 403 werden **ohne Höchstzahl** wiederholt
(Abstand `UPLOAD_WARTEN_MS` = 1/3/8 s, das `online`-Ereignis löst sofort aus),
nur ein endgültiges 4xx verwirft — sichtbar, mit dem Servertext in `#fehler`.
Segmente tragen eine laufende Nummer und werden strikt in dieser Reihenfolge
eingereiht, auch wenn ein späteres `onstop` früher feuert. Daran hängen vier
Regeln:
- **Sofort aufnehmen, später hochladen.** Die Aufnahme startet sofort (sonst
  fehlen die ersten Worte), das erste Segment wartet aber, bis `/interview`
  dieser Aufnahme angenommen ist **und** der Poll einmal `interviewmodus`
  meldet — sonst machte `aufnahme.klasse_fuer` daraus eine `kurz`-Aufnahme.
  Danach rastet eine **Sperrklinke je Aufnahme** ein (`sitzung.bestaetigt`).
  Läuft der Bot gar nicht, warten Segmente und `/fertig` sichtbar
  (`_TEXT_WARTE_MODUS`) — ohne Bot gibt es keinen Ort für sie.
- **`/fertig` erst nach dem letzten Segment.** Es wird erst eingereiht, wenn
  der letzte Recorder sein `onstop` hatte — sonst verdichtet der Bot ein
  Interview, dem das letzte Segment fehlt. Ist der Servermodus schon aus
  (anderes Telefon, Erkenner), wird es nicht mehr gesendet.
- **Modusende hält an, statt still nachzuschicken.** Endet der Interviewmodus
  serverseitig, während dieses Telefon noch aufnimmt oder Segmente offen hat,
  stoppt die Aufnahme, die offenen Segmente werden **geparkt** (auch eines,
  dessen Upload erst danach scheitert), und die Gruppe entscheidet:
  „Rest als Interview nachreichen" (`/interview`, die Segmente, `/fertig` —
  nur, solange kein anderes Interview läuft, `_TEXT_NACHREICHEN_SPAETER`) oder
  „Rest verwerfen". Ohne Modus wäre ein 45-s-Segment ein Gesprächsbeitrag,
  und Gesprächszug, Erkenner und Journal liefen über Interviewmaterial.
  **Vorläufige Voreinstellung, die Entscheidung liegt bei Birk.**
- **Das Mikrofon wird freigegeben** (Tracks gestoppt, `AudioContext.close()`)
  nach jedem Interview-Ende, jedem PTT-Druck und in jedem Fehlerzweig; und
  `beforeunload` warnt bei laufender Aufnahme, gehaltenem PTT, voller Schlange
  oder geparkten Segmenten.
Der Leer-Schutz ist der vorhandene (`aufnahme._TEXT_LEER_VERWORFEN`). **Zwei
bekannte Grenzen, bewusst offen:** `fetch` hat kein Timeout (ein hängender
Upload hält die Schlange, bis der Browser aufgibt), und eine Wiederholung nach
Netzfehler kann einen schon angekommenen Upload doppelt anlegen (keine
Idempotenz-Kennung); PTT nimmt erst nach `getUserMedia` auf, der Anfang kann
fehlen.

**Die Endung entscheidet über den MIME-Typ** (Falle 3, und hier war die eine
Stelle, die dafür angefasst werden musste): `web_kanal.MIME_ERLAUBT`
(= `web_chat.MIME_ERLAUBT`, eine Tabelle an einer Stelle) ist eine
Allowlist **Content-Type → Endung** (`audio/webm` → `.webm`, `audio/mp4` →
`.m4a` für Safari, dazu `audio/ogg` und `audio/mpeg`), die Datei landet mit
dieser Endung unter `IT_AUDIO/<chat_id>/web-eingang/`, und
`telegram.lies_nachricht` trägt sie als neuen, optionalen Schlüssel `endung`
weiter, den `aufnahme.empfange` in den Zielpfad setzt. Ohne das bekäme ein
WebM den Pfad `<message_id>.ogg` und damit `audio/ogg`. Telegram nennt keine
Endung; dort bleibt es bei `aufnahme.ENDUNG_VORGABE` (`.ogg`), bitgleich wie
vorher. Größengrenze je Segment: **8 MiB** (`MAX_AUDIO_BYTES`) — gerechnet
aus Opus 32 kbit/s ≈ 180 KiB je 45 s mit zwanzigfacher Luft, und klar unter
`stt.MAX_UPLOAD_BYTES` (25 MiB).

**Betrieb:** dieselbe Unit-Vorlage, dasselbe `scripts/betrieb-start.sh`,
derselbe Profil-Check — ein Web-Bot unterscheidet sich allein durch
`IT_KANAL=web` und `IT_WEB_CHAT_ID` in `betrieb/<gruppe>.env`.
`IT_BOT_TOKEN` ist dort nicht Pflicht. **Zwei Variablen gehören dagegen
(auch) in die Web-Unit**, weil der Webserver keine `Einstellungen` lädt und
selbst aus seiner Umgebung liest: `IT_WEB_SEGMENT_MS` (die Seite gibt den Wert
an den Browser weiter — in der Env eines Bots wirkt er auf den Browser
nicht) und `IT_AUDIO` (der Webserver legt die Uploads dort ab, und
`WebKanal.lade_datei` verweigert jeden Pfad außerhalb des **eigenen**
`IT_AUDIO` — Web-Unit und Web-Bots müssen aufs selbe Verzeichnis zeigen;
beide laufen im Repo-Verzeichnis, Vorgabe `audio`). Die Web-Unit setzt
`IT_AUDIO` deshalb ausdrücklich (`docs/interview-theater-web.service`), der
Webserver speichert den Upload-Pfad **absolut** und nennt das Verzeichnis
beim Start in `betrieb/web.log` (Abschlussreview I5).

**Abnahme:** `tests/test_web_e2e_http.py` fährt eine Gruppe per HTTP von
Phase 1 bis zum ersten Interview (`bot.schleife` mit `WebKanal` und ein echter
Webserver; Attrappen nur für Sprachmodell und Whisper). `tests/e2e/test_web_chat_e2e.py` (Playwright, 29 Tests,
Fakes für `getUserMedia`/`MediaRecorder`) prüft im Browser Segmente,
PTT-Abbruch, Warteschlange, Modusende und das Handy-Bild; der Screenshot
`docs/web-chat/handy-2026-09-30.png` wird nur mit
`IT_SCHUSS_AKTUALISIEREN=1` überschrieben. Ohne Playwright wird die Datei
übersprungen.

**Was bewusst fehlt** (siehe „Was bewusst fehlt" unten): ein QR-Code zum
Link, die englischen UI-Texte, die Härtung (Rate-Limit, Nonce in der Query)
und die Kennzeichnung des Transkript-Echos — die Härtung macht die Karte
„Absicherung Web".

### Fassungen umschalten (07.09.2026)

Die Szenenübersicht trägt je Szene einen Zähler („3 Fassungen"), der auf die
Szene zeigt; im Szenenblock steht dann eine Leiste mit einer Nummer je
Fassung, **genau ein** Text und darunter der Link auf die vorige. **Rein
serverseitig** über `?szene=<id>&fassung=<n>` (`web.fassungswahl`,
`web.fassungslink`) — kein neues Framework, kein JavaScript, kein POST, und
**keine Änderung am Auth-Modell**: das Token steht weiter im Pfad, nicht in
der Query. Das sanfte Nachladen holt `location.href` samt Query, die Auswahl
überlebt also den Austausch des `<body>`; der Anker `#szene-<id>` bringt den
Browser an die Szene zurück, die deshalb bei einer Auswahl serverseitig `open`
bekommt. **Read-only**: eine frühere Fassung wieder in Kraft zu setzen ist
eine Entscheidung der Gruppe und gehört in den Chat, wo die Knöpfe darunter
hängen — `web_schreiben.FELDER` kennt kein Feld dafür. Auch hierfür genügt ein
Neustart von `interview-theater-web.service`; die Bots brauchen einen nur, weil
`szene.schreibe` die neuen Zeilen anlegt.

### Die Gestaltung (01.10.2026, Padua)

Alles Gestalterische liegt in **einem** Modul (`web_gestalt.py`) und wird
an neun Zeilen eingehaengt (gezaehlt am 03.10.2026): sechs in
`web_vereint.seite` (Rahmen-CSS, drei gescopte Bloecke, `css_interview()`
nur mit Chat, dazu das Effekt-JS), je eine in `web.textbuch_html` und
`web.leitfaden_html` und eine in `web.dashboard_html` (`tokens_css()` +
`css_dashboard()`, nur mit Profilschalter, siehe unten). Dazu seit der
read-only Werkbank eine zehnte, ebenfalls in `web_vereint.seite`
(`css_werkbank()`, nur mit `[web] workbench_bearbeitbar = false`). Es fasst **kein
Markup** an — was die Gestaltung zusaetzlich braucht, legt das Effekt-JS
zur Laufzeit an (alles mit dem Praefix `ux-`). **Zwei Ausnahmen**, beide
in `web.py` (Nacharbeit 03.10.2026): (1) `web.gruppe_koerper` stellt „Was
noch fehlt" vor die Formulare des Arbeitsstands, statt dahinter — eine
Umstellung, kein neues Element (Test
`test_was_fehlt_steht_vor_den_formularen_des_arbeitsstands`); (2) das
Team-Dashboard bekommt **neues Markup** (`_fortschritt_html`,
`_achtung_html`, `_dashboard_inhalt_html`: Akt n/7 mit sieben Segmenten,
der Hinweis „Needs attention", die gekappte Karte) — aber **nur hinter dem
Profilschalter `[web] dashboard_gestaltet`** (gesetzt allein in
`workshop/padua-2026/profil.toml`); ohne ihn bleibt das Dashboard-HTML
byte-gleich (`tests/test_web_dashboard_en.py`). Seit 04.10.2026 kein
Abnahmekriterium mehr, wenn die Abweichung nur Dortmund betrifft — siehe
„Dortmund eingefroren" oben; Test ggf. `@pytest.mark.dortmund`. Seit dem
04.10.2026 trägt `css_buehne()` (`_BUEHNE`) auch die ruhende Darstellung der
Schärfungskette (`.begriffsboard .vorgaenger`, Pfeil per `::before`) —
**ohne** Bewegung im CSS; die setzt `ladeBuehne()` per CSSOM und nur ohne
`prefers-reduced-motion`. Keine neue Einhängezeile, kein neuer Schalter.

**Ein Block Design-Tokens ist der ganze Entwurf.** `TOKENS["a"]`
(„Terminal zuerst": Phosphor auf Schwarzblau, Monospace, Tableiste unten)
und `TOKENS["b"]` („Buehne zuerst": Amber auf Samtschwarz, Serife, Tabs
oben) tragen **dieselben Schluessel**; umgeschaltet wird ueber
`VORGABE_ENTWURF` oder `IT_UX_ENTWURF`, dazu vier benannte
Komponenten-Abweichungen (Tab-Ort, Knopfform, Akt-Moment, Skript-Satz).
Die klickbaren Muster, an denen entschieden wurde, liegen unter
`docs/ux-padua/entwurf-{a,b}.html`.

**Drei CSP-Regeln, die im Code stehen und nicht im Kommentar** (die
Richtlinie aus der Absicherungs-Karte hat `default-src 'none'`,
`script-src`/`style-src` nur mit Nonce und **kein `font-src`**):

1. **Kein Webfont, kein `@font-face`, kein `@import`, keine Fremdquelle** —
   System-Schriftstacks (`--schrift-lesen/-tech/-skript`). Ein
   eingebetteter Font waere geblockt, auch mit `data:`-URL.
2. **Kein `style="…"`-Attribut, kein `on…=`-Handler** im ausgelieferten
   HTML. Dynamische Werte gehen ueber **CSSOM**
   (`el.style.setProperty('--fortschritt', …)`) — das ist unter
   `style-src 'nonce-…'` erlaubt, `setAttribute('style', …)` waere es
   nicht. Ein Test misst das am fertigen HTML der vereinten Seite, der
   Probenansicht und des Leitfadens.
3. **`@keyframes` und `@media` nur in `css_rahmen()`.** Die drei anderen
   CSS-Funktionen laufen beim Aufrufer durch `web_vereint.scope_css`, und
   dessen Regex machte aus dem Rumpf eines `@keyframes` (`50% { … }`) eine
   gescopte Regel `.panel-chat 50%`.

**`prefers-reduced-motion: reduce` legt alles still**, und zwar mit
`!important` — die Animationen aus A2/W sind gescopt und damit
spezifischer als jede Regel dieses Moduls. Der Strom baut seinen Text
trotzdem stueckweise auf: das ist Information, keine Animation. **Kein
Zustand haengt an einer Bewegung**; jeder steht zusaetzlich im Text.

**Der Kontrast ist gerechnet, nicht geschaetzt.** `web_gestalt.KONTRAST`
ist die Tabelle der Paare, die die Gestaltung wirklich uebereinanderlegt;
`tests/test_web_gestalt_tokens.py` rechnet fuer **beide** Entwuerfe das
WCAG-Verhaeltnis nach (≥ 4.5 fuer Text, ≥ 3 fuer Bedienelemente). Wer eine
Farbkombination hinzufuegt, traegt sie dort ein — sonst prueft sie
niemand. `--linie` steht bewusst nicht darin (dekorative Haarlinie);
Raender, die einen Zustand tragen, benutzen `--rand`.

**Der Aufnahmeknopf ist das wichtigste Element** (Dortmund Tag 1: 13 von
20 Aufnahmen leer, ein Knopf 14× in 93 Sekunden gedrueckt). Vier
Zustaende, aus dem DOM abgeleitet und **ohne neuen Schluessel im
Zustands-Poll**: `ruht` → `startet` → `laeuft` → `laedt`. Jeder steht im
**Text** (zweite Zeile `#ux-rec-zeile` **neben** dem Knopf — `_CHAT_JS`
schreibt in den Knopf selbst), der laufende ist **groesser** als der
ruhende, und `:active` gibt die Rueckmeldung in unter 100 ms. Die
Gestaltung **sperrt keinen Druck**: dass `_CHAT_JS` waehrend eines
Uebergangs weiter auf Klicks reagiert, ist ein Logikbefund an der
Web-Chat-Karte und steht in `docs/ux-padua/BERICHT.md`.

**Der Ausdruck bleibt hell.** `css_rahmen()` traegt einen eigenen
`@media print`-Block, weil die Gestaltung im `<style>` **nach**
`_CSS_TEXTBUCH` steht — ohne ihn kaeme ein schwarzes Blatt aus dem
Drucker.

**Der Interview-Modus zeigt nur noch die Aufnahme** (03.10.2026,
`web_gestalt.css_interview()` und `_JS_INTERVIEW`). Erkannt allein am DOM:
`html[data-ux-interview="1"]`, solange `#fuss[data-interview="1"]` **und**
`#uhr` sichtbar ist — `data-interview` allein steht schon beim Druck und
auch dann, wenn ein anderes Telefon den Modus haelt. Im Modus fallen
Aktzeile, Tableiste, Verlauf, Eingabe, PTT und alle Effekte weg; es bleiben
ein zugeklappter Leitfaden (Text per `textContent` aus dem schon
ausgelieferten `pre.leitfaden`), eine grosse Uhr, der Pegel, eine kleine
Lampe statt des runden Knopfs, die Zustandszeile, „Pause" und **ein**
Hauptknopf „■ Beenden" unten in der Daumenzone. Das Chat-Panel ist im
Modus erzwungen sichtbar (ein Zurueck-Wischen auf `#stand` nahm sonst den
Stopp mit). Dazu ein **Wake Lock**: feature-detected, jede Ablehnung
geschluckt, angefordert beim Eintritt, freigegeben bei Modusende,
`visibilitychange` → hidden und `pagehide`, neu angefordert beim
Zurueckkommen. Er verhindert nur das automatische Sperren; was beim
Sperren von Hand, bei einem Anruf oder ohne Netz mit der Aufnahme
geschieht, steht als Befund an A2 in `docs/ux-padua/DESIGN-REVIEW.md`.
Ueber jedem Tab steht ausserdem eine Zeile „Als Nächstes: …"
(`_JS_NAECHSTES`), gelesen aus der ersten offenen Aufgabe der aktiven Phase
in der Aktfolge — kein neuer Serverschluessel.

**Das Team-Dashboard `/` ist nur im Padua-Profil gestaltet.** Der
Profilschalter `[web] dashboard_gestaltet` (Vorgabe `false`, `true` nur in
`workshop/padua-2026/profil.toml`) haengt `css_dashboard()` ein und stellt
die Karte um: Akt n/7 mit sieben Segmenten, ein Hinweis „Needs attention"
nur bei einem Problem (`web.ACHTUNG_VORFAELLE`, Fehlschlaege und Vorfaelle
der letzten 2 h, Kosten ab 80 % des Deckels, Web-Eingaenge, die der Bot seit
3 min nicht abgeholt hat), keine leeren Felder, kein Leitfaden, kein
Botname. Ohne Profil und mit `dortmund-2026` bleibt das HTML byte-gleich —
`tests/test_web_dashboard_en.py` haelt es fest. Seit 04.10.2026 kein
Abnahmekriterium mehr, wenn die Abweichung nur Dortmund betrifft — siehe
„Dortmund eingefroren" oben; Test ggf. `@pytest.mark.dortmund`. **Betrieb:** die
Kostenwarnung liest `IT_KOSTEN_DECKEL_CHF` aus der Umgebung des
**Webdienstes** (Vorgabe 5.0); `docs/interview-theater-web.service` setzt
die Variable nicht. Wer den Deckel in den Bot-Envs aendert, setzt ihn auch
dort, sonst warnt das Dashboard gegen die Vorgabe. Begruendungen je
Element: `docs/ux-padua/DESIGN-REVIEW.md`.

**Die Werkbank ist in Padua reine Anzeige** (03.10.2026, Karte
t_49e7354c, Birk: „Workbench reiner Status-Ausspieler. Änderungen passieren
über Chat."). Profilschalter `[web] workbench_bearbeitbar` (Vorgabe `true`,
`false` nur in `workshop/padua-2026/profil.toml`). Mit `false` ersetzt
`web.werkbank_koerper` den Rumpf von `gruppe_koerper`: EINE Achse, die
sieben Phasen in Reihenfolge, je ein `<details>` mit Zähler („4 of 5", ✓
wenn alles erledigt), aufgeklappt nur die aktuelle Phase, darunter je
Attribut ein Punkt in drei **Formen** — gefüllt mit Haken `--signal`
(erledigt), Ring `--warn` (offen, bis zur aktuellen Phase), gestrichelter
Ring `--text-leise` (später) — und ein `aria-label`; Roadmap-„läuft"
erscheint als offen plus Wort. **Eine Quelle:** `roadmap.werkbank` auf
derselben `lage` wie `roadmap.aus_daten`, `AUFGABEN` unverändert; die
Detailzeilen (Diskussion, je Interview, je Szene Prosa/Überarbeitung/Form,
je Figur Sprechweise) lesen nur, was `web_daten.werkbank` read-only lädt.
`fehlstellen.py` bleibt für `/stand` und Dortmund; in Padua sind die
offenen Punkte die Liste. Kein Formular, kein `_BEARBEITEN_JS`, kein
Probenansicht-/Chat-Link, keine Phasenanzeige im Panel; der Inhalt je
Phase kommt aus denselben Bausteinen wie vorher (`_interview_html`,
`_festlegungen_html` ohne Löschknopf, `_dramaturgie_html`,
`_sprechanteile_html`, `_leitfaden_html` — `pre.leitfaden` muss bleiben,
der Interview-Modus liest ihn). Der Werkbank-POST (`POST /g/<token>`)
antwortet dann **403**; die Chat-POSTs laufen weiter. Der Nonce steht in
Padua im Chat-Panel (`chat_koerper(mit_nonce=True)`); `friskeNonce()` findet
in `teil/stand` keinen mehr, der Chat-Poll hält ihn frisch. Das CSS
(`web_gestalt.css_werkbank`) ist die zehnte Einhängezeile, nur mit dem
Schalter `false`. Ohne Profil und mit `dortmund-2026` bleibt alles
byte-gleich — `tests/test_werkbank_bitgleich.py` gegen
`tests/fixtures/werkbank_vorher_*.html`. Seit 04.10.2026 kein
Abnahmekriterium mehr, wenn die Abweichung nur Dortmund betrifft — siehe
„Dortmund eingefroren" oben; Test ggf. `@pytest.mark.dortmund`. Grenze: die Einzelseite
`gruppe_html` (von keiner Route mehr ausgeliefert) zeigt die Punkte
ungestaltet. Screenshots: `docs/ux-padua/workbench/`.

### Eine Oberfläche je Gruppe (30.09.2026, Karte W)

`/g/<token>` ist seitdem **eine** Seite mit drei Tabs — **Chat** (der Ersatz
für Telegram, Karte A2), **Arbeitsstand** (die bisherige Gruppenseite, weiter
editierbar) und **Textbuch** (die Probenansicht). Alle drei liegen im
**selben Dokument**; umgeschaltet wird nur über `hidden`, nie über einen
Seitenwechsel — sonst risse jeder Tabwechsel die laufende Aufnahme, die halb
getippte Nachricht und den laufenden Stream mit. Der Tab steht als bloßes
Wort im Fragment (`#chat`, `#stand`, `#textbuch`), damit die Zurück-Taste des
Handys funktioniert und ein Link teilbar bleibt; ein Rollenlink der
Probenansicht behält dabei seine Form (`#textbuch&figur=Leyla`).

**Die alten Adressen leben weiter**, und das ist keine Höflichkeit: die
Probenansicht (`/g/<token>/textbuch`, `.md`, `.txt`) und der Leitfaden
(`/g/<token>/leitfaden`) bleiben **eigene** Seiten mit ihrem `@media print`
und ohne Nachladen — gedruckte QR-Codes und geteilte Rollenlinks dürfen nicht
sterben. `/g/<token>/chat` (Karte A2) leitet mit **302** auf `/g/<token>#chat`.

**Nachgeladen wird nur noch das Stand-Panel** (`/g/<token>/teil/stand`,
`web_vereint.sende_teil`), mit denselben zwei Sperren wie bisher (Fokus in
einem Feld, ungespeicherte Änderung) und **nur, wenn es sichtbar ist**.
`web._SCROLL_JS` steht weiter, aber die vereinte Seite lädt es nicht: es
tauscht `document.body.innerHTML`, und daran hängen Recorder, Eingabefeld und
Strom.

**Das CSS wird zur Laufzeit eingeschränkt** (`web_vereint.scope_css`), die
bestehenden Konstanten bleiben Zeichen für Zeichen. Gemessen am 30.09.2026
kollidieren `_CSS_GRUPPE` und `_CSS_TEXTBUCH` in `body` und `h1`, und
`.leiste` heißt im Textbuch die Rollenleiste und im Chat die Knopfleiste; die
Probenansicht hängt ihren Zustand außerdem an `<body>`, was im gemeinsamen
Dokument den Chat mitfärben würde (deshalb `data-textbuch` als Wurzel).

**Das Team-Dashboard `/` bleibt unverändert** — es hängt am Beamer, es zeigt
alle Gruppen, und es ist nicht diese Karte. (Gestaltet wurde es später von
der UX-Karte Padua, und nur hinter dem Profilschalter
`[web] dashboard_gestaltet` — siehe „Die Gestaltung".)

**Ein vierter Tab braucht nur drei Stellen.** `web_vereint.TABS` ist die
EINE Liste, die Tableiste, Panel-Schleife und das Hash-Routing im Browser
treibt (sie geht als `__TABS__` in `_VEREINT_JS` ein) — der inzwischen
gebaute „Bühne"-Tab (CoThinker, Phase-4-Regiekarten, seit 04.10.2026 auch
Phase 1, siehe oben) brauchte dafür nur einen Eintrag in `TABS`, eine
Beschriftung in `_TEXT_TAB` (plus ihre englische Fassung in
`sprachen/en/texte.toml`) und einen Panel-Rumpf im `panels`-Dict von
`web_vereint.seite` — sonst nichts.

### Die Phasenübersicht (30.09.2026, Karte W)

Oben auf der vereinten Seite, **eine Zeile hoch**: „Phase N von 7 · Name —
2/4". Per `<details>` aufklappbar zur vollen Liste aller sieben Phasen mit
ihren Aufgaben (✅ erledigt · ⏳ läuft · ⬜ offen) — **ohne JavaScript
benutzbar**. Auf einem Telefon ist der Chat die Arbeitsfläche; eine dauerhaft
aufgeklappte Liste nähme ein Drittel des Bildschirms für etwas, das man
dreimal am Tag braucht.

Die Daten kommen aus `roadmap.aus_daten` — **rein**, kein Modellaufruf, und
die Aufgabenliste ist per Test an `phasentexte.PARAMETER` genagelt: eine
zweite, frei erfundene Wunschliste wäre der erste Stand, der ausschert
(dieselbe Regel wie bei `fehlstellen`). **'läuft' zeigt nur, was in der
Datenbank steht** — Interviewmodus, `gruppe.web_tippt_bis`, eine laufende
Zeile in `web_strom`; ein Szenenlauf-Lock lebt im Bot-Prozess und ist für den
Webserver unsichtbar. Ein Klick auf eine **Aufgabe** springt zu ihrer Stelle
(Tab + Feld) und setzt **nichts**; ein Klick auf eine **Phase** schaltet um
(siehe Phasenregel oben).

### Der Strom (30.09.2026, Karte W)

Birk: „die website soll die llm antworten streamen können." Gestreamt werden
**Gesprächszug, Auftragszug, Szenenlauf und Prosalauf** — alles, dessen
Ergebnis ein Mensch liest. **Nicht** gestreamt werden Erkenner, Journal,
Verdichter, Sprachprofil, Schärfung, Szenenfolge-Vorschlag und Dramaturgie:
ihr Ergebnis liest eine Maschine.

**Der Gesprächszug ist dabei ein Schema-Aufruf** (`ablauf.SCHEMA`,
`{"antwort": string}`) — was ankommt, ist ein wachsender JSON-Präfix, kein
Text. `strom.wert_aus_praefix` dekodiert daraus den bisherigen Wert, samt
halbem Escape, halber `\uXXXX`-Folge und halbem Surrogatpaar. **Kein Prompt
und kein Response-Format ändert sich dafür** — der Korpus gilt unverändert.

Der Weg: das Modell wird im **Bot**-Prozess gerufen, der Browser hängt am
**Web**-Prozess; dazwischen liegt die Tabelle `web_strom` (eine Zeile je
laufendem Aufruf, `zustand` läuft/fertig/abgebrochen, `post_id` der fertigen
Nachricht). Der Bot schreibt gedrosselt (`strom.INTERVALL_S` = 0,15 s), der
Webserver liest read-only und schickt die Deltas per **SSE** über
`GET /g/<token>/chat/strom` (`text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, `Connection: close`, Keepalive alle 15 s, Ende nach
`STROM_MAX_S` = 300 s). **Karte A2 sagt „kein SSE" — diese eine Route ist die
Ausnahme**, für alles andere bleibt der Poll.

**Was sichtbar streamt, ist schon gesäubert:** `strom.sichtbar` nimmt die
VORSCHLAG-Markerzeilen heraus, auch die halb getippte. **Kein halber Text wird
je eine Nachricht:** reißt der Anbieterstream nach dem ersten Stück ab, geht
die Zeile auf `abgebrochen`, die vorläufige Blase verschwindet, und **genau
ein** Wiederholungsversuch ohne Stream holt die vollständige Antwort — eine
Buchung, nicht zwei. Lehnt der Anbieter `stream` ab oder liefert keine
`usage`, fällt der Prozess still auf den blockierenden Weg zurück und
vermerkt das **einmal** (`strom_nicht_verfuegbar`), damit der Kostendeckel
nicht dauerhaft auf Schätzungen steht. **Der Telegram-Weg bleibt unangetastet**:
`telegram.Telegram` hat kein `strom`, und ohne `bei_teil` ist jeder
Anbieteraufruf zeichengleich wie vorher (Test).

**Betriebshinweis nginx:** ohne `proxy_buffering off;` (oder mit einem Proxy,
der `X-Accel-Buffering` ignoriert) kommen die Teilstücke am Stück an. Die
nginx-Konfiguration liegt nicht im Repository; gemessen wird sie mit
`curl -N <URL>/g/<token>/chat/strom`.

**Ob der Gesprächszug wirklich streamt** (ANNAHME 4: Infomaniak akzeptiert
`stream` zusammen mit `json_schema` und liefert `usage` mit), misst erst ein
echter, bezahlter Lauf: `python -m scripts.strom_probe --bericht` (kein Test,
kostet Geld), Bericht unter `docs/web-vereint/strom-probe-<datum>.md`. Das
Skript steht seit `1e0f9ec`; der Lauf selbst steht zum Stand dieser Karte
noch aus — die Betriebszugänge dafür lagen dieser Session nicht vor.

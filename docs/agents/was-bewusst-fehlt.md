# Was bewusst fehlt

> Ausgelagert aus `AGENTS.md` am 05.10.2026 (Stand `cb200e4`, Zeilen 3521–3707 und 1802–2075).
> Wortlaut unveraendert; Index und Kurzfassung stehen in `AGENTS.md`.

## Was bewusst fehlt

- **Hartes Löschen im Chat.** Entfernt wird nur weich, und Material
  (Aufnahmen, Transkripte, Verdichtungen) gar nicht — der vollständige
  Löschweg bleibt `scripts/loeschen.py`, von Hand, mit Rückfrage.
- **Freies Schreiben über die Weboberfläche.** Die Gruppenseite ändert seit
  dem 05.09.2026 abends eine kleine, feste Liste von Parametern (siehe
  „Weboberfläche"); alles darüber hinaus — Material, Szenen-Volltext,
  Journal — bleibt Sache des Chats.
- **Der automatische Phasensprung.** Er hat einmal existiert
  (`ART_ERMOEGLICHT`, `sprung_nach`) und ist am 05.09.2026 **bewusst und
  ersatzlos** gestrichen worden, nicht aus Zeitmangel: **Datenstand ist nicht
  Absicht** — eine fertige Verdichtung sagt nicht, ob noch drei Interviews
  kommen, und ein gesetztes Kernthema sagt nicht, dass die Gruppe damit
  fertig ist. Geblieben ist die Frage (`phasen.moegliche_naechste` /
  `offenes_angebot`): erlaubt die Materiallage eine höhere Phase, bietet der
  Bot sie im Fluss an, gesetzt wird sie nur von der Gruppe.

- **Phase 6 ist EINE Kurzgeschichte, nicht fünf Szenenläufe** (06.09.2026,
  Birk 11:50, `kurzgeschichte.py`). Ein Opus-Lauf schreibt aus Setting,
  Figuren (mit `figur.sprachstil`) und der gewählten Geschichte eine
  zusammenhängende Kurzgeschichte. Danach werden die Abschnitte zu Szenen —
  `nummer`, `titel` = Überschrift, `prosa` = Abschnittstext, `was_passiert`
  aus der Pflichtzeile `Zusammenfassung:`, `ort`/`zeit`/`anlass` aus dem
  Setting (`szene.rahmenfelder`), **`form` bleibt NULL** (die entscheidet
  der Feinschliff). Die bestehende Szenenfolge wird dabei **abgeglichen, nicht
  ersetzt** (`repo.gleiche_szenenfolge_ab`: gleiche Nummer → aktualisieren,
  fehlende → ergänzen, überzählige → stehen lassen), das Journal hält die
  Herkunft fest. Keine Herkules-Zahlen in `formen/prosa.md`.
  **Wie viele Abschnitte, entscheidet die Szenenfolge** (Birk, 02.10.2026,
  Karte P2-Fix): steht eine, bindet ihre Zahl — ein Abschnitt je geplanter
  Szene, in deren Reihenfolge. Genannt wird sie im **Auftrag**
  (`kurzgeschichte.abschnittszahl` → `_ZEILE_ABSCHNITTE`); trägt der
  Nutzertext schon einen Längen-Block, nennt ihn dieser
  (`laengen.SATZ_BINDUNG`) — **nie beide**, ein Fakt hat genau eine Stelle
  im Prompt. Steht **keine** Szenenfolge, wählt das Modell die Zahl selbst
  (typisch 3–7); `kurzgeschichte.ANWEISUNG` formuliert genau diese zwei
  Fälle, weil eine Systemanweisung die Datenlage nicht kennt. Der Grund für
  die Bindung ist der Abgleich oben: bei zu wenigen Abschnitten bleiben
  prosalose Szenen stehen, und Phase 7 verlangt Prosa für **jede** geplante
  Szene (`phasen.voraussetzungen`) — ohne Vorfall und ohne Zeile im Chat.
  **Das ist die bekannte Grenze dieses Wegs** (Befund
  `docs/prompt-audit/2026-10-02-padua-p2/BEFUND.md`): verfehlt das Modell
  die bindende Zahl trotzdem, räumt niemand auf.
  Die Zerlegung selbst hängt an keiner Zahl — ein Test misst das
  (`test_teil4_kurzgeschichte`: vier Überschriften → vier Szenen, sechs →
  sechs; dort ist **keine** Szenenfolge angelegt, also genau der freie Fall).

- **Der Prosa-Lauf startet nur aus einem Knopf, und die USA-Frage steht beim
  Eintritt in Phase 6** (06.09.2026, Birk 12:25). Beim Eintritt kommen
  Einleitung und — einmal je Gruppe, **vor** dem ersten Lauf — die
  USA-Einwilligung als eigene Nachricht mit genau „Ja, US-Modell" / „Nein,
  Schweiz"; erst nach der Antwort steht der Knopf „Geschichte schreiben".
  Vorher kam die Frage mitten aus dem Szenenlauf, wenn die Gruppe schon
  wartete, und der Lauf brach dafür ab. Der Gesprächs-Bot löst **nie** einen
  Lauf aus: eine Antwort mit „Start frei", „ich schreibe die Szene aus",
  „US-Server"/„Schweiz" ohne laufenden Lauf wird verworfen
  (`ablauf.ist_erfundene_systemzeile`, Vorfall
  `gespraech_systemzeile_erfunden`), und `system.md` verbietet die Ansage.

- **Was fehlt, steht neben dem, was dasteht** (06.09.2026,
  `fehlstellen.py`). `/stand` und die Gruppenseite zeigten bis dahin nur den
  gefüllten Arbeitsstand; woran die Gruppe als nächstes arbeiten müsste,
  musste sie sich aus sieben Blöcken mit „noch offen"-Zeilen selbst
  zusammenreimen. Das Register dreht dieselbe Datenlage um und liefert je
  Fehlstelle `bereich`, einen deutschen Satz, `szene`/`figur` wo zutreffend
  und die Phase, in der das dranwäre. **Reine Leseabfrage, kein
  Modellaufruf**, wie `phasen.voraussetzungen` — und geprüft wird genau das,
  woran der Code schon hängt (`phasen.voraussetzungen`,
  `szene.PFLICHTFELDER`, `aufnahme.unausgewertete_interviews`,
  Ebene 2 der Figuren erst ab Phase 5 wie in `knoepfe.ebene2_erlaubt`); eine
  zweite, frei erfundene Wunschliste wäre der erste Stand, der ausschert.
  Ausgespielt wird an genau **zwei bestehenden Orten** — ein Abschnitt in
  `/stand` und einer auf der Gruppenseite —, **nur wenn es Fehlstellen
  gibt** (eine Zeile „nichts fehlt" ist Lärm), höchstens `HOECHSTENS` = 8
  Zeilen. Kein neuer Knopf, keine eigene Bot-Nachricht. Auf der
  Gruppenseite steht der Abschnitt seit dem 03.10.2026 direkt nach dem
  Überblick und **vor** den Formularen des Arbeitsstands (UX-Karte Padua,
  `web.gruppe_koerper`) — vorher kam man am Telefon erst nach rund zwei
  Bildschirmen Formularen dort an. Sortiert wird nach
  Arbeits-, nicht nach Phasenreihenfolge: erst die aktuelle Phase, dann der
  Rückstand aus früheren (er blockiert), dann das Kommende. Wie beim
  Leitfaden gibt es **einen Zusammenbau und zwei Aufrufer**: `aus_daten` ist
  rein und kennt nur Dicts, `register` holt sie über `repo`,
  `web_daten.fehlstellen` über die read-only geöffnete Verbindung — der
  Webserver bekommt dadurch keinen `repo`-Pfad.

- **Der Leitfaden hat eine eigene Seite** (06.09.2026, Route
  `/g/<token>/leitfaden`, auch unter `IT_WEB_PREFIX`). Der gebaute Leitfaden
  ging einmal in den Chat und versank — dabei ist genau er das Dokument, das
  eine Sechzehnjährige in der Hand hält, wenn sie eine fremde Person
  anspricht. Die Seite ist **rein lesend**: kein Nachladen, kein POST, kein
  Nonce, und deshalb auch nicht der Rahmen der beiden anderen Seiten
  (`web._seite` hängt das sanfte Nachladen an, das einer Interviewerin mitten
  im Gespräch den Text unter dem Daumen austauschen würde). Groß gesetzt,
  hoher Kontrast, jede Frage in einem eigenen Block, dazu eine
  `@media print`-Regel. **Keine zweite Wahrheit:** Route und Chat-Text stehen
  beide auf `leitfaden.bausteine` — `aus_feldern` setzt daraus den Chattext,
  `web.leitfaden_html` die Handy-Ansicht. `web_daten.leitfaden_nach_token`
  lädt bewusst **nur** den Arbeitsstand und weder Szenen noch Interviews noch
  Journal: was gar nicht geladen wird, kann auch nicht versehentlich
  ausgeliefert werden (Test wie der bestehende in `tests/test_web.py`: kein
  Transkript, kein Nachrichtentext im HTML). Verlinkt an zwei Orten —
  auf der Gruppenseite unter dem Leitfaden-Text (relativ,
  `<token>/leitfaden`, damit es hinter nginx genauso geht) und im Chat unter
  dem Leitfaden selbst (`leitfaden.TEXT_WEBLINK`, **zusätzlich**; der
  bestehende Text bleibt, weil eine Gruppe ohne Netz im Probenraum sonst
  nichts mehr hätte). Steht noch kein Leitfaden, kommt eine ruhige Seite
  („Der Leitfaden entsteht in Phase 2.") statt eines Fehlers. Dafür nehmen
  `leitfaden.sende`/`sende_einmal` seit heute ein optionales `e` entgegen —
  ohne Basis-URL steht die Zeile gar nicht da.

- **Eine Szene bekommt Fassungen, statt überschrieben zu werden**
  (06.09.2026, Tabelle `szenenfassung`). „Neu schreiben" ersetzte bis dahin
  `szene.volltext`; die Gruppe kam nicht zurück, und in der Probe will man
  zwei Fassungen nebeneinander lesen. Jeder **erfolgreiche** Szenenlauf
  (`szene.schreibe` und der Prosalauf in `kurzgeschichte.lege_szenen_an`)
  hängt seine Fassung **zusätzlich** an — `szene.volltext` bleibt genau wie
  bisher die aktuelle Fassung, **kein Aufrufer außerhalb ändert sich**.
  Dasselbe Prinzip wie beim Journal: **nur anhängen, nie ändern, nie
  löschen** — es gibt bewusst kein `aktualisiere_szenenfassung` und kein
  `entfernt_am`. Scheitert das Anhängen, ist die Szene trotzdem geschrieben:
  eine verlorene Historienzeile darf keinen bezahlten Lauf kosten. Migration:
  `db._migriere_erste_szenenfassung` gibt jeder bestehenden Szene mit
  Volltext **eine** Fassung Nummer 1 mit `szene.geaendert_am` als Zeitpunkt —
  idempotent über ein `NOT EXISTS` und ohne eigenen `user_version`-Schritt,
  damit auch eine später importierte Szene noch richtig durchläuft. Gezeigt
  wird sie an zwei Orten, beide **read-only**: die Fassungsleiste je Szene auf
  der Gruppenseite (seit dem 07.09.2026 zum Umschalten, siehe unten) und ein
  Knopf „Fruehere Fassungen" unter einer angesehenen Szene
  (`knoepfe.ART_FASSUNGEN`, deterministisch, Zusage 2 gilt) — der Knopf zeigt
  die **aktuelle** Fassung nicht noch einmal, und beide fehlen ganz, solange
  es nur eine gibt. **Zurücksetzen auf eine frühere
  Fassung ist bewusst nicht gebaut:** das ist eine Entscheidung mit
  Datenwirkung, die Birk erst freigeben muss. `szene.fruehere_fassungen`
  (der `FASSUNGSTRENNER`-Text aus `repo.hebe_fassung_auf`) bleibt daneben
  unverändert stehen — er ist der ältere, gröbere Weg und wird von der neuen
  Tabelle nicht angefasst.

- **Sprechanteile sind gezählt, nicht geschätzt** (06.09.2026,
  `sprecher.py`). Der praktisch wichtigste Befund für eine Laiengruppe stand
  nirgends: eine Spielerin mit vier Zeilen merkt das in der Probe, und dann
  ist der Text geschrieben. Gezählt wird über `szene.volltext` — den
  Theatertext, nicht die Prosafassung —, **kein Modellaufruf**. Die Regel für
  eine Sprecherzeile ist bewusst schlank: am Zeilenanfang ein Name, danach
  ein Doppelpunkt; ein Name gilt, wenn er in der Figurenliste steht oder
  durchgehend großgeschrieben ist. **Die Grenze steht im Docstring und in
  einem Test:** Namen mit Punkt (`FRAU K.:`) oder Komma (`MIRA, LEISE:`)
  werden nicht erkannt — sie mitzunehmen hieße, „Sie sagt: nein." als
  Sprecherzeile zu lesen. Eine Ziffer im Kopf schließt aus, gemessen an den
  echten Opus-Texten unter `docs/prompt-audit/2026-09-06/opus-thinking-texte/`:
  dort stand `SZENE 1: … ca. 10 min` über dem Text und zählte ohne diese
  Regel mit rund 30 Wörtern als Sprecher mit. **Erkennt eine Szene keine
  einzige Sprecherzeile, liefert sie gar nichts** (Lied, Rap und Chor können
  ohne Sprecherkopf geschrieben sein) und zählt auch nicht in den Nenner:
  lieber „1 von 4 Szenen" als eine erfundene Null. Regieanweisungen in runden
  Klammern zählen nicht als gesprochenes Wort. Ausgespielt auf der
  Gruppenseite als Tabelle (Figur, Anteil, Repliken, Szenen) mit einer
  sachlichen Hinweiszeile je Figur unter `SCHWELLE_ANTEIL` = 3 %, und im Chat
  als Zeile „Wer spricht wie viel" im Durchlauf-Knopfmenü
  (`knoepfe.ART_SPRECHANTEILE`, deterministisch, Zusage 2 gilt).
- **Was in kein Feld passt, geht in die Tabelle `festlegung` — nicht ins
  Journal** (06.09.2026, `docs/analyse-phase4-datenverlust-2026-09-06.md`).
  Der Befund: von 42 Festlegungen einer Gruppe in Phase 4 waren **22
  verloren**. Das Schema kennt nur einen festen Satz vorab definierter Slots;
  alles daneben — Gruppenzugehörigkeit einer Figur, ihre Herkunft, „nur eine
  Szene, erste Folge einer Serie", eine Längenvorgabe für Szenentexte —
  landete höchstens als `journal`-Eintrag und fiel nach `JOURNAL_EINTRAEGE`
  = 8 weiteren Zeilen aus dem Prompt, ohne je zurückzukehren.
  **Journal und Festlegung sind Chronik gegen Geltungsanspruch:** das Journal
  hält den *Weg* fest und wird gekappt, eine Festlegung *gilt* und geht
  vollständig mit. Beides in einer Tabelle zu mischen erzwingt genau die
  Kappung, die den Verlust erzeugt hat.
  Drei Schreibwege, einer davon die Rückfallebene: die Erkenner-art
  `festlegung_setzen` (der Regelweg), der versteckte Befehl `/festlegung
  <bereich>: <text>` (weil der Erkenner über ein Modell läuft, und das ist
  am 06.09. mitten in Phase 4 mit HTTP 5xx ausgefallen) und der Knopfweg für
  die Formwahl. Zurückgenommen wird über `entfernen` („Festlegung: …"),
  `/festlegung weg <suchwort>` oder den Löschknopf auf der Gruppenseite —
  **Pflicht, nicht Kür**: ohne ihn erbt die Tabelle den alten Fehler mit den
  veralteten Einträgen.
  Zwei Sperren gegen die **doppelte Wahrheit**: kein `bereich` heißt wie ein
  Arbeitsstandfeld (`repo.FESTLEGUNG_BEREICHE`), und ein Text, der in einem
  gesetzten Feld ohnehin schon steht, wird verworfen (Vorfall
  `festlegung_stand_schon_im_feld`) — das Gegenstück zu
  `erkenner._ist_geschichte` in der anderen Richtung. Im Prompt steht der
  Block **direkt hinter dem Arbeitsstand**, gedeckelt auf 20 Zeilen und 800
  Token, und gekappt wird **die jüngste Zeile zuerst**: anders als beim
  Journal, weil eine frühe Grundfestlegung mehr wiegt als eine späte
  Detailnotiz. Auf der Gruppenseite steht er **aufgeklappt** — das Journal
  war dort auch sichtbar und trotzdem unwirksam.
  **Der Erkenner-Korpuslauf für `festlegung_setzen` steht aus**
  (`korpus/erkenner.jsonl`, Fälle `fl01`–`fl09`).

- **Eine Menüzeile ist keine Geschichte** (06.09.2026, aus derselben
  Analyse). `knoepfe._speichere_geschichte` speicherte eine angetippte
  Auswahlzeile ohne Szenenzeilen als ganze Geschichte — die Absicht trägt
  aber nur, wenn die Zeile eine *Handlungs*richtung beschreibt. Live
  beschrieb sie eine **Formabfolge** über drei Szenen:
  `arbeitsstand.geschichte` trug 113 Zeichen Formwahl statt der 665 Zeichen
  langen, vierteiligen Handlung, und `szene.form` war in allen 15 Zeilen
  NULL. `szenenfolge.formabfolge` erkennt so eine Zeile eng — mindestens
  zwei verschiedene Formen, und strukturell verwendet (an „Szene N"
  gebunden oder als Kette „Chor-Dialog-Rap") —, und die Wahl wird
  **übernommen statt verworfen**: in `szene.form`, wo die Szene existiert,
  sonst als Festlegung im Bereich `form`. `form` und nicht `form_vorschlag`:
  die Regel „die Form ist ein Vorschlag" hält den Vorschlag eines Modells
  aus dem Feld heraus, nicht die Wahl der Gruppe — und hier hat sie
  gedrückt.

- **Eine nachbenannte Figur schluckt ihren Platzhalter** (06.09.2026, aus
  derselben Analyse). `figur` führte 16 Zeilen statt 10, drei Paare mit
  wortgleicher Beschreibung, keine weich gelöscht — und der Schaden war
  nicht die Dublette, sondern ihre Richtung: die im Chat erarbeiteten
  Sprachstile hingen an den **Platzhaltern**, die benannten Figuren hatten
  `sprachstil` NULL, und `szene_figur` verwies gemischt auf beide Seiten.
  `repo.fuehre_figur_zusammen` schmilzt sie zusammen — Stil, Profil, Zitate,
  Interviewzuordnung und Besetzung wandern auf den Namen, aber nur, wo der
  Name dort nichts hat; der Platzhalter bekommt `entfernt_am`.
  **Zusammenführen und nicht löschen**: den Platzhalter samt Stil
  wegzuwerfen wäre derselbe Verlust noch einmal. Ausgelöst wird es nur von
  einem **Platzhalternamen** mit wortgleicher Beschreibung
  (`repo.ist_platzhaltername`) — zwei benannte Figuren werden nie
  verschmolzen.

- **Vor dem Text steht, wer vorkommt** (07.09.2026, `vorspann.py`). Phase 6
  lieferte die Kurzgeschichte ohne Vorspann; die Gruppe — und jeder, der den
  Text später liest — hatte dreizehn Figuren vor sich, ohne zu wissen, wer wer
  ist. Der Vorspann ist ausdrücklich **nicht Teil der Geschichte**, sondern
  steht davor, an **drei Orten mit demselben Inhalt**: im Chat vor den
  Abschnitten (`knoepfe.zeige_kurzgeschichte`), ganz oben auf der Gruppenseite
  (`web._vorspann_html`, read-only) und unter der Überschrift des
  Textbuch-Exports (`szenenfolge.textbuch`).
  **Deterministisch, kein Modellaufruf** — und das ist die Entscheidung, nicht
  eine Sparmaßnahme: der Vorspann darf nichts erfinden, und er soll bei jedem
  Abruf identisch sein. Ein Modell dazwischen hätte drei Fassungen derselben
  Liste erzeugt. Datengetrieben wie `kontext.baue`: jeder Block fällt weg,
  solange seine Daten leer sind.
  Zwei am echten Material gemessene Fallen sind im Code:
  (1) `figur.beschreibung` trägt die **Schärfungsnotizen aus Phase 5 ohne
  Trennzeichen angeklebt** („kaempft mit sich selbst liefert den Hintergrund
  fuer ihre Ablehnung", 371 Zeichen) — es gibt dort kein Satzende, an dem sich
  schneiden ließe, deshalb schneidet `vorspann.erster_satz` an den Formeln
  (`liefert`, `macht deutlich`, `zeigt`, `begruendet`, `erklaert`,
  `verstaerkt`, `unterstreicht`, mit und ohne Umlaut), sonst am Satzende. Die
  Untergrenze `MINDEST_ZEICHEN` (20) ist der Grund, warum „Mira zeigt Härte."
  nicht zu „Mira" wird: die Formeln sind Notiz-Anfänge, keine verbotenen
  Wörter. (2) Figuren mit `entfernt_am IS NOT NULL` gehören nicht hinein — hier
  noch einmal gefiltert, obwohl `repo.figuren` und `web_daten._figuren` es
  schon tun: der Vorspann ist die eine Liste, die ein Außenstehender liest.
- **Zwischen Fassungen wird umgeschaltet, nicht aufgeklappt** (07.09.2026,
  auf der Tabelle `szenenfassung` von oben). Der aufklappbare Block zeigte
  alle früheren Fassungen am Stück; wer die zweite von vier lesen wollte,
  bekam vier Texte hintereinander. Seitdem steht im Szenenblock eine **Leiste
  mit einer Nummer je Fassung** und darunter **genau eine** — die gewählte —,
  dazu ein Link auf die vorige; in der Szenenübersicht steht je Szene der
  Zähler („3 Fassungen") als Weg dorthin. `web._fassungen_html` ersetzt damit
  den früheren Block: der aktuelle Text stünde sonst zweimal auf der Seite,
  einmal als „der Text" und einmal als „Fassung N". Ab **zwei** Fassungen —
  bei einer gibt es nichts umzuschalten, dann steht der Volltext wie bisher
  da.
  **Rein serverseitig, rein lesend**: `?szene=<id>&fassung=<n>` plus Anker
  (`web.fassungslink`, gelesen von `web.fassungswahl`), kein JS, kein POST,
  kein Cookie — das Token bleibt im Pfad, das Auth-Modell unverändert, und
  das sanfte Nachladen holt `location.href` samt Query, die Auswahl übersteht
  also den Austausch des `<body>`. Eine frühere Fassung wieder in Kraft zu
  setzen ist weiterhin **nicht gebaut** (Entscheidung mit Datenwirkung).
  **Rückwärtskompatibel**: `web_daten.szenenfassungen` legt drei Quellen
  zusammen — das Altfeld `szene.fruehere_fassungen`, die Tabelle und den
  aktuellen `volltext` —, zählt doppelte Texte einmal und nummeriert die
  Liste **selbst** von 1 durch: die Nummer in der URL ist die Nummer in der
  Ansicht, nicht die aus der Tabelle, sonst zeigte ein Link nach dem
  Nachrüsten auf die falsche Fassung. Fehlt die Tabelle noch, ist das
  Ergebnis kleiner statt ein Fehler — der Webserver migriert nichts.
- **Der Stil ist eine Auswahl je Szene, kein Overlay je Bot** (06.09.2026,
  Birk 12:50, `stile.py` + `prompts/stile/<slug>.md`). Birk: „alle Gruppen
  sollen auf alle Stile zugreifen können, als Auswahl, mit Nennung des
  Originalmaterials." Im Feinschliff folgt auf die Form-Frage **eine**
  Nachricht „Welcher Stil?" als Optionen-Menü (fetter Titel, ein Satz,
  Herkunft — Schatten/Morpheuz x Monet192, Lovesong/Adele,
  Herkules.exe/ArtesMobiles) plus „Ohne Stilvorlage"; der Bot schlägt
  passend zur Form vor (Rap → Schlagabtausch, Lied/Chor → Litanei,
  Dialog/Monolog → Herkules) **mit Begründung**, gesetzt wird aber allein
  durch den Druck (`szene.stil`, additive Spalte über
  `_migriere_fehlende_spalten`). `szene.systemanweisung(form, stil)` hängt
  den Stil-Block **nach** dem Formen-Regelblock und **vor** die Tells — und
  **nur bei `form != prosa`**: die Prosafassung ist eine Geschichte, kein
  Bühnentext. Die Web-Gruppenseite hat dasselbe als Dropdown je Szene;
  `web_schreiben.STILE` muss wortgleich zu `stile.STILE` bleiben (Test).

Die Übergaben der Karte Padua A2 (Web-Kanal, 30.09.2026) — was sie bewusst
**nicht** erledigt, jeweils mit Grund:

- **Ein QR-Code zum Gruppenlink.** `scripts/web_gruppe.py` gibt die URL aus,
  keinen Code — dafür bräuchte es eine Abhängigkeit (`qrcode`, `segno`), und
  das Projekt hat auf der Webseite bewusst nur die Standardbibliothek. Wer ihn
  will, entscheidet vorher, welche Abhängigkeit er sich leistet.
- **Englische UI-Texte der Chatansicht.** Die neuen Texte stehen als
  modulweite `_TEXT_*`-Konstanten in `web_chat.py` — genau die Form, die der
  Mechanismus aus Karte A1 (`T = sprache.Texte(__name__)`) später übersetzt.
  Übersetzt sind sie noch nicht; das ist eine Übergabe an A1, nicht eine
  Lücke dieser Karte.
- **Härtung der Weboberfläche** („Absicherung Web"). Es gibt kein
  Rate-Limit: wer den Link hat, kann so viele Nachrichten und Uploads
  schicken, wie er will, und jeder Upload kostet bis zu 8 MiB Speicher und
  einen bezahlten Whisper-Aufruf; heute begrenzen nur `MAX_AUDIO_BYTES` und
  `MAX_TEXT_ZEICHEN` das **einzelne** Ereignis. Das Token in der URL ist
  weiterhin das einzige Geheimnis (E6), und der Nonce steht bei Audio in der
  Query und damit in der Serverlogzeile (`web._Basishandler.log_message`) —
  neu ist das nicht, das Token steht dort ebenfalls.
- **Das Transkript-Echo ist im Web eine gewöhnliche Blase.** In Telegram
  steht es als `typ='transkript'` in `nachricht` und fällt damit aus allen
  drei Fenstern; im Chat sieht es aus wie jede andere Bot-Nachricht, weil es
  über `tg.sende` läuft. Fachlich ist das richtig (es IST die Bestätigung),
  optisch fehlt die Kennzeichnung „das ist dein abgetippter Text, keine
  Antwort des Bots". Übergabe an „Absicherung Web".
- **Die Endung im Telegram-Pfad** (siehe Falle 3): `audio`-Nachrichten und
  Dokumente bekommen in Telegram weiterhin einen `.ogg`-Pfad. Nicht
  angefasst, weil es den Telegram-Pfad ändert (E1).
- **Der Simulator kennt den Web-Kanal nicht.** `simulation/` fährt weiter
  über `TelegramAttrappe` und `bot.verarbeite_update` direkt. Das ist in
  Ordnung (sie misst Prompts und Navigation, nicht den Kanal), aber ein Lauf
  über `WebKanal` wäre der ehrlichere Test des Web-Wegs — `hole_updates` ist
  die eine Methode, die die Simulation nicht berührt.
- **`WebKanal.aktualisiere_knoepfe` hat keinen Aufrufer.** Implementiert und
  getestet, aber `interview_theater/` ruft sie seit dem 06.09.2026 nicht
  (Fragenauswahl per Nummer im Text). Der nächste Toggle bringt sie zurück.
- **Kein Dashboard-Blick auf den Kanal.** `gruppe.kanal` steht in der
  Datenbank, aber nicht in `web_daten.dashboard`.
- ~~Der Chat-Link steht auch bei Telegram-Gruppen.~~ Seit dem
  Abschlussreview (I3) behoben: Link nur bei `gruppe.kanal = 'web'`, alle
  Wege unter `/chat` sonst 404 (siehe „Der Web-Kanal").

Die Übergaben von Padua Phasen TEIL 2 (Prüflauf, Phasen 6/7, 03.10.2026,
siehe „Prüflauf vor jeder Anzeige") — offen, jeweils mit Grund:

- **Die deutschen Phasen-Prompts 6 und 7 tragen noch B3 und den „Hook".**
  `prompts/phasen/6.md` sagt weiter „schreib uns Szene 3" neben der einen
  Geschichte (Flow-Audit B3), `prompts/phasen/7.md` nennt in Regel 4 noch den
  Hook. Neu geschrieben ist nur die englische Fassung (der Hook steht dort
  jetzt in `formen/lied.md`); die deutschen Dateien hasht der
  Dortmund-Schnappschuss, und der Wortlaut ist Birks Entscheidung.
- **`phasentexte.PARAMETER` für 6 und 7 ist nicht profilfähig.** Die
  Checkliste der Phase 6 zählt weiter Bühnentexte (`_geschriebene_szenen`
  liest `volltext`), obwohl in Padua dort Prosa abgenommen wird; die
  Abnahmen (`gesamttext_fixiert_am`, `ueberarbeitung_bestaetigt_am`,
  `sprechweisen_fixiert_am`) stehen in keiner Checkliste.
- **`schaerfung_entscheidung` „none"** verwirft die **gerade angebotenen**
  Stellen (`knoepfe.szenen.verwirf_schaerfung`, das nächste Ziel von
  `biete_schaerfung`), nicht zwingend die im Satz genannte Szene oder Figur —
  meist dasselbe, aber nicht garantiert.
- **`erstentwurf_fassung` ist die Fassung vor dem letzten Prüflauf**, nicht
  die allererste: jeder Lauf setzt den Zeiger neu (der Docstring von
  `repo.setze_szene_erstentwurf` sagt noch „genau einmal").
- **Die Chat-Abnahme in Phase 5** (`fassung_abnehmen`) schickt keine eigene
  Bestätigungszeile; die Gruppe sieht nur den nächsten Szenenlauf anlaufen.
  In 6 und 7 kommt eine Zeile.
- **Ein Undo von `formen_setzen`** nimmt die Formen zurück
  (`ruecknahme.ZUSATZ_JE_ART`), aber nicht einen dadurch schon angestoßenen
  Sprechweisen-Lauf.
- **Ungemessen:** der bezahlte Korpuslauf für die 17 neuen englischen
  Erkenner-Fälle (FP = 0 nicht belegt) und ein bezahlter Simulationslauf
  `--skript padua` (`IT_WORKSHOP=padua-2026 python -m scripts.simulation
  --set 1 --seed 7 --skript padua --bericht`) — ob die Stimmen die
  Schrittbudgets der Phasen 5–7 einhalten, weiß niemand.

Die Übergaben der Karte t_4517d4ad (Begriffsboard, 04.10.2026) — was sie
bewusst nicht erledigt, jeweils mit Grund:

- Seit Karte t_2b9d2cbe gemessen (vorher/nachher gegen Kimi, Opus-Arm als
  Entscheidungsvorlage, siehe `docs/begriffsboard-inhalt/BERICHT.md`);
  Korpusfälle gibt es weiterhin nicht.
- Die Schwellen sind die des Brainstorms (Erwachsenen-Meetings,
  `brainstorm.py`-Kopf), nicht an Schüler-Diskussionen gemessen.
- Ein leeres Ergebnis ersetzt nie ein volles Board — dann rückt die
  Markierung nicht vor, und der nächste Pausenschnitt über der Schwelle löst
  erneut aus.
- Der Merkplatz für den Vorschlag lebt im Prozess (wie `vorschlagssperre`):
  ein Neustart zwischen „Discussion done" und Ende des laufenden Laufs
  verliert den Vorschlag.
- Das Board fließt nicht in die Bühnenkarten der Phase 4
  (`buehnenkarte._kontext_phasen_1_bis_3`) — nur `begriffe_detail` über
  `kontext.baue`.
- Die CoThinker-Darstellung ist ungestaltet (`data-*`, UX-Karte).
- **Ungemessen (t_cb2c4678):** kein bezahlter Lauf für `vorheriger_begriff` —
  ob Kimi/Opus das Feld zuverlässig füllen, weiß niemand. Vergisst das
  Modell es, fehlt nur der Strich; die Begründung erzählt die Entwicklung
  trotzdem.
- Die Wortzahl „1–3" eines Begriffs (und damit eines Vorgängers) steht im
  Prompt, nicht im Code; der Code garantiert „ein Begriff, früher schon auf
  dem Board".
- **Endstand = Zwischenstand (t_cb2c4678):** ein Rest unter `min_zeichen`
  (600 Zeichen ≈ 37 s Rede nach den Erwachsenen-Daten in `brainstorm.py`)
  nach dem letzten Lauf erreicht das Board nicht — so entschieden (Birk).
  Ungemessen für Schülerinnen und Schüler.
- Ohne VAD trägt kein Diskussionssegment einen Schnittgrund: dann gibt es
  weder Board-Lauf noch Vorschlag noch Verdichtung (vor dieser Karte
  genauso). Und hat das letzte Teilstück bei „Discussion done" keine Bytes,
  kommt kein Ende-Schnitt an (`r.onstop`).
- **Design-Erweiterung (04.10.2026): ein Begriff, der ganz vom Board faellt, bleibt unsichtbar.** Nennt die
  Gruppe einen Begriff danach nicht mehr, und das Modell fuehrt ihn im naechsten Lauf nicht mehr, ersetzt
  `begriffsboard._lauf_einmal` das gespeicherte Board vollstaendig durch das neue Ergebnis (`repo.lege_begriffsboard_an`)
  -- der Begriff verschwindet ohne jede Spur, kein Ereignis, kein Zeitstempel. Birk hat das am 04.10.2026 17:10
  als moegliche eigene Visualisierung angefragt ("ein Begriff, der ganz aus dem Board faellt, weil er nie wieder
  genannt wurde"); eine Pruefung ergab: dafuer existiert heute **keine Datengrundlage** -- nichts haelt fest,
  *dass* ein Begriff verschwunden ist, nur *was* zuletzt gespeichert wurde. Nicht gebaut, um nichts zu erfinden.
  Zu unterscheiden vom bestehenden `status="verworfen"` (ein Begriff, den das Modell ausdruecklich als erledigt
  markiert -- der bleibt sichtbar und bekommt seit der Design-Erweiterung eine eigene, gedaempft-kursive
  Darstellung, siehe die `begriffsboard.py`-Zeile oben). Ein kuenftiger Bau bräuchte einen Vorher/Nachher-Abgleich
  der beiden Boardstaende in `_lauf_einmal` und eine neue, dauerhaft gespeicherte Markierung -- beides nicht Teil
  dieser Karte.
- **Design-Erweiterung (04.10.2026): der Poll-Takt des CoThinker-Tabs bleibt bei den 10 s aller Panels.** Birk
  nannte als Vorbild den 3-s-Fingerprint-Poll von `cothinker/stage/stage.py`. `ladeBuehne()` haengt heute am selben
  `setInterval(ladeBuehne, __NACHLADEN_MS__)` wie der Stand-Panel-Poll (`web_vereint.NACHLADEN_MS`, eine Konstante,
  zweifach in `_VEREINT_JS` eingesetzt). Ein eigener, kuerzerer Takt nur fuer die Buehne ist technisch machbar
  (eine zweite Platzhalter-Konstante, ein zweiter `setInterval`), wurde aber **gepruft und bewusst nicht
  umgesetzt**: hoehere Serverlast im Mehrgruppenbetrieb gegen einen von Birk selbst als „Inspiration, kein hartes
  Muss" eingeordneten Punkt. Offen fuer eine eigene, kleine Karte, falls Birk den schnelleren Takt tatsaechlich
  will.
- **Unabhaengiger Bestandsfehler, nur nebenbei entdeckt (04.10.2026): `test_cothinker_panel_hat_kontrast`
  schlaegt fehl, mit dem Begriffsboard hat das nichts zu tun.** Bei der Arbeit an dieser Karte ist aufgefallen,
  dass `tests/e2e/test_web_gestalt_buehne_e2e.py::test_cothinker_panel_hat_kontrast` rot ist: ein `<button>` mit
  dem Zeicheninhalt „▶" erreicht nur ein Kontrastverhaeltnis von 2,25 gegen seinen Hintergrund, verlangt sind
  4,5:1. Per isoliertem Vorher/Nachher-Dateitausch bestaetigt: der Fehler bestand schon **vor** dieser Karte und
  ist von keiner ihrer Aenderungen verursacht. Nicht behoben, weil ausserhalb des Umfangs dieser Karte --
  festgehalten, damit ihn niemand ein zweites Mal entdecken muss.

Die Übergaben der Karte t_9258d2e9 (Begriffsboard-Resonanz, 04.10.2026) —
offen, jeweils mit Grund:

- **Der fokussierte Zweitaufruf ist gebaut, aber noch nicht gemessen.**
  `begriffsboard_analyse.analysiere` hat keinen Live-Aufrufer
  (`interview_theater/begriffsboard_analyse.py`, Test `test_kein_live_aufrufer`);
  der bezahlte Rauchtest, der ihn gegen das echte Modell misst
  (`scripts/rauchtest_begriffsboard_resonanz.py`), konnte in diesem Lauf
  nicht ausgeführt werden (keine Zugangsdaten in der Ausführungsumgebung,
  siehe `docs/begriffsboard-resonanz/BERICHT.md`, Abschnitt „Ausstehend").
  Live ja/nein und welches Modell: Birk (Geld, Modellwahl), nach dem
  nachgeholten Messlauf.
- **Die Mehrheitsregel für Verhörer im Board-Prompt ist unverändert.** Arm D
  des Rauchtests misst „Sinn zuerst" nur als String im Skript; eine Änderung
  an `prompts/begriffsboard.md`/`sprachen/en/prompts/begriffsboard.md` ist
  Birks Entscheidung auf Grundlage des Berichts.
- **Resonanz (D4) nicht gebaut.** Der Messlauf vor dem Einbau
  (`scripts/rauchtest_begriffsboard_resonanz.py`, Aufgabe 4 des Plans) steht
  aus — ohne ihn kein Gate-Ergebnis und damit kein Einbau (`ohne Messung kein
  Einbau`, Plan-Vorgabe). Der Plan für den Einbau steht in
  `docs/superpowers/plans/2026-10-04-padua-begriffsboard-resonanz.md`,
  Aufgaben 5–7.
- **Sprachfund nicht gelöst**: das Board-Modell antwortet im EN-Board
  manchmal deutsch („weather" → „Wetter"); der Rauchtest akzeptiert beides,
  behoben ist es nicht (eigene Karte).
- `scripts/rauchtest_begriffsboard_resonanz.py` — **kein Test, läuft nie
  automatisch, kostet Geld**; Kartendeckel über die Rohdatei
  `korpus/berichte/begriffsboard_resonanz_roh.jsonl` (gitignored).

Die **Weboberflächen sind gebaut** (`web.py`/`web_daten.py`, siehe
„Weboberfläche" unten) — und **Szenen werden geschrieben** (`szene.py`, seit
04.09.2026 abends): der Volltext liegt in `szene` und auf der Gruppenseite.


# Korpuslauf 2026-10-18

Erzeugt von `scripts/pruefe_prompts.py` gegen das echte Modell.

## erkenner

| id | erwartet | geliefert | Treffer | FP | FN | ms |
|---|---|---|---|---|---|---|
| en-e01-interview-starten | interview_starten= | interview_starten= | 1 | 0 | 0 | 1322 |
| en-e02-interview-starten-noch-eine | interview_starten= | interview_starten= | 1 | 0 | 0 | 1773 |
| en-e03-interview-beenden-thats-it | interview_beenden= | interview_beenden= | 1 | 0 | 0 | 426 |
| en-e04-interview-benennen | interview_benennen=baker | interview_benennen=the baker's interview | 1 | 0 | 0 | 510 |
| en-e05-transkript-korrigieren | transkript_korrigieren=ship | transkript_korrigieren=sheep -> ship | 1 | 0 | 0 | 508 |
| en-e06-transkript-zwei-korrekturen | transkript_korrigieren=harbour | transkript_korrigieren=Pronto -> Porto / the hardware -> the harbour | 1 | 0 | 0 | 732 |
| en-e07-begriffe-aus-dem-plenum | begriffe_setzen=football | begriffe_setzen=home, borders, football, grandmother, the sea | 1 | 0 | 0 | 634 |
| en-e08-fragen-aufgeschrieben | fragen_setzen=football | fragen_setzen=home: What did home smell like when you were small? bor… | 1 | 0 | 0 | 770 |
| en-e09-kernthema | kernthema_setzen=leaving without saying goodbye | kernthema_setzen=leaving without saying goodbye | 1 | 0 | 0 | 453 |
| en-e10-format-sprechtheater | format_setzen=spoken | format_setzen=Spoken theatre | 1 | 0 | 0 | 499 |
| en-e11-rahmen-waschsalon | rahmen_setzen=laundrette | rahmen_setzen=a laundrette, the last night before it closes for good | 1 | 0 | 0 | 525 |
| en-e12-hauptkonflikt | hauptkonflikt_setzen=sell the laundrette | hauptkonflikt_setzen=the brother wants to sell the laundrette, the si… | 1 | 0 | 0 | 629 |
| en-e13-zwei-figuren | figur_setzen=Ines; figur_setzen=Karim | figur_setzen=Ines: 60, runs the laundrette since 1989; figur_setzen=K… | 2 | 0 | 0 | 1007 |
| en-e14-figur-quelle-zustimmung | figur_quelle_setzen=Ines: Interview 2 | figur_quelle_setzen=Ines: Interview 2 | 1 | 0 | 0 | 577 |
| en-e15-figur-quelle-von-sich-aus | figur_quelle_setzen=Karim: Interview 3 | figur_quelle_setzen=Karim: Interview 3 | 1 | 0 | 0 | 953 |
| en-e16-wortlaut-an | wortlaut_an=baker | wortlaut_an=baker interview | 1 | 0 | 0 | 445 |
| en-e17-wortlaut-aus | wortlaut_aus= | wortlaut_aus= | 1 | 0 | 0 | 732 |
| en-e18-verworfen-kindheitsfragen | verworfen=childhood questions | verworfen=childhood questions at the start - feels too private for th… | 1 | 0 | 0 | 531 |
| en-e19-verworfen-video | verworfen=video | verworfen=projecting interview videos behind the actors - too much te… | 1 | 0 | 0 | 567 |
| en-e20-titel-festlegung | festlegung_setzen=Salt and Sugar | festlegung_setzen=TITEL: Salt and Sugar | 1 | 0 | 0 | 866 |
| en-e20b-entschieden-interviews-in-german | entschieden=German | entschieden=all interviews will be conducted in German - otherwise tr… | 1 | 0 | 0 | 692 |
| en-e21-szene-planen-kueche | szene_planen=kitchen | szene_planen=SZENE 2 / ORT: back kitchen of the laundrette / ZEIT: ea… | 1 | 0 | 0 | 1084 |
| en-e22-szene-schreiben-nach-planung | szene_schreiben=kitchen | szene_schreiben=SZENE 2: Ines tells Karim in the kitchen early mornin… | 1 | 0 | 0 | 1760 |
| en-e23-phase-figuren | phase_setzen=4 | phase_setzen=4 | 1 | 0 | 0 | 403 |
| en-e24-entfernen-figur | entfernen=FIGUR Tomas | entfernen=FIGUR Tomas | 1 | 0 | 0 | 419 |
| en-e25-entfernen-kernthema | entfernen=KERNTHEMA | entfernen=KERNTHEMA | 1 | 0 | 0 | 436 |
| en-e26-usa-ja | szene_usa=JA | szene_schreiben=JA | 0 | 1 | 1 | 468 |
| en-e27-usa-nein | szene_usa=NEIN | szene_schreiben=NEIN | 0 | 1 | 1 | 512 |
| en-e28-festlegung-figur-herkunft | festlegung_setzen=Porto | festlegung_setzen=FIGUR/Ines: comes from Porto, came here at 22, used… | 1 | 0 | 0 | 896 |
| en-e29-festlegung-stil-laenge | festlegung_setzen=one page | festlegung_setzen=STIL: one page per scene max from now on | 1 | 0 | 0 | 1314 |
| en-e30-kuerzen-mit-nummer | szene_kuerzen=3 | szene_kuerzen=3 | 1 | 0 | 0 | 527 |
| en-e31-kuerzen-ohne-nummer | szene_kuerzen= | — | 0 | 0 | 1 | 291 |
| en-e32-format-als-aussage | format_setzen=musical | format_setzen=Musical: songs and rap | 1 | 0 | 0 | 552 |
| en-z01-begriffe-zustimmung-italienisch | begriffe_setzen=belonging | begriffe_setzen=belonging, family, noise, courage | 1 | 0 | 0 | 587 |
| en-z02-figuren-zustimmung-italienisch | figur_setzen=Nadia; figur_setzen=Karim; figur_setzen=Lena | figur_setzen=Nadia: cleans the machines at night; figur_setzen=Karim:… | 3 | 0 | 0 | 2137 |
| en-z03-kernthema-zustimmung | kernthema_setzen=No way back | kernthema_setzen=No way back | 1 | 0 | 0 | 504 |
| en-z04-rahmen-zustimmung | rahmen_setzen=night bus | rahmen_setzen=a night bus from the city to the coast, the last one of… | 1 | 0 | 0 | 897 |
| en-z05-fragen-zustimmung | fragen_setzen=border | fragen_setzen=home: What did home smell like when you were small? bor… | 1 | 0 | 0 | 1644 |
| en-a01-aufnahme-an-den-bot | an_den_bot= | an_den_bot= | 1 | 0 | 0 | 448 |
| en-a02-aufnahme-material | — | — | 0 | 0 | 0 | 352 |
| en-a03-aufnahme-fertig-gesagt | interview_beenden= | interview_beenden= | 1 | 0 | 0 | 427 |
| en-a04-aufnahme-benannt | interview_benennen=fisherman | interview_benennen=the fisherman's interview | 1 | 0 | 0 | 624 |
| en-a05-aufnahme-wie-viele-interviews | an_den_bot= | an_den_bot= | 1 | 0 | 0 | 465 |
| en-a06-aufnahme-interviewfrage-imperativ | — | — | 0 | 0 | 0 | 286 |
| en-a07-aufnahme-kernthema-erzaehlt | — | — | 0 | 0 | 0 | 262 |
| en-n01-interview-nur-erwaehnt | — | — | 0 | 0 | 0 | 339 |
| en-n02-wie-viele-interviews | — | — | 0 | 0 | 0 | 252 |
| en-n03-begruessung | — | — | 0 | 0 | 0 | 352 |
| en-n04-lob-und-termin | — | — | 0 | 0 | 0 | 412 |
| en-n05-fragen-nur-ueberlegt | — | — | 0 | 0 | 0 | 363 |
| en-n08-szene-zu-lang-kritik | — | — | 0 | 0 | 0 | 271 |
| en-n09-mittelteil-muss-raus | — | — | 0 | 0 | 0 | 292 |
| en-n10-ja-zur-frage-nicht-zur-sache | — | — | 0 | 0 | 0 | 255 |
| en-n11-vorschlag-mit-zweifel | — | — | 0 | 0 | 0 | 262 |
| en-n12-aufnahme-loeschen-verlangt | — | — | 0 | 0 | 0 | 284 |
| en-n13-zweifel-an-figur | — | — | 0 | 0 | 0 | 246 |
| en-n16-go-ohne-planung | — | — | 0 | 0 | 0 | 283 |
| en-n18-ja-ohne-usa-frage | — | — | 0 | 0 | 0 | 262 |
| en-n19-phase-spaeter | — | — | 0 | 0 | 0 | 265 |
| en-n20-quelle-nur-ueberlegt | — | — | 0 | 0 | 0 | 257 |
| en-n21-lob-verdichtung | — | — | 0 | 0 | 0 | 274 |
| en-n22-organisatorisches | — | — | 0 | 0 | 0 | 245 |
| en-n23-rueckfrage-an-den-bot | — | — | 0 | 0 | 0 | 263 |
| en-n24-italienische-plauderei | — | — | 0 | 0 | 0 | 253 |
| en-n25-kein-konflikt-noetig-frage | — | — | 0 | 0 | 0 | 288 |
| en-n26-szene-lob-kein-kuerzen | — | — | 0 | 0 | 0 | 280 |
| en-n27-figur-vorschlagen-frage | — | — | 0 | 0 | 0 | 251 |
| en-n28-setting-frage | — | — | 0 | 0 | 0 | 262 |
| en-n29-format-frage | — | — | 0 | 0 | 0 | 274 |
| en-n30-szene-kritik-ohne-auftrag | — | — | 0 | 0 | 0 | 253 |
| en-n31-lob-figur | — | — | 0 | 0 | 0 | 252 |
| en-n32-kernthema-nachfrage | — | — | 0 | 0 | 0 | 281 |
| en-n33-kuerzen-als-frage | — | — | 0 | 0 | 0 | 258 |
| en-e33-szenenanzahl-direkt-genannt | szenenanzahl_setzen=5 | szenenanzahl_setzen=5 | 1 | 0 | 0 | 427 |
| en-e34-szenenanzahl-auf-nachfrage | szenenanzahl_setzen=6 | szenenanzahl_setzen=6 | 1 | 0 | 0 | 456 |
| en-e35-overview-ending-sadder | uebersicht_aendern=ending sadder | text_ueberarbeiten=make the ending sadder, they shouldn't really find… | 0 | 1 | 1 | 550 |
| en-e36-overview-try-again-no-direction | uebersicht_aendern= | — | 0 | 0 | 1 | 3278 |
| en-n34-overview-yes-is-not-aendern | — | — | 0 | 0 | 0 | 257 |
| en-tu01-mutter-wuetender | text_ueberarbeiten=angrier | text_ueberarbeiten=make the mother angrier | 1 | 0 | 0 | 448 |
| en-tu02-szene-zwei-stiller | text_ueberarbeiten=scene 2 | text_ueberarbeiten=scene 2: less talking, more silence | 1 | 0 | 0 | 526 |
| en-tu03-ende-zu-weich | text_ueberarbeiten=hurt | text_ueberarbeiten=the ending is too soft, make it hurt more | 1 | 0 | 0 | 517 |
| en-tn01-warum-so-wuetend | — | — | 0 | 0 | 0 | 262 |
| en-tn02-spaeter-lesen | — | — | 0 | 0 | 0 | 281 |
| en-fa01-ja-speichern | fassung_abnehmen= | fassung_abnehmen= | 1 | 0 | 0 | 384 |
| en-fa02-perfekt-so-lassen | fassung_abnehmen= | fassung_abnehmen= | 1 | 0 | 0 | 424 |
| en-fn01-ja-zur-pause | — | — | 0 | 0 | 0 | 305 |
| en-fs01-formen-liste | formen_setzen=chorus | formen_setzen=1: chorus / 2: dialogue / 3: rap | 1 | 0 | 0 | 559 |
| en-fs02-formen-im-satz | formen_setzen=song | formen_setzen=1: Song / 2: Monologue | 1 | 0 | 0 | 795 |
| en-fsn01-was-ist-chor | — | — | 0 | 0 | 0 | 287 |
| en-sw01-mira-kurze-saetze | sprechweise_setzen=Mira | sprechweise_setzen=Mira: short sentences, lots of slang | 1 | 0 | 0 | 674 |
| en-sw02-jo-langsamer | sprechweise_setzen=Jo | sprechweise_setzen=Jo: slower, like he's tired | 1 | 0 | 0 | 1309 |
| en-swn01-mira-aelteste | festlegung_setzen=oldest | festlegung_setzen=FIGUR/Mira: oldest of the siblings | 1 | 0 | 0 | 613 |
| en-se01-zeile-fuer-szene-eins | schaerfung_entscheidung=scene 1 | schaerfung_entscheidung=scene 1 | 1 | 0 | 0 | 525 |
| en-se02-nichts-fuer-mira | schaerfung_entscheidung=none | schaerfung_entscheidung=none | 1 | 0 | 0 | 1064 |
| en-sen01-was-heisst-das-zitat | — | — | 0 | 0 | 0 | 363 |
| en-rs01-bruecke-gebaut | recherche_starten=When was this bridge actually built? | recherche_starten=when was this bridge actually built? | 1 | 0 | 0 | 943 |
| en-rs02-gesetz-nachschlagen | recherche_starten=Whether that old law about the harbour really exist… | recherche_starten=whether that old law about the harbour really exist… | 1 | 0 | 0 | 612 |
| en-rs03-spaeter-irgendwann | — | — | 0 | 0 | 0 | 276 |
| en-e37-teile-als-szenen | szenenanzahl_setzen=3 | szenenanzahl_setzen=3 | 1 | 0 | 0 | 598 |
| en-e38-durchlaufend-keine-neue-anzahl | — | — | 0 | 0 | 0 | 330 |
| en-ssn01-szene-nicht-geschrieben | stagescript_notiz=scene 2 | stagescript_notiz=scene 2: needs a real back-and-forth, not everyone … | 1 | 0 | 0 | 591 |
| en-ssn02-ohne-nummer | stagescript_notiz=no interview quotes | text_ueberarbeiten=scene 1: no interview quotes in this one | 0 | 1 | 1 | 504 |
| en-ssnn01-gezeigter-text | text_ueberarbeiten=back-and-forth | text_ueberarbeiten=scene 2: give them a real back-and-forth instead o… | 1 | 0 | 0 | 619 |

**erkenner** (google/gemma-4-31B-it), 103 Laeufe

- Trefferquote: 61/67
- Falsch-Positive: **4**
- Falsch-Negative: 6
- Median-Dauer: 453 ms
- Token: 1062271 ein, 2393 aus — 0.2134 CHF (Preise Stand 04.09.2026)
- Fragen ohne Thema vor dem Doppelpunkt: 0
- Falsch-Negative in Zustimmungsfaellen (12 Faelle, soll 0): **2**
  - verpasst in: en-e26-usa-ja, en-e31-kuerzen-ohne-nummer

<details><summary>Auffaellige Faelle im Einzelnen</summary>

**en-e26-usa-ja** — FP 1, FN 1
> Gegenstueck zu u01: Zustimmung nach der USA-Frage, wert als Protokollwort JA.

```json
[
  {
    "art": "szene_schreiben",
    "wert": "JA"
  }
]
```

**en-e27-usa-nein** — FP 1, FN 1
> Gegenstueck zu u02: Ablehnung nach der USA-Frage, wert als Protokollwort NEIN.

```json
[
  {
    "art": "szene_schreiben",
    "wert": "NEIN"
  }
]
```

**en-e31-kuerzen-ohne-nummer** — FP 0, FN 1
> Gegenstueck zu sk02: ohne Nummer ist der zuletzt geschriebene Text gemeint -- leerer wert, keine geratene Nummer.

```json
[]
```

**en-e35-overview-ending-sadder** — FP 1, FN 1
> Padua Phasen TEIL 1 (03.10.2026): feedback on the generated overview that fits no existing field, overview not yet fixed. Englischer Gegenfall zu ue01. wert bewusst knapp (nur "ending sadder") -- der Kern der Sache, kein Wortlaut: ein Teilstring-Vergleich gegen die volle Formulierung des Modells ("shouldn't"/"don't" etc. variieren) ist zu zerbrechlich, siehe AGENTS.md "wert im Erkenner-Korpus ist der Kern der Sache, nicht der erwartete Wortlaut".

```json
[
  {
    "art": "text_ueberarbeiten",
    "wert": "make the ending sadder, they shouldn't really find each other"
  }
]
```

**en-e36-overview-try-again-no-direction** — FP 0, FN 1
> Padua Phasen TEIL 1 (03.10.2026): plain "try again" with no direction -- wert stays empty, nothing guessed. Englischer Gegenfall zu ue02.

```json
[]
```

**en-ssn02-ohne-nummer** — FP 1, FN 1
> Padua Quickfix (08.10.2026, Punkt 1): kein Yes/No-Angebot gerade offen (Szene 1 ist schon gespeichert) -> die Rueckmeldung meint die naechste, noch nicht geschriebene Szene, stagescript_notiz ohne genannte Nummer. Frei erfunden.

```json
[
  {
    "art": "text_ueberarbeiten",
    "wert": "scene 1: no interview quotes in this one"
  }
]
```

</details>


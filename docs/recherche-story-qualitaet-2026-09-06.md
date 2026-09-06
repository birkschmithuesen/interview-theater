# Was macht eine gute (Theater-)Geschichte aus — und wie ein Judge-LLM das prüfbar bewertet

**Datum:** 2026-09-06
**Kontext:** Telegram-Bot begleitet Jugend-/Laientheatergruppen (15–18 J.) von Interviews über Setting/Figuren/Geschichte zu geschriebenen Szenentexten (Dialog, Monolog, Chor, Lied, Rap). Ein LLM schreibt die Szenen. Ziel: automatischer Qualitäts-Fan-out mit mehreren spezialisierten Judge-Aufrufen à **einer präzisen Frage**, deren Ergebnis in gezielte Überarbeitung mündet — statt einer vagen Gesamtnote.
**Zweck dieses Dokuments:** dramaturgische Fundierung + fertiger, operationalisierbarer Fragenkatalog + Architekturempfehlung.

---

## 0. Quellenlage

| # | Quelle | URL | Wofür genutzt |
|---|---|---|---|
| Q1 | Aristoteles, *Poetik* (Darstellung: theatrum vinum, Essay mit Stegemann-Bezug) | https://theatrumvinum.de/2023/02/04/aristoteles-poetik/ | Mythos/Handlung als Primat, Peripetie, Anagnorisis, Hamartia, Einheit der Handlung |
| Q2 | Gustav Freytag, *Die Technik des Dramas* (1863), Originalzitate | https://www.zum.de/Faecher/D/BW/gym/take5/freytag.htm | Pyramide, erregendes Moment, Steigerung, Höhepunkt, Umkehr, Moment der letzten Spannung, Katastrophe |
| Q3 | John Yorke, *Into the Woods* — „Roadmap of Change" (Beat-Aufschlüsselung) | https://www.arcstudiopro.com/blog/roadmap-of-change-john-yorke | Fünfakter als Wissens-/Veränderungskurve, Midpoint, Zweifel/Regression, Fraktalität |
| Q4 | John Yorke, *Into the Woods* — 5-Akt-Struktur (Story Planner) | https://www.storyplanner.com/story/plan/into-the-woods-5-act-structure | Tentpoles, Aktgrenzen |
| Q5 | Robert McKee, *Story* — Kernprinzipien (Zusammenfassung sobrief) | https://sobrief.com/books/story | „The Gap", Value Charge / Szenenwendung, Controlling Idea, Charakter = Entscheidung unter Druck, Subtext |
| Q6 | McKee, *Story* — Beat/Turning-Point-Analyse | https://jamesdangerblog.wordpress.com/2017/04/23/story-substance-structure-style-and-the-principles-of-screenwriting-by-robert-mckee/ | Szenenarc, Beat-Zerlegung, Turning Point lokalisieren |
| Q7 | Lajos Egri, *The Art of Dramatic Writing* — Notizen mit Direktzitaten | http://harimohanparuvu.blogspot.com/2021/03/the-art-of-dramatic-writing-lagos-egri.html | Prämisse (Satz mit Subjekt–Konflikt–Ende), Drei-Dimensionen-Figur, Orchestrierung, Unity of Opposites |
| Q8 | Brecht / Episches Theater (Lernhelfer, Schülerlexikon) | https://www.lernhelfer.de/schuelerlexikon/deutsch-abitur/artikel/das-epische-theater | Montage von Einzelszenen, Songs/Chor als V-Effekt, Haltung statt Einfühlung, Zuschaueransprache |
| Q9 | Verfremdungseffekt (Wikipedia DE) | https://de.wikipedia.org/wiki/Verfremdungseffekt | Funktion des Song-/Kommentar-Einschubs, Unterbrechung der Illusion |
| Q10 | Chris Megson (Royal Holloway): Verbatim Theatre | https://www.royalholloway.ac.uk/research-and-education/subjects/drama-and-theatre/teacherhubdrama-theatre-and-dance/verbatim-theatre/ | Interviewmaterial → Skript, „recorded delivery", Feedback-Loop zu Beitragenden, ethische Verantwortung |
| Q11 | Derek Paget, *„Verbatim Theatre": Oral History and Documentary Techniques* (PDF) | https://temporada-alta.com/wp-content/uploads/verbatim_theatre_oral_history_and_documentary_techniques.pdf | Authentizitäts-/Editier-Dialektik, Zeugenschaft als dramaturgisches Prinzip |
| Q12 | Trabasso u. a.: Causal thinking and the representation of narrative events | https://www.sciencedirect.com/science/article/abs/pii/0749596X8590049X | Kausalnetzwerk-Modell: Ereignisse in der Kausalkette werden erinnert, Sackgassen nicht |
| Q13 | Sah: The Development of Coherence in Narratives: Causal Relations (ACL) | https://aclanthology.org/Y13-1015.pdf | Kausalrelationen als messbares Kohärenzmaß |
| Q14 | Chhun et al. 2022, **HANNA** — *Of Human Criteria and Automatic Metrics* (COLING) | https://aclanthology.org/2022.coling-1.509.pdf / https://arxiv.org/abs/2208.11646 | 6 orthogonale Kriterien: Relevance, Coherence, Empathy, Surprise, Engagement, Complexity; automatische Metriken korrelieren schwach |
| Q15 | HANNA Datensatz/Repo | https://github.com/dig-team/hanna-benchmark-asg | 1.056 Stories, 3 Rater, 6 Kriterien, 19.008 Ratings |
| Q16 | Chen et al. 2022, **StoryER** (EMNLP) | https://arxiv.org/abs/2210.08459 | Ranking + Rating + Reasoning; aspektweise Bewertung (opening, character-shaping) mit Kommentar schlägt reines Scoring |
| Q17 | Zheng et al. 2023, *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* | https://arxiv.org/abs/2306.05685 | Position Bias, Verbosity Bias, Self-Enhancement Bias, begrenzte Reasoning-Fähigkeit + Gegenmaßnahmen |
| Q18 | Ye et al. 2024, *Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge* (CALM) | https://arxiv.org/html/2410.02736v1 | 12 Bias-Typen, automatisierte Perturbations-Prüfung, Empfehlungen zur zuverlässigen Anwendung |
| Q19 | Liu et al. 2023, **G-Eval** | https://arxiv.org/abs/2303.16634 | Form-Filling-Paradigma + CoT; höhere Human-Korrelation als Referenzmetriken; Bias zugunsten LLM-generierter Texte |
| Q20 | Chekhov's Gun (Wikipedia, mit Originalbriefzitaten) | https://en.wikipedia.org/wiki/Chekhov%27s_gun | „Remove everything that has no relevance to the story…" — narrative Ökonomie, Einlösepflicht |

---

## 1. Kurzsynthese: 12 Qualitätsdimensionen

Gegliedert nach **Ebene**, weil der Fan-out genau daran hängt: eine Dimension auf Szenenebene braucht nur die Szene im Kontext, eine auf Geschichtsebene braucht die Synopsen-Kette.

### Ebene A — GESCHICHTE / Szenenfolge

**A1 — Prämisse / Controlling Idea (Zielsatz des Stücks)**
Egri fordert einen einzigen Satz, der Subjekt, Konflikt und Ausgang enthält („Ruthless ambition leads to self-destruction"); er sei „das Samenkorn", aus dem alles Weitere wächst, und der Autor müsse ihn beweisen wollen (Q7). McKee nennt dasselbe *Controlling Idea*: die Bedeutungsaussage, die der Climax durch die Handlung belegt (Q5). Für ein Laienstück aus Interviewmaterial ist das der Filter, der aus Anekdotensammlung ein Stück macht. Prüfbar: Lässt sich aus der Szenenfolge genau eine solche These rekonstruieren — und arbeiten die Szenen daran, oder daneben?

**A2 — Kausale Verkettung statt Aneinanderreihung**
Aristoteles' Einheit der Handlung verlangt, dass die Teile so verbunden sind, dass Umstellen oder Weglassen das Ganze zerstört (Q1). Die kognitionspsychologische Forschung bestätigt das empirisch: Ereignisse, die in der kausalen Kette vom Anfang zum Ende liegen, werden erinnert und als wichtig eingeschätzt; „dead-end"-Ereignisse fallen heraus (Q12, Q13). Prüfbar auf Szenenfolgen-Ebene: Existiert für jede Szene *n* eine „weil/deshalb"-Verbindung zu *n−1* oder ist sie nur ein „und dann"?

**A3 — Dramatische Kurve / Struktur über die Folge**
Freytag: Einleitung → erregendes Moment → Steigerung → Höhepunkt → tragisches Moment/Umkehr → Moment der letzten Spannung → Katastrophe; „Satz und Gegensatz, Kampf und Gegenkampf, Steigen und Sinken, Binden und Lösen" (Q2). Yorke übersetzt das in eine Wissenskurve: Der Protagonist bewegt sich von Nicht-Wissen über Zweifel, Midpoint-Umschlag, Regression zur Meisterschaft (Q3, Q4). Prüfbar: Sind erregendes Moment, Midpoint-Umschlag und Höhepunkt als konkrete Szenen benennbar — oder verläuft die Spannung flach?

**A4 — Figurenwandel / Arc über die Folge**
Yorkes Kern: Die Reise ist Erkenntniszuwachs — über die Welt *und* über das Thema (Q3). McKee: „Character is plot", eine flache Figur repariert man durch das Plot-Design, nicht durch Beschreibung (Q5). Aristoteles' Anagnorisis (Erkennen) ist der klassische Marker desselben (Q1). Prüfbar: Nennt die Szenenfolge einen Zustand X der Hauptfigur zu Beginn und einen davon verschiedenen Zustand Y am Ende, plus die Szene, in der der Umschlag passiert?

**A5 — Continuity / Welt-, Zeit- und Figurenlogik**
Nicht klassisch-dramaturgisch, aber der häufigste Fehlermodus LLM-geschriebener Serien: Figuren wissen plötzlich Dinge, die sie nicht erfahren haben; Orte/Uhrzeiten widersprechen sich; Namen driften. Kausalkohärenz (Q12/Q13) ist die theoretische Basis, HANNA operationalisiert es als *Coherence* (Q14). Prüfbar und teilweise **mechanisch** vorprüfbar (siehe §5).

**A6 — Narrative Ökonomie / eingelöste Versprechen (Tschechows Gewehr)**
Tschechow: „Remove everything that has no relevance to the story. If you say in the first act that there is a rifle hanging on the wall, in the second or third act it absolutely must go off" (Q20). Aristoteles' Notwendigkeitskriterium (Q1) sagt dasselbe strenger. In Verbatim-Stoffen besonders relevant, weil Interviewmaterial ständig Nebenmotive einschleppt. Prüfbar: Welche Gegenstände/Geheimnisse/Ankündigungen/Konflikte werden eingeführt und nie eingelöst?

**A7 — Formenvielfalt mit Funktion (Montage, Songs, Chor)**
Brecht montiert Einzelszenen und setzt Songs, Kommentare, Chor und Publikumsansprache als Verfremdungseffekte ein — sie sollen unterbrechen, kommentieren, Haltung sichtbar machen, nicht illustrieren (Q8, Q9). Für ein Stück mit Dialog/Monolog/Chor/Lied/Rap ist die entscheidende Frage nicht „ist die Form da?", sondern „tut die Form etwas, was ein Dialog nicht könnte?". Prüfbar pro Nicht-Dialog-Szene.

**A8 — Materialtreue & Zeugenschaft (Verbatim-Dimension)**
Verbatim-Theater erzeugt Bedeutung gerade aus der Spannung zwischen originalem Zeugnis und dramaturgischer Bearbeitung; das Stück wird oft vor den Beitragenden gespielt — ein Feedback-Loop mit ethischer Verantwortung (Q10, Q11). Bei Jugendlichen, deren eigene Interviews Grundlage sind, heißt das: Erkennen sich die Sprechenden wieder, oder hat das LLM sie zu Klischees geglättet? Prüfbar gegen die Interview-Notizen.

### Ebene B — EINZELSZENE

**B1 — Szenenwendung (Value Charge Flip)**
McKee: Eine echte Szene dreht ihre Wertladung von plus nach minus oder umgekehrt; passiert das nicht, ist es Exposition oder ein Nicht-Ereignis — „Delete every scene where the value charge doesn't flip" (Q5, Q6). Das ist das schärfste, am leichtesten operationalisierbare Einzelszenen-Kriterium überhaupt und die häufigste Schwäche von LLM-Szenen: sie plaudern, aber ändern nichts. Prüfbar: Was ist der Wert am Anfang, was am Ende, in welcher Zeile kippt er?

**B2 — Konflikt, Widerstand und Einsatz (Stakes)**
Freytags „Kampf und Gegenkampf" (Q2), Egris „Unity of Opposites" — Gegner müssen so verbunden sein, dass keiner ausweichen kann (Q7), McKees Prinzip des Antagonismus: Der Widerstand muss stark genug sein, um die Figur zu verändern (Q5). Prüfbar: Will in der Szene jemand konkret etwas, will ein anderer etwas Unvereinbares, und kostet Scheitern etwas?

**B3 — The Gap: Erwartung vs. Ergebnis**
McKees Kernmechanik: Story lebt in der Lücke, die sich auftut, wenn eine Figur handelt und die Welt anders reagiert als erwartet; die Figur muss daraufhin eine riskantere Handlung wählen (Q5, Q6). Prüfbar pro Szene: Gibt es mindestens eine Handlung, deren Resultat von der Erwartung abweicht?

**B4 — Exposition im Handeln statt im Referat**
McKee: Exposition wird dramatisiert, nie serviert; was Figuren sagen, verdeckt, was sie denken (Subtext) (Q5). LLM-Szenen neigen zum Gegenteil: Figuren erklären einander Dinge, die sie längst wissen („As you know, Bob"). Prüfbar durch gezielte Suche nach Sätzen, deren Adressat die Information bereits hat.

### Ebene C — FIGUR / STIMME

**C1 — Figurenspezifische Stimme (Idiolekt)**
Egris Drei-Dimensionen-Modell (physisch, soziologisch, psychologisch) begründet, *warum* Figuren unterschiedlich sprechen müssen: Herkunft, Bildung, Milieu und Temperament färben die Sprache (Q7). Orchestrierung heißt: kontrastierende Figuren, keine Varianten derselben Person. Prüfbar mit einem „Blind-Attribution-Test": Kann man Namen entfernen und die Sprecher wieder zuordnen?

**C2 — Handlung aus Motivation / Charakter durch Entscheidung**
Aristoteles: Je weniger das Schicksal lenkt, desto mehr konstituieren die Entscheidungen die Figur (Q1). McKee: Charakter zeigt sich in Entscheidungen unter Druck, nicht in Beschreibung (Q5). Egri: „deep-rooted motivation" (Q7). Prüfbar: Trifft die Figur in der Szene eine Wahl, deren Motiv aus vorher Etabliertem folgt — oder handelt sie, weil der Plot es braucht?

**C3 — Emotionale Beteiligung und Altersstimmigkeit (Empathy/Engagement)**
HANNA misst genau das mit *Empathy* („how much did you feel with the characters") und *Engagement* als eigenständige, von Kohärenz unabhängige Kriterien (Q14, Q15); StoryER bestätigt, dass Menschen aspektweise urteilen, u. a. über „character-shaping" (Q16). Für 15–18-Jährige kommt hinzu: Spielbarkeit und Sprachregister müssen zur Gruppe passen — kein Erwachsenen-Feuilleton im Mund von Jugendlichen, keine anbiedernde Jugendsprache. Prüfbar als eigene Frage.

> **Verhältnis zu HANNA:** Die sechs HANNA-Kriterien (Relevance, Coherence, Empathy, Surprise, Engagement, Complexity, Q14) sind hier nicht verworfen, sondern verteilt: Relevance→A1, Coherence→A2/A5, Empathy→C3, Surprise→B3, Engagement→C3, Complexity→B2/C1. Wichtig ist HANNAs Befund, dass **automatische Referenzmetriken (BLEU, ROUGE, BERTScore …) nur schwach mit menschlichem Urteil korrelieren** — deshalb Judge-LLM statt Metrik, aber mit Belegpflicht.

---

## 2. Judge-Fragen mit Ausgabeschema

**Gemeinsame Konventionen für alle Fragen**

- Antwortskala: `0` = Kriterium klar verfehlt, `1` = teilweise/schwach erfüllt, `2` = erfüllt. Binäre Fragen nutzen nur 0/2.
- Jeder Judge-Aufruf enthält **genau eine** Frage. Keine Sammelrubriken, keine Gesamtnote.
- **Zitatpflicht:** `beleg` muss ein wörtliches, zusammenhängendes Textstück (≥ 15 Zeichen) aus dem geprüften Material sein. Wird mechanisch verifiziert (§4).
- `schwere` ∈ `{"blocker","hoch","mittel","niedrig"}` — steuert, ob eine Überarbeitung erzwungen wird.
- `konkreter_umbauvorschlag`: eine ausführbare Anweisung an den Schreib-LLM, max. 2 Sätze, mit Szenennummer/Figurennamen — kein „mehr Spannung erzeugen".

**Basis-JSON-Schema (identisch für alle Fragen):**

```json
{
  "frage_id": "B1_szenenwendung",
  "ebene": "szene",
  "score": 0,
  "befund": "Die Szene endet im selben emotionalen Zustand, in dem sie beginnt: Mira und Jonas streiten über den Schlüssel, ohne dass sich das Machtverhältnis ändert.",
  "beleg": "MIRA: Gib mir den Schlüssel. / JONAS: Nein. / MIRA: Bitte. / JONAS: Nein.",
  "beleg_ort": {"szene": 4, "zeilen": [22, 25]},
  "schwere": "hoch",
  "konkreter_umbauvorschlag": "Lass Jonas in Zeile 25 den Schlüssel hergeben, aber eine Bedingung stellen, die Mira nicht erfüllen kann — damit kippt die Szene von 'Mira ohnmächtig' zu 'Mira scheinbar am Ziel, real tiefer verstrickt'.",
  "unsicher": false
}
```

`unsicher: true` ist Pflicht, wenn der Judge kein wörtliches Zitat findet — dann wird `score` verworfen und die Frage eskaliert an einen Menschen oder ein zweites Modell (§4).

### Ebene A — Geschichte / Szenenfolge

**A1 — Prämisse**
> *Frage:* „Formuliere in EINEM Satz die Prämisse dieses Stücks in der Form ‚<Subjekt> führt durch <Konflikt> zu <Ausgang>'. Vergib dann: 2, wenn die Szenenfolge genau eine solche These trägt und mindestens drei Szenen erkennbar daran arbeiten; 1, wenn eine These erkennbar ist, aber ≥ 2 Szenen ihr widersprechen oder unbeteiligt sind; 0, wenn sich keine These oder mehrere gleichrangige rekonstruieren lassen. Zitiere wörtlich die Stelle, die die These am deutlichsten trägt oder bricht." *(Q7, Q5)*
> Zusatzfeld: `"rekonstruierte_praemisse": "..."`

**A2 — Kausale Verkettung**
> *Frage:* „Prüfe für jede Szene n ≥ 2, ob sie kausal an eine frühere Szene anschließt (‚deshalb/deswegen') oder nur zeitlich folgt (‚und dann'). Vergib 2, wenn ≤ 1 Szene rein additiv ist; 1 bei 2–3; 0 bei ≥ 4. Zitiere die erste Stelle, an der die Kausalkette reißt." *(Q1, Q12, Q13)*
> Zusatzfeld: `"additive_szenen": [3, 7]`

**A3 — Dramatische Kurve**
> *Frage:* „Benenne die Szenennummer für (a) das erregende Moment, (b) den mittleren Umschlag/Midpoint, (c) den Höhepunkt. Vergib 2, wenn alle drei eindeutig identifizierbar und in dieser Reihenfolge sind; 1, wenn eines fehlt oder mehrdeutig ist; 0, wenn zwei oder mehr fehlen. Zitiere je den auslösenden Satz." *(Q2, Q3)*
> Zusatzfeld: `"tentpoles": {"erregendes_moment": 2, "midpoint": 5, "hoehepunkt": 8}`

**A4 — Figurenwandel**
> *Frage:* „Beschreibe für die Hauptfigur den Zustand in der ersten und in der letzten Szene in je einem Halbsatz. Vergib 2, wenn beide Zustände klar verschieden sind UND eine Szene benennbar ist, in der der Wandel kippt; 1, wenn ein Wandel behauptet, aber nicht in einer Szene ereignishaft wird; 0, wenn kein Unterschied erkennbar ist. Zitiere den Satz, der den Wandel am deutlichsten markiert (oder seinen Beleg schuldig bleibt)." *(Q3, Q5, Q1)*
> Zusatzfelder: `"figur": "Mira", "zustand_anfang": "...", "zustand_ende": "...", "wendeszene": 6`

**A5 — Continuity (Wissenslogik der Figuren)**
> *Frage:* „Nenne jede Stelle, an der eine Figur Wissen, ein Objekt oder eine Beziehung voraussetzt, das im bisherigen Szenenverlauf weder gezeigt noch plausibel erschließbar ist. Vergib 2 bei keiner Stelle; 1 bei einer; 0 bei ≥ 2. Zitiere die Stelle wörtlich." *(Q12, Q14)*
> Zusatzfeld: `"verstoesse": [{"szene": 5, "wissen": "Jonas kennt Miras Adresse", "eingefuehrt_in": null}]`

**A5b — Continuity (Zeit/Ort)**
> *Frage:* „Extrahiere für jede Szene die angegebenen Orts- und Zeitangaben und prüfe auf Widersprüche (z. B. eine Figur ist gleichzeitig an zwei Orten, Zeit läuft rückwärts ohne markierte Rückblende). Vergib 2 bei keinem Widerspruch, 1 bei einem erklärbaren, 0 bei ≥ 1 unerklärtem. Zitiere beide widersprechenden Angaben." *(Q1 Einheit; mechanisch vorprüfbar, §5)*

**A6 — Tschechows Gewehr**
> *Frage:* „Liste alle Elemente auf, die eingeführt und mit Bedeutung aufgeladen werden (Gegenstände, Geheimnisse, Ankündigungen, Drohungen, offene Konflikte), und prüfe, ob jedes später eingelöst, aufgelöst oder bewusst verworfen wird. Vergib 2, wenn alle eingelöst sind; 1 bei einem offenen Element; 0 bei ≥ 2. Zitiere die Einführungsstelle des wichtigsten uneingelösten Elements." *(Q20, Q1)*
> Zusatzfeld: `"uneingeloest": [{"element": "Vaters Brief", "eingefuehrt_szene": 2, "eingeloest_szene": null}]`

**A7 — Formfunktion (Chor/Lied/Rap/Monolog)**
> *Frage:* „Für diese Nicht-Dialog-Szene: Beantworte, ob die gewählte Form (Chor/Lied/Rap/Monolog) etwas leistet, was ein Dialog an derselben Stelle nicht leisten könnte — kommentieren, verallgemeinern, Zeit raffen, Haltung offenlegen, Publikum direkt adressieren. Vergib 2 bei klarer Eigenleistung, 1 wenn die Form nur wiederholt, was der Dialog schon gesagt hat, 0 wenn sie den Handlungsfluss ohne Gewinn unterbricht. Zitiere die Zeilen, die die Eigenleistung tragen bzw. die Redundanz zeigen." *(Q8, Q9)*

**A8 — Materialtreue zum Interviewmaterial**
> *Frage:* „Vergleiche diese Szene mit den beigefügten Interview-Auszügen. Vergib 2, wenn mindestens ein konkretes, unverwechselbares Detail aus dem Material (Formulierung, Bild, Ereignis) erkennbar weiterlebt; 1, wenn nur Themen übernommen wurden; 0, wenn die Szene das Material durch Klischees ersetzt hat. Zitiere die Szenenstelle UND die zugehörige Interviewstelle." *(Q10, Q11)*
> Zusatzfeld: `"beleg_quelle": "wörtliches Zitat aus dem Interviewmaterial"`

### Ebene B — Einzelszene

**B1 — Szenenwendung / Value Flip**
> *Frage:* „Benenne die Wertladung am Szenenanfang und am Szenenende (z. B. ‚Vertrauen +' → ‚Vertrauen −'). Vergib 2, wenn die Ladung kippt und die kippende Zeile zitierbar ist; 1, wenn sich nur die Intensität ändert; 0, wenn Anfangs- und Endzustand gleich sind. Zitiere die Zeile des Umschlags oder die letzte Zeile als Beleg für dessen Fehlen." *(Q5, Q6)*
> Zusatzfelder: `"wert": "Vertrauen", "ladung_anfang": "+", "ladung_ende": "-", "wendezeile": 24`

**B2 — Konflikt & Einsatz**
> *Frage:* „Nenne für diese Szene: (a) was Figur X konkret will, (b) wer/was es verhindert, (c) was X verliert, wenn sie es nicht bekommt. Vergib 2, wenn alle drei aus dem Text belegbar sind; 1, wenn (c) fehlt oder nur behauptet ist; 0, wenn (a) oder (b) fehlt. Zitiere die Stelle, die das Wollen am klarsten zeigt." *(Q2, Q5, Q7)*

**B3 — The Gap**
> *Frage:* „Gibt es in dieser Szene mindestens eine Handlung, deren Ergebnis anders ausfällt als die handelnde Figur erwartet hat? Antworte 2 = ja mit sichtbarer Reaktion der Figur, 1 = Abweichung vorhanden, aber ohne Reaktion, 0 = nein. Zitiere Handlung und Reaktion." *(Q5, Q6)*

**B4 — Exposition / Subtext**
> *Frage:* „Finde Repliken, in denen eine Figur einer anderen etwas erklärt, das diese laut bisherigem Verlauf bereits weiß, oder in denen eine Figur ihr eigenes Gefühl direkt benennt statt es zu zeigen. Vergib 2 bei keiner solchen Replik, 1 bei einer, 0 bei ≥ 2. Zitiere die auffälligste wörtlich." *(Q5)*

### Ebene C — Figur / Stimme

**C1 — Idiolekt / Blind-Attribution**
> *Frage:* „Dir werden die Repliken dieser Szene OHNE Figurennamen vorgelegt, dazu die Figurenprofile. Ordne jede Replik einer Figur zu. Vergib 2, wenn du ≥ 80 % korrekt zuordnest; 1 bei 50–79 %; 0 darunter. Zitiere zwei Repliken verschiedener Figuren, die austauschbar klingen." *(Q7)*
> Betrieb: Der Judge bekommt anonymisierten Text; die Auflösung erfolgt **außerhalb** des LLM durch mechanischen Abgleich mit der Ground Truth. Der LLM vergibt keinen Score, er liefert nur die Zuordnung — der Score wird berechnet. (Bias-frei, siehe §4.)
> Zusatzfeld: `"zuordnung": [{"replik_index": 0, "vermutete_figur": "Mira"}, ...]`

**C2 — Motivierte Entscheidung**
> *Frage:* „Trifft in dieser Szene mindestens eine Figur eine Entscheidung, und lässt sich ihr Motiv aus zuvor über diese Figur Etabliertem herleiten? Vergib 2 = ja, Entscheidung + herleitbares Motiv; 1 = Entscheidung, aber Motiv nur behauptet; 0 = keine Entscheidung oder Motiv widerspricht dem Etablierten. Zitiere die Entscheidung." *(Q1, Q5, Q7)*

**C3 — Beteiligung & Altersstimmigkeit**
> *Frage:* „Beantworte zwei Teilaspekte: (a) Gibt es mindestens eine Stelle, an der die Figur verwundbar wird und mitfühlbar ist? (b) Ist das Sprachregister für Spieler:innen von 15–18 Jahren sprechbar und glaubwürdig — weder feuilletonistisch überhöht noch anbiedernd jugendsprachlich? Vergib 2, wenn beides zutrifft; 1, wenn eines; 0, wenn keines. Zitiere je eine Belegstelle." *(Q14, Q16)*
> Zusatzfelder: `"beleg_verwundbarkeit": "...", "beleg_register": "..."`

---

## 3. Fan-out-Architektur: was parallel, was gebündelt

### Materialklassen (bestimmen die Bündelung)

| Klasse | Inhalt im Prompt | Fragen |
|---|---|---|
| **M1 — Szene solo** | genau eine Szene + Figurenprofile | B1, B2, B3, B4, C2, C3 |
| **M2 — Szene anonymisiert** | eine Szene ohne Sprechernamen + Profile | C1 |
| **M3 — Szene + Interviewauszüge** | eine Szene + gematchte Interviewpassagen | A8 |
| **M4 — Szene mit Formmarker** | nur Chor-/Lied-/Rap-/Monolog-Szenen | A7 |
| **M5 — Synopsen-Kette** | alle Szenen als je 3-Zeilen-Synopse + Prämisse-Feld | A1, A2, A3, A4 |
| **M6 — Volltext-Fenster** | Szenen n−2 … n im Volltext (Gleitfenster) | A5, A5b, A6 |

### Empfehlung

**Echt parallel (je 1 Aufruf, unabhängig, kein geteilter Zustand):**
B1, B2, B3, B4, C2, C3 auf M1 — sechs Aufrufe pro Szene. Sie sind bewusst *nicht* zusammengelegt, obwohl sie dasselbe Material sehen: die Ein-Frage-Regel ist der ganze Punkt des Designs (siehe Halo-Effekt in §4). Wenn Budget knapp ist, lässt sich B2+B3 zusammenlegen (beide betreffen den Konfliktmotor) und C2+C3 zusammenlegen — aber nie mehr als zwei Fragen pro Aufruf, und dann mit getrennten JSON-Objekten in einem Array, nicht mit einer gemeinsamen Note.

C1 (M2) und A8 (M3) laufen ebenfalls parallel, brauchen aber je einen *anderen* Prompt-Zusammenbau (Anonymisierung bzw. Interview-Retrieval) — Vorverarbeitung im Code, nicht im LLM.

A7 (M4) läuft nur für Nicht-Dialog-Szenen, also bedingt.

**Zwingend gebündelt / sequenziell:**

- **A1–A4 auf M5**: brauchen alle die vollständige Synopsen-Kette. Ideal wären vier separate Aufrufe mit demselben M5-Kontext (Kontext ist billig, weil Synopsen kurz sind) — also parallel bei geteiltem Material. Nur wenn Kosten drücken: A1+A4 bündeln (Prämisse und Arc hängen zusammen), A2+A3 bündeln.
- **A5/A5b/A6 auf M6**: brauchen Volltext über mehrere Szenen. Diese drei gehören in **einen** Aufruf pro Gleitfenster, weil das Volltext-Fenster teuer ist und alle drei exakt dasselbe Fenster lesen. Ausgabe: Array mit drei JSON-Objekten. Zusätzlich ist ein großer Teil davon mechanisch vorprüfbar (§5), was den LLM-Aufwand erst auf die Restfälle reduziert.
- **A6 braucht global**: Uneingelöste Elemente können erst am Ende der Folge entschieden werden. Praktikabel: mechanischer Kandidaten-Extraktor über alle Szenen (§5), dann **ein** LLM-Aufruf pro Kandidat-Cluster am Ende, nicht pro Szene.

### Geschätzte Aufrufzahl

Für ein Stück mit **S = 10 Szenen**, davon ca. 3 in Nicht-Dialog-Form:

| Block | Rechnung | Aufrufe |
|---|---|---|
| Szenenebene M1 (6 Fragen × 10 Szenen) | 6 × 10 | 60 |
| C1 anonymisiert (M2) | 1 × 10 | 10 |
| A8 Materialtreue (M3) | 1 × 10 | 10 |
| A7 Formfunktion (M4) | 1 × 3 | 3 |
| A1–A4 auf Synopsen-Kette (M5) | 4 × 1 | 4 |
| A5/A5b/A6-Fenster (M6, gebündelt, Fenster ≈ S−1) | 1 × 9 | 9 |
| A6 Abschlussprüfung uneingelöster Elemente | 1 | 1 |
| **Summe volle Prüfung** | | **≈ 97** |

**Sparvariante (empfohlen als Default im Bot):** Szenenebene auf B1, B2, B4, C1 reduzieren (4 × 10 = 40), A5/A5b/A6 erst nach mechanischer Vorfilterung nur für Verdachtsfälle aufrufen (≈ 3), Geschichtsebene voll (4), A8 nur für Szenen mit Interview-Match (≈ 5), A7 (3) → **≈ 55 Aufrufe** pro Stück. Bei kurzen Szenen (< 400 Token) sind das Sekunden bei paralleler Ausführung.

**Betriebsempfehlung:** Fan-out mit Nebenläufigkeit 8–12, harte Timeouts pro Aufruf, Retry nur bei Schema-Verletzung, Ergebnisse als JSONL in eine Datei pro Stück anhängen — dann kann der Reviewer/Bot nachträglich beliebig aggregieren, ohne neu zu prüfen.

**Aggregation → Überarbeitung:** Nicht mitteln. Regel: Jeder `score: 0` mit `schwere ∈ {blocker, hoch}` erzeugt genau einen Überarbeitungsauftrag, adressiert an die Szene, mit dem `konkreter_umbauvorschlag` als Anweisung. Maximal 3 Aufträge pro Szene pro Runde, priorisiert nach `schwere` und dann nach Ebene (Geschichte vor Szene vor Stimme) — sonst überschreibt der Schreib-LLM sich selbst.

---

## 4. Bekannte Fallen von LLM-as-a-judge — und Gegenmaßnahmen hier

| Falle | Befund in der Literatur | Gegenmaßnahme in diesem Design |
|---|---|---|
| **Position Bias** | Judges bevorzugen systematisch die erste (oder eine feste) Position im Paarvergleich (Q17, Q18). | Wir bewerten **absolut, nicht paarweise**. Wo doch verglichen wird (Varianten A/B einer überarbeiteten Szene): jeden Vergleich zweimal mit vertauschter Reihenfolge, nur übereinstimmende Urteile zählen; Uneinigkeit → „unentschieden". |
| **Verbosity / Length Bias** | Längere Antworten werden höher bewertet, unabhängig von Qualität (Q17, Q18). | Score-Definitionen sind an **zählbare Ereignisse** gebunden (kippt die Ladung? existiert das Motiv? wie viele additive Szenen?), nicht an „Qualität". Zusätzlich: Szenenlänge als Kovariate mitloggen und regelmäßig prüfen, ob Score mit Länge korreliert — tut er es, ist die Frage zu vage formuliert. |
| **Self-Enhancement Bias** | Judges bevorzugen Texte des eigenen Modells (Q17); G-Eval zeigt denselben Effekt zugunsten LLM-generierter Texte allgemein (Q19). | **Getrenntes Modell als Richter** — anderer Anbieter oder mindestens andere Modellfamilie als der Schreib-LLM. Im Bot als Konfigurationszwang: `writer_model != judge_model`, und die Kombination protokollieren. |
| **Note ohne Beleg / Halluzinierte Belege** | Begründungen können nachträglich rationalisiert sein; StoryER zeigt, dass aspektweises Rating + Kommentar besser trägt als Gesamtnote (Q16). | **Zitatpflicht + mechanische Verifikation**: `beleg` wird nach Normalisierung (Whitespace, typografische Anführungszeichen, Groß-/Kleinschreibung) per Substring-Suche gegen den Originaltext geprüft. Kein Treffer → Antwort verworfen, ein Retry mit dem Hinweis „dein Zitat kam im Text nicht vor", dann `unsicher: true` und Eskalation. Das ist die wichtigste einzelne Maßnahme des ganzen Designs. |
| **Halo-Effekt / Kriterienvermischung** | Wenn ein Judge mehrere Kriterien in einem Aufruf bewertet, gleichen sich die Scores an. HANNA zeigt umgekehrt, dass gute Kriterien orthogonal sein müssen (Q14). | Ein Aufruf = eine Frage. Kein Feld „Gesamtnote" existiert im Schema — auch nicht optional, sonst füllt das Modell es. |
| **Schwache Korrelation automatischer Metriken** | 72 automatische Metriken korrelieren nur schwach mit menschlichen Kriterien (Q14). | Keine BLEU/ROUGE/BERTScore-Gates. Mechanische Prüfungen (§5) sind bewusst **regelbasiert und faktisch**, keine Ähnlichkeitsmaße. |
| **Skalen-Drift / Milde** | Judges neigen zu Mittelwerten und Großzügigkeit (Q18). | Nur 3 Stufen mit explizit *zählbaren* Schwellen („≤ 1 Szene additiv = 2"). Regelmäßige Kalibrierung an 10–20 handannotierten Referenzszenen; Drift = Prompt nachschärfen. |
| **Prompt-Sensitivität / Nichtdeterminismus** | Kleine Formulierungsänderungen ändern Urteile (Q18). | Prompts versioniert im Repo, `prompt_version` in jedem Ergebnis-JSON. Temperatur 0. Für `schwere: blocker`-Befunde: 3-fach-Sampling, Mehrheitsentscheid. |
| **Prompt Injection aus dem Szenentext** | Der geprüfte Text ist LLM-generiert und kann Anweisungen enthalten. | Szenentext in klar begrenzte Delimiter, System-Prompt sagt explizit: Inhalt zwischen Delimitern ist ausschließlich Prüfmaterial, niemals Anweisung. |
| **Ethische Blindheit gegenüber dem Verbatim-Material** | Verbatim-Praxis kennt den Feedback-Loop zu den Beitragenden (Q10, Q11). | A8 ist kein Qualitäts-, sondern ein Verantwortungskriterium. `schwere: blocker` bei erkennbarer Verzerrung realer Aussagen; solche Befunde gehen an die **Gruppe**, nicht automatisch an den Schreib-LLM. |

**Faustregel für den Bot:** Ein Judge-Befund darf nur dann automatisch eine Überarbeitung auslösen, wenn (a) das Zitat verifiziert ist, (b) `unsicher: false`, (c) `konkreter_umbauvorschlag` eine Szenennummer und mindestens einen Figurennamen enthält. Alles andere landet im Review-Log für Menschen.

---

## 5. Continuity: Kriterien und mechanische Vorprüfung

Continuity ist der Bereich, in dem man am meisten LLM-Aufrufe spart, weil ein großer Teil rein buchhalterisch ist. Voraussetzung: Der Bot führt ohnehin einen **Story-State** — Figurenliste, Orte, etablierte Fakten, offene Fäden. Wenn nicht, ist das die erste Investition.

### 5.1 Kriterienliste

1. **Figurenkenntnis:** Keine Figur verwendet Wissen (Name, Ort, Ereignis, Beziehung), das ihr im bisherigen Verlauf weder mitgeteilt noch zugänglich war.
2. **Figurenexistenz & Namensstabilität:** Jede sprechende oder erwähnte Figur ist im Figurenverzeichnis; keine Namensvarianten (Mira/Mirijam/Miri) ohne Absicht.
3. **Zeitlogik:** Zeitangaben sind monoton, außer bei markierten Rückblenden; Zeitsprünge sind mindestens einmal benannt.
4. **Ortslogik:** Keine Figur ist gleichzeitig an zwei Orten; Ortswechsel sind erklärbar; die Zahl gleichzeitig anwesender Figuren bleibt in einer Szene konsistent (niemand spricht nach seinem Abgang).
5. **Objektlogik:** Ein Objekt wechselt Besitzer nur durch gezeigte oder erzählte Übergabe.
6. **Tschechows Gewehr:** Jedes aufgeladene Element wird eingelöst, aufgelöst oder ausdrücklich verworfen.
7. **Offene Konflikte:** Jeder in einer Szene eröffnete Konflikt wird bis zum Stückende eskaliert, gelöst oder als bewusst offen markiert.
8. **Roter Faden / Prämissenbindung:** Jede Szene lässt sich auf die Prämisse (A1) beziehen; Szenen ohne Bezug sind Kandidaten für Streichung.

### 5.2 Was mechanisch (ohne LLM) prüfbar ist

Diese Checks laufen deterministisch über die strukturierten Szenendaten und produzieren **Verdachtslisten**, die dann gezielt an den Judge gehen:

| Check | Verfahren | Ergebnis |
|---|---|---|
| **Namensstabilität** | Alle Sprecher-Labels + im Text erwähnte Eigennamen extrahieren; Abgleich gegen Figurenverzeichnis; Fuzzy-Match (Levenshtein ≤ 2) meldet Varianten. | Harte Fehler, sofort korrigierbar — **kein LLM nötig**. |
| **Geisterfiguren** | Sprecher-Label nicht im Verzeichnis → Fehler. Figur im Verzeichnis, die nie spricht und nie erwähnt wird → Warnung. | Hart. |
| **Erstauftritt-Register** | Für jede Figur die Szene ihres ersten Auftritts festhalten. Wird sie vorher von einer anderen Figur beim Namen genannt, ohne dass die Nennung erklärt ist → Verdacht für A5. | Verdachtsliste. |
| **Wissens-Ledger** | Pro Szene eine kleine Faktenliste pflegen (`fakt_id`, `bekannt_fuer: [Figuren]`, `eingefuehrt_in_szene`). Wenn eine Szene einen Fakt einer Figur zuschreibt, die nicht in `bekannt_fuer` steht → Verdacht. Das Ledger kann beim Schreiben mitgeschrieben werden (der Schreib-LLM liefert es als Nebenausgabe), die **Prüfung** ist dann reine Mengenlehre. | Verdachtsliste für A5, sehr treffsicher. |
| **Anwesenheitsmatrix** | Aus Szenenkopf (Ort, Figuren) + Auftritts-/Abgangsregieanweisungen eine Matrix bauen. Spricht eine Figur, die laut Matrix abgegangen oder nie aufgetreten ist → harter Fehler. Steht eine Figur in zwei parallel datierten Szenen an zwei Orten → harter Fehler. | Hart, **kein LLM nötig**. |
| **Zeitachse** | Zeitangaben aus Szenenköpfen parsen (relative wie „am nächsten Morgen" per kleiner Regelliste). Nicht-monotone Folge ohne `rueckblende: true` → harter Fehler. | Hart. |
| **Objekt-Tracking** | Objektliste pflegen (`objekt`, `besitzer`, `szene`). Besitzerwechsel ohne Übergabe-Ereignis → Verdacht. | Verdachtsliste. |
| **Tschechow-Kandidaten** | Alle Substantive/Nominalphrasen sammeln, die (a) in mindestens einer Regieanweisung oder Requisitenliste stehen ODER (b) in einer Szene ≥ 2-mal vorkommen, und dann in keiner späteren Szene mehr auftauchen. Ergebnis: Kandidatenliste „eingeführt, nie wieder erwähnt". | Verdachtsliste für A6 — reduziert A6 von „ganzes Stück lesen" auf „5 Kandidaten prüfen". |
| **Offene Konflikte** | Konfliktregister: Jede Szene bekommt beim Schreiben ein Feld `konflikt_eroeffnet` / `konflikt_geschlossen` (IDs). Am Ende: alle IDs ohne Schließung listen. | Hart, sofern das Register geführt wird. |
| **Roter Faden** | Reine Struktur-Heuristik: Szenen, in denen die Hauptfigur nicht vorkommt UND kein im Prämissensatz genanntes Motiv-Stichwort erscheint, markieren. | Schwache Verdachtsliste — muss durch A1/A2 bestätigt werden. |
| **Formverteilung** | Zählen: wie viele Szenen je Form (Dialog/Monolog/Chor/Lied/Rap), Position im Stück. Reine Warnung bei Klumpung (z. B. 3 Songs hintereinander) oder Nichtnutzung einer versprochenen Form. | Hart. |
| **Sprechanteile** | Wortanteil pro Figur über das ganze Stück. Für Laiengruppen praktisch relevant: Figuren mit < 3 % Anteil sind für die Spielerin frustrierend. | Hart, gruppenrelevant. |
| **Belegverifikation** | Substring-Match der Judge-Zitate gegen den Originaltext (§4). | Hart, obligatorisch. |

**Was NICHT mechanisch geht** und deshalb beim LLM bleibt: ob ein Element wirklich „aufgeladen" war (Tschechow braucht semantisches Gewicht), ob Wissen „plausibel erschließbar" war, ob ein Konflikt inhaltlich gelöst oder nur weggeschrieben wurde, ob eine Szene die Prämisse trägt.

**Wirkung:** In der Praxis fängt die mechanische Schicht die peinlichen Fehler (Namensdrift, Geisterfiguren, Sprechen nach dem Abgang, Zeitsprünge) vollständig ab — genau die Fehler, die Jugendliche beim Lesen sofort bemerken und die Vertrauen kosten. Der Judge-LLM wird dann nur noch für die semantischen Fragen bezahlt.

---

## 6. Umsetzungsreihenfolge (Empfehlung)

1. **Story-State + mechanische Checks** (Namensstabilität, Anwesenheitsmatrix, Zeitachse, Tschechow-Kandidaten). Ohne LLM, sofortiger Nutzen, Grundlage für alles Weitere.
2. **Belegverifikation** als Bibliotheksfunktion — bevor der erste Judge scharf geschaltet wird.
3. **B1 (Value Flip) als erste Judge-Frage.** Höchster Ertrag pro Aufruf: findet die typische LLM-Plauderszene zuverlässig.
4. **A1 + A2** auf der Synopsen-Kette. Findet strukturelles Auseinanderfallen früh, wenn Umbau noch billig ist.
5. **C1 (Blind-Attribution)** — bei LLM-Szenen fast immer ein Treffer und für die Gruppe unmittelbar einleuchtend.
6. Rest nach Bedarf; A8 nur, wenn die Interview-Zuordnung technisch steht.

---

*Erarbeitet auf Basis der in §0 gelisteten 20 Quellen. Dramaturgische Primärkonzepte sind Aristoteles, Freytag, Egri, McKee, Yorke, Brecht, Tschechow und der Verbatim-Diskurs; die Evaluationsmethodik stützt sich auf HANNA, StoryER, G-Eval sowie die Bias-Literatur zu LLM-as-a-judge.*

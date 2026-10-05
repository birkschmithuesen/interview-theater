# Flow-Audit -- Klasse-B-Befunde (04.10.2026, Phase 1+2)

Gefunden vom neuen dreischichtigen Flow-Audit (`simulation/flow_audit.py`,
`simulation/flow_audit_dynamisch.py`, `scripts/flow_audit_lauf.py`) --
Schicht 1 statisch (0 Befunde), Schicht 2 dynamisch gegen den echten
Bot-Code (offline per Attrappe UND, einmal, real gegen Kimi/Erkenner +
Sonnet-Richter). Nicht behoben -- jeder Fix ist entweder eine
Design-Entscheidung mit mehr als einer sinnvollen Loesung oder braucht
Birks Entscheidung zum Wortlaut. Sortiert nach Schwere.

1. **Phase 2 · Frage per Chat annehmen.** Ein zustimmendes "yes, that
   one's good" waehrend "Fragen einzeln durchgehen" entscheidet die Frage
   nicht -- jede freie Chat-Nachricht wird als Schaerfungswunsch gelesen
   (`knoepfe.fragen.nimm_offene_frage_text`), nie als Zustimmung; nur der
   "Accept"-Knopf wirkt. Reproduziert offline UND im echten Lauf (Sonnet-
   Richter: 0/2 auf allen sechs Fragen). Vorschlag: entweder einen
   phase-2-gebundenen Erkenner-Intent nach dem Muster
   `schaerfung_entscheidung` ergaenzen, oder `nimm_offene_frage_text`
   selbst um eine kleine Zustimmungs-Erkennung erweitern. Frage: Soll ich?

2. **Phase 2 · Wartezustand beim Hintergrundvergleich.** Waehrend der
   A/B-Gegenueberstellung (eigene vs. KI-Fragen) lief im echten Lauf keine
   sichtbare Tippanzeige -- die Gruppe sieht keinen Hinweis, dass im
   Hintergrund noch etwas passiert (Richter: 0/2 auf "weiss ich, wo wir
   sind"). Vorschlag: eine deterministische Zwischenzeile oder laengere
   Tippanzeige fuer diesen Hintergrundlauf. Frage: Soll ich?

3. **Phase 1 · Begriffs-Vorschlag im Chat.** Im echten Lauf wiederholte
   sich die Bot-Antwort einmal dreifach in einer Nachricht und vergrub die
   eigentliche Frage in viel Text (Richter: 0/2 auf "knapp im richtigen
   Moment"). Einzelbeobachtung, nicht reproduziert offline. Vorschlag:
   beobachten, ob das bei weiteren echten Laeufen wiederkehrt, bevor am
   Prompt gedreht wird. Frage: Soll ich einen zweiten echten Lauf
   ansetzen, um das zu bestaetigen?

## Hinweis zur Audit-Methode selbst (keine Bot-Luecke)

Zwei weitere mechanisch rote Befunde aus dem echten Lauf ("Priya schreibt
eine eigene Frage", "Priya korrigiert einen Begriff im Chat") sind nach
Lesen der woertlichen Bot-Antworten **wahrscheinlich keine echten
Holzwege**: in beiden Faellen stellte das Gespraechsmodell eine
Rueckfrage, bevor es etwas speicherte -- genau das Verhalten, das
`prompts/phasen/1.md`/`workshop/padua-2026/prompts/phasen/2.md` fuer eine
wirklich unklare Aeusserung ausdruecklich vorschreiben ("Erst fragen, dann
vorschlagen"). Der Audit-Lauf spielt pro Station nur EINE Nachricht --
Priyas (bewusst zoegerliche) Formulierung bekam dadurch nie die Chance,
auf die Rueckfrage zu antworten. Das ist eine bekannte Grenze des
heutigen Werkzeugs (einzuege Nachricht je Station), kein Befund ueber den
Bot. Vorschlag fuer eine Folgekarte: Stationen mit einer zweiten,
klaerenden Nachricht ausstatten, bevor "wirkungslos" gewertet wird.

## Abnahme- und END-Schritt: Prompt-Check

Der Prompt-Check ist seit dem 05.10.2026 (Karte t_1dcf3864) ein **fester
Schritt** jeder Abnahme und jedes END -- nicht, weil Prompts huebsch sein
sollen, sondern weil sie heiss nachgeladen werden und sich deshalb zwischen
zwei Abnahmen aendern, ohne dass jemand es sieht. Gemessen: zwischen dem
02.10. und dem 05.10.2026 wuchs der Systemprompt der Phase 1 um rund 1 762
Zeichen, und niemand hatte diese Drift benannt.

Die Befehlsfolge (alle drei kosten 0 CHF, Details in
`simulation/README.md`, Abschnitt „Der Prompt-Check"):

```
python3.11 -m pytest -q -m "not dortmund" tests/test_modellaufrufe_inventar.py
python3.11 -m scripts.erzeuge_prompts_padua_voll docs/prompt-audit/<datum>-padua-voll
python3.11 -m scripts.pruefe_prompt_dumps docs/prompt-audit/<datum>-padua-voll \
    --basis <letzter-audit>/uebersicht.tsv
python3.11 -m scripts.pruefe_prompts_lesung docs/prompt-audit/<datum>-padua-voll
python3.11 -m scripts.pruefe_profil padua-2026
```

**Die Pass-Regel:** abgenommen ist, wenn **kein Befund der Klassen (a)
Prompt<->Regel und (b) Prompt<->Prompt ohne Eigentuemer dasteht**. Ein Befund
hat einen Eigentuemer, wenn er entweder behoben (mit einem Test, der den
Wortlaut nagelt) oder einer anderen Karte zugeschrieben (z. B. „liegt bei
t_0b702d1d") oder mit Empfehlung auf der Birk-Liste des BEFUND steht. Die
Klassen (c) tot/veraltet und (d) Kontextstruktur sind Arbeitsvorrat und
blockieren keine Abnahme.

**Was NICHT blockiert:** ein Treffer im mechanischen Pruefer allein (er ist ein
Bericht, Exit immer 0) und ein als `unsicher` verworfener Opus-Befund (ein
verworfener Befund ist keiner).

**Was sehr wohl blockiert:** ein rotes
`tests/test_modellaufrufe_inventar.py` -- dann gibt es einen Modellaufruf, den
der Check nicht sieht, und jede Aussage „wir haben alle Prompts geprueft" waere
falsch.

**Stand des ersten Laufs** (`docs/prompt-audit/2026-10-05-padua-voll/`,
05.10.2026): Dump und mechanischer Pruefer sind durchgelaufen (38 Dumps,
`mechanik.md`); die Opus-Lesung selbst ist in dieser Session **nicht**
abgeschlossen worden -- Ursache ist ein hartcodiertes 120-Sekunden-Timeout in
`simulation/claude.py`, das die rechenaufwendige Lesungsaufgabe konsequent
abschneidet, keine Erreichbarkeits- oder Prompt-Luecke (siehe BEFUND.md,
Abschnitt 7). Ohne eine durchgelaufene Lesung gibt es aus diesem Lauf keine
Kategorie-a/b-Befunde zu bewerten; die Pass-Regel oben konnte deshalb in
diesem Lauf noch nicht am echten Fall demonstriert werden, bleibt aber die
geltende Regel fuer den naechsten Lauf, sobald die Lesung durchlaeuft.

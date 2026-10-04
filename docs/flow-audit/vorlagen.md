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

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

## Flow-Audit -- Phase 3+4 (04.10.2026)

Erweiterung des Flow-Audits (t_92f99911) auf Phase 3 (Interviews) und
Phase 4 (Setting, Figuren & Geschichte) -- Schicht 1 statisch (0 rote
Befunde nach einer Korrektur, siehe Commit c41e286), Schicht 2 dynamisch
(13 neue Stationen, offline UND einmal real gegen Kimi/Erkenner +
Opus-Richter, Sonnet-Beschraenkung der Vorkarte aufgehoben). Sortiert nach
Schwere, hoechstens 5.

1. **Phase 4 · Die Geschichte per Chat erzaehlen.** Erzaehlt die Gruppe den
   Bogen und das Ende ihrer Geschichte frei im Chat, speichert der ECHTE
   Erkenner das als `hauptkonflikt_setzen`, nicht als `geschichte_setzen`
   -- `arbeitsstand.geschichte` bleibt leer. Da `geschichte` eine
   Voraussetzung fuer Phase 5 ist (`phasen.voraussetzungen[5]`), kann eine
   Gruppe so erleben, dass sie ihre Geschichte "erzaehlt" hat und trotzdem
   nicht weiterkommt. Nur am echten Modell sichtbar (Schicht 2 offline mit
   der Attrappe war gruen, weil dort die Absicht direkt vorgegeben wurde)
   -- Opus-Richter: `fuehle_ich_mich_als_urheberin` 1/2,
   `kommt_mein_feedback_an` 1/2. Vorschlag: den Erkenner-Prompt
   praezisieren, wann "die Geschichte" statt "der Hauptkonflikt" gemeint
   ist (ein freier Bogen+Ende-Satz sollte `geschichte_setzen` ausloesen),
   oder die beiden Felder im Arbeitsstand zusammenlegen. Frage: Soll ich
   einen Korpusfall dafuer anlegen und gegen das echte Modell pruefen
   (kostet Geld, FP=0-Regel)?

2. **Phase 3 · Ein laufendes Interview per Chat verwerfen.** Eine
   beilaeufige Formulierung ("can we just delete this one and start over")
   fuehrt beim echten Erkenner NICHT zu einer konkreten
   `entfernen interview N`-Absicht (anders als beim Mutationsprobe-Test in
   Schicht 2, der die Absicht direkt vorgab). Staerker noch: der
   Gespraechs-Bot antwortete im echten Lauf, man koenne "von hier aus"
   nichts loeschen und solle das Workshop-Team kontaktieren -- das ist
   sachlich falsch, `entfernen interview <Nummer>` koennte genau das. Nur
   am echten Modell sichtbar. Vorschlag: den Erkenner-Prompt um ein
   Beispiel fuer diese Phrasierung ergaenzen, UND die Phase-3-Anweisung
   (`prompts/phasen/3.md`/die englische Fassung) korrigieren, damit der
   Bot die Loeschmoeglichkeit nicht abstreitet. Frage: Soll ich?

3. **Phase 2 (ausserhalb dieser Karte, aber im selben echten Lauf
   gemessen) · Begriffsboard-Korrektur im Chat.** Im echten Lauf zeigte die
   Antwort die korrigierte Sechser-Liste im Chattext an, schrieb sie aber
   nicht in `arbeitsstand.begriffe`/`begriffe_detail` -- in der Attrappe
   (Schicht 2, Task t_2cdea48b) war genau diese Zeile gruen. Ein
   Unterschied, der nur am echten Modell sichtbar wird, und der zur
   VORIGEN Karte gehoert (hier nur vermerkt, nicht behoben). Frage: Soll
   ich das dort nachtragen?

4. **Dokumentation: die Phase-2-Zeile "Direkt aus Phase 1 oder 2 heraus
   eine Interview-Aufnahme per Chat starten" in `flow_erwartungen.toml`**
   (Karte t_2cdea48b) beschreibt `interview_starten` ungenau als
   tatsaechlich startend. Diese Karte hat die analoge Phase-3-Zeile dafuer
   bereits korrigiert (Commit c41e286, `weg = "knopf"` statt `"beides"` --
   der Chat bietet nur den Start-Knopf an, `befehle._befehl_aufnahme`
   startet wirklich). Frage: Soll ich dieselbe Korrektur auch an der
   Phase-2-Zeile nachtragen (gehoert zu t_2cdea48b)?

5. **`aufnahme._phasenfrage` ist toter Code.** Seit dem 05.09.2026 hat die
   Funktion keinen einzigen Aufrufer mehr (Kommentar an der Stelle, wo sie
   herausgenommen wurde: "die Gruppe macht ein Interview nach dem anderen
   und entscheidet selbst, wann sie weitergeht") -- AGENTS.md beschreibt
   sie aber weiterhin als aktiven Mechanismus fuer "Kommen noch Interviews,
   oder gehen wir ans Kernthema?". Der tatsaechlich wirkende Weg ist
   ausschliesslich `kontext._baue_phasenhinweis` (im naechsten
   Gespraechszug, nicht an der Verdichtungsnachricht), dynamisch bestaetigt
   in Station 21 (offline und real: genau einmal). Vorschlag:
   `aufnahme._phasenfrage` entfernen und den AGENTS.md-Absatz "Die Phase
   setzt allein die Gruppe" entsprechend aktualisieren. Frage: Soll ich?

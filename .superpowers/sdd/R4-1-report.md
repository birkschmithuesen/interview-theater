# R4-1 – H3, M5, H2 (Padua P2, Erkenner gegen den Einzeldurchgang)

Nur Code, keine Prompts, `knoepfe/fragen.py` unberuehrt (B4).

## H3 – "Removed: Questions" mitten im Durchgang

sim.db erkenner_lauf 24 / schritt 28: `entfernen FRAGEN` leerte alle sieben
eigenen Fragen. Fix `erkenner.entferne`: Ziel `fragen`, `quelle="erkenner"`
und `knoepfe.einzeln_aktiv` -> still `None` (nur Log), wie der bestehende
Schutz fuer `fragen_setzen`. Ein getippter Befehl (`quelle="befehl"`)
entfernt weiter (ausdruecklicher Wunsch). Andere Durchgangsfelder sind nicht
ueber `entfernen` erreichbar (`_ENTFERNEN_ARBEITSSTAND` kennt nur `fragen`).

## M5 – "So geht ein Interview" deutsch

`erkenner._interviewmodus_texte` liest jetzt `knoepfe.texte.T.TEXT_ABLAUF`
(EN-Eintrag `sprachen/en/texte.toml:83`).

## H2 – Phase 3 aus der Nachricht, die den Vergleich startet

Merker wie R3-3, aber in `ablauf` gesetzt (nicht in `knoepfe/fragen.py`):
`ablauf.antworte` liest vor dem Zug `(fragen_eigene_erstellt_am gesetzt,
einzeln_aktiv)` und im `finally` noch einmal; schaltet einer davon in diesem
Zug ein, gilt `_vergleich_im_zug[chat_id] = letzte_message_id`.
`erkenner.laufe` holt ihn vor `erkenne` ab (`nimm_vergleich_im_zug`, nur
wenn die Nachricht im Stapel `repo.unextrahierte` liegt, gilt einen Lauf) und
streicht `phase_setzen` aus den Aenderungen (keine "Noted: phase"-Meldung,
auch kein Angebot ueber `_erneuere_angebot_auf_bitte`). Eine spaetere
Nachricht wechselt die Phase wie immer (Invariante). Auch der Fall "KI-Fragen
noch nicht fertig" ist abgedeckt (`fragen_eigene_erstellt_am` schaltet ein).

## Tests

- neu `tests/test_erkenner_durchgang_schutz.py` (7, ohne Fix 4 rot): Repro
  lauf 24, Gegenproben (ausserhalb Durchgang, Befehl), EN-Ablauftext, H2
  gleiche Nachricht -> Phase 2 ohne Meldung, spaetere Nachricht -> Phase 3,
  Gegenprobe ohne Vergleichsstart -> Phase 3.
- `tests/conftest.py`: autouse-Reset auch fuer `ablauf._vergleich_im_zug`.
- Gezielt gruen: test_erkenner*, test_begriffe*, test_phase2_einzeln,
  test_p2_livefix, test_fragen*, test_knoepfe_struktur, test_sprache_texte,
  test_ablauf*, test_bot, test_undo*, test_befehle, test_profil_bitgleich,
  test_fixture_padua_voll, test_simulation_lauf/birk, test_flow_audit_lauf u. a.
  (2151 + 562 passed).

## Offen / Hinweise

- Merker ist Prozessspeicher (wie R3-3): Neustart zwischen Zug und Erkenner
  -> alter Fehler moeglich.
- Ein KI-Hintergrundlauf (`fragen_ki.starte`), der zufaellig waehrend eines
  Zugs den Durchgang offenbart, setzt den Merker fuer diese Nachricht mit --
  ihr `phase_setzen` faellt dann ebenfalls weg (selten, harmlos: die Gruppe
  kann es wiederholen).
- `_biete_phase_an` ("The material would allow phase 3") bleibt unveraendert;
  Ursache S2 (vorzeitiges `fragen` durch den Erkenner) ist B4.
- M6 (Freitext ueberschreibt Karte) nicht angefasst (B4).

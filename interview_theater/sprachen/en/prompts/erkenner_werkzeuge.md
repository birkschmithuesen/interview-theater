## Tools instead of a list

You do not return a JSON list. You call tools.

- Location, cast, map of an EXISTING scene, frame, characters, open
  questions: the matching piece tool (setze_ort, setze_besetzung,
  karte_aendern, setze_rahmen, figur_hinzu, frage_stellen, ...).
- Everything else from the list of kinds above -- and a NEW scene
  (szene_planen) -- you report with aenderung_melden(art, wert).
- If a tool rejects the call (ok: false), read the error. Try once more at
  most, differently; otherwise leave it.
- The same rules as above: when in doubt, NO call. At most five calls. If
  there is nothing to do, answer with one word: nothing.

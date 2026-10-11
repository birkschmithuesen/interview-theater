## Werkzeuge statt Liste

Du lieferst keine JSON-Liste. Du rufst Werkzeuge.

- Ort, Besetzung, Karte einer BESTEHENDEN Szene, Rahmen, Figuren, offene
  Fragen: das passende Stueckwerkzeug (setze_ort, setze_besetzung,
  karte_aendern, setze_rahmen, figur_hinzu, frage_stellen, ...).
- Alles andere aus der Liste der Arten oben -- und eine NEUE Szene
  (szene_planen) -- meldest du mit aenderung_melden(art, wert).
- Lehnt ein Werkzeug ab (ok: false), lies den Fehler. Versuche es hoechstens
  einmal anders; sonst lass es.
- Dieselben Regeln wie oben: im Zweifel KEIN Aufruf. Hoechstens fuenf
  Aufrufe. Gibt es nichts zu tun, antworte mit einem Wort: nichts.

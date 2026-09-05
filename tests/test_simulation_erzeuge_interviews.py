"""Der Generator der fuenfzehn Transkripte -- die Pruefungen, ohne Netz.

Das Skript selbst laeuft nie automatisch (es kostet Modellzeit und schreibt
ins Repository). Was hier geprueft wird, ist sein Gewissen: ``pruefe``. Wenn
die Funktion etwas durchlaesst, entsteht eine Datei, die
``tests/test_simulation_material.py`` anschliessend rot macht -- und niemand
weiss, welcher der vier Versuche schuld war.
"""

from simulation import erzeuge_interviews as gen
from simulation import material

GUT = {
    "themen": ["Koffer", "Warten", "Kopfkissen"],
    "sprachmerkmale": ["kurze Saetze", "Abbrueche", "tuerkische Einsprengsel"],
    "zitate_soll": [
        "Ein Koffer und eine Tuete mit Brot.",
        "Nimm das Kopfkissen mit, dann schlaefst du.",
        "Ich habe den Koffer nie ausgepackt.",
    ],
    "transkript": (
        "Leyla: Was hattest du dabei?\n\n"
        "Meryem: Ein Koffer und eine Tuete mit Brot. Mehr halt nicht. Also, "
        "doch, ein Kopfkissen. Meine Mutter hat gesagt: Nimm das Kopfkissen "
        "mit, dann schlaefst du.\n\n"
        "Leyla: Und heute?\n\n"
        "Meryem: Ich habe den Koffer nie ausgepackt. " + "Und so weiter. " * 90
    ),
}


def test_ein_sauberes_ergebnis_geht_durch():
    assert gen.pruefe(GUT, "Meryem") == []


def test_die_wortzahl_wird_an_denselben_grenzen_gemessen_wie_im_test():
    kurz = {**GUT, "transkript": "Leyla: Was?\n\nMeryem: Ein Koffer und eine "
                                 "Tuete mit Brot. Nimm das Kopfkissen mit, dann "
                                 "schlaefst du. Ich habe den Koffer nie "
                                 "ausgepackt. halt"}
    fehler = gen.pruefe(kurz, "Meryem")
    assert any(str(material.WOERTER_MIN) in f for f in fehler)


def test_ein_zitat_das_nur_fast_dasteht_faellt_durch():
    """Geprueft wird mit ``zitat.pruefe`` -- der Funktion, die im Betrieb
    entscheidet. Eine mildere Pruefung liesse Zitate durch, die die Kennzahl
    ``zitate_soll`` anschliessend nie findet."""
    fast = {**GUT, "zitate_soll": [
        "ein koffer und eine tuete mit brot",   # Kleinschreibung
        "Nimm das Kopfkissen mit, dann schlaefst du.",
        "Ich habe den Koffer nie ausgepackt.",
    ]}
    fehler = gen.pruefe(fast, "Meryem")
    assert any("zeichengenau" in f for f in fehler)


def test_genau_drei_sollzitate():
    fehler = gen.pruefe({**GUT, "zitate_soll": GUT["zitate_soll"][:2]}, "Meryem")
    assert any("verlangt sind 3" in f for f in fehler)


def test_kommas_in_den_stichwortlisten_werden_abgelehnt():
    """Der Kopf schreibt sie als ``[a, b, c]`` -- ein Komma im Stichwort
    zerrisse den Eintrag beim Lesen lautlos in zwei."""
    fehler = gen.pruefe({**GUT, "themen": ["Koffer, gross", "Warten", "Brot"]},
                        "Meryem")
    assert any("Kommas" in f for f in fehler)


def test_umlaute_werden_abgelehnt():
    mit_umlaut = {**GUT, "transkript": GUT["transkript"].replace("Saetze", "Sätze")
                  + " Straße"}
    assert any("Umschrift" in f for f in gen.pruefe(mit_umlaut, "Meryem"))


def test_ohne_dialogform_faellt_es_durch():
    ohne = {**GUT, "transkript": GUT["transkript"].replace("Leyla:", "Frage:")}
    assert any(gen.INTERVIEWERIN in f for f in gen.pruefe(ohne, "Meryem"))


def test_geschriebene_statt_gesprochener_sprache_faellt_auf():
    glatt = {
        **GUT,
        "zitate_soll": ["Der Koffer stand im Flur."],
        "transkript": "Leyla: Frage.\n\nMeryem: Der Koffer stand im Flur. "
                      + "Ein Satz mehr. " * 100,
    }
    assert any("gesprochen" in f for f in gen.pruefe(glatt, "Meryem"))


def test_leeres_transkript_bricht_sofort_ab():
    assert gen.pruefe({**GUT, "transkript": "  "}, "Meryem") == [
        "Feld 'transkript' ist leer."
    ]


def test_der_kopf_wird_von_material_wieder_gelesen(tmp_path):
    """Der Rundlauf: was der Generator schreibt, muss ``material.lade``
    einlesen koennen -- Listenform, Soll-Zitate mit Kommas darin, alles."""
    pfad = tmp_path / "1-meryem-koffer.md"
    pfad.write_text(
        gen._kopf("Meryem", 1, GUT) + "\n" + GUT["transkript"], encoding="utf-8"
    )
    geladen = material.lade(pfad)
    assert geladen.name == "Meryem"
    assert geladen.nummer == 1
    assert geladen.themen == ("Koffer", "Warten", "Kopfkissen")
    assert geladen.zitate_soll == tuple(GUT["zitate_soll"])


def test_die_besetzung_deckt_alle_fuenfzehn_dateien_ab():
    """Namen und Motive stehen fest -- sonst zoege ``--set 1 --seed 1`` nach
    einer Neuerzeugung andere Dateien, und zwei Laeufe waeren nicht mehr
    vergleichbar."""
    kennungen = {k for _, k, _, _ in gen.BESETZUNG}
    dateien = {p.stem for p in material.VERZEICHNIS.glob("set*/*.md")}
    assert kennungen == dateien
    assert len(gen.BESETZUNG) == len(material.SETS) * material.PRO_LAUF

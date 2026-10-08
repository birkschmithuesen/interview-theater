"""Deterministische Sprachmessung (P7-Audit-Karte, Klasse 5: Englisch an
italienische Gruppen).

Die Positiv-Fixtures sind woertlich aus dem echten Live-Fall (Padua-
Nachtlauf 08.10.2026, VACUUM-Kopie einer echten Datenbank, NIE die
Live-Datenbank selbst -- nur extrahierte Werte ins Repo): Systemzeilen, die
VOR den Commits a5ab681/b954c37 englisch an italienische Gruppen gingen. Die
Negativ-Fixtures sind echte italienische Bot-Antworten derselben Gruppen aus
Phase 7, aus demselben Nachtlauf."""

from interview_theater import sprachmessung

# --- echte Fundstellen, Padua G1-G3, vor dem Fix (08.10.2026, vor 14:47) ---

ECHTE_ENGLISCHE_FUNDE = [
    'Recording is on. When the interview is over, tap "■ Stop".',
    'This is how an interview works: tap "Start interview". Then send the '
    'voice message or voice messages of your interviewee - after each one '
    'you get the typed-out text and tell me with a button whether to keep it.',
    "I've read this as the order of places around the table, not the order "
    "of arrival. The stranger sits between Silvio and Francesco, and "
    "'saresti l'ultimo' stays true.",
]

# --- echte italienische Bot-Antworten derselben Gruppen, Phase 7 ----------

ECHTE_ITALIENISCHE_POSTS = [
    "La scena 1 di 3 (Tornare a casa) è nella scheda Script. Leggetela lì "
    "-- va bene così? Altrimenti dimmi cosa deve cambiare.",
    "Sto riscrivendo lo stage script per la scena 1.",
    "Sì, la scena 1 è già nella scheda Script. Cosa deve cambiare nella "
    "scena 1? Scrivilo in un messaggio.",
    "Riscrivo la scena 1 con la vostra modifica -- circa un minuto. Poi "
    "qui di nuovo Yes, save / No, change.",
]


def test_ist_englisch_erkennt_die_echten_funde():
    for text in ECHTE_ENGLISCHE_FUNDE:
        assert sprachmessung.ist_englisch(text), text


def test_ist_englisch_erkennt_italienische_antworten_nicht():
    for text in ECHTE_ITALIENISCHE_POSTS:
        assert not sprachmessung.ist_englisch(text), text


def test_ist_englisch_einzelnes_englisches_knopfwort_zaehlt_nicht():
    """Ein Knopfname wie 'Yes, save' mitten in einem italienischen Satz
    darf keinen Treffer ausloesen -- ``_MINDESTTREFFER`` faengt das ab."""
    text = "Poi qui di nuovo Yes, save / No, change."
    assert not sprachmessung.ist_englisch(text)


def test_anteil_englisch_ueber_die_echten_posts():
    alle = ECHTE_ITALIENISCHE_POSTS + ECHTE_ENGLISCHE_FUNDE
    anteil = sprachmessung.anteil_englisch(alle)
    assert anteil == len(ECHTE_ENGLISCHE_FUNDE) / len(alle)


def test_anteil_englisch_ohne_texte_ist_null():
    assert sprachmessung.anteil_englisch([]) == 0.0


def test_anteil_englisch_rein_italienisch_ist_null():
    assert sprachmessung.anteil_englisch(ECHTE_ITALIENISCHE_POSTS) == 0.0


def test_ist_englisch_grenzfall_genau_mindesttreffer():
    """Genau ``_MINDESTTREFFER`` (3) englische Treffer, kein italienisches
    Gegengewicht -- der Grenzfall, den die Mutationsprobe (``>=`` zu ``>``)
    unbemerkt kippen konnte: eine kurze Systemzeile mit drei
    Stoppwoertern aus ``_ENGLISCHE_WOERTER`` und keinem italienischen Wort."""
    text = "Tap and send."
    woerter = [w.lower() for w in sprachmessung._WORT_MUSTER.findall(text)]
    assert sum(1 for w in woerter if w in sprachmessung._ENGLISCHE_WOERTER) == 3
    assert sum(1 for w in woerter if w in sprachmessung._ITALIENISCHE_WOERTER) == 0
    assert sprachmessung.ist_englisch(text)


# --- der aktuelle Stand: dieselben drei Systemzeilen heute -----------------


def test_die_gefixten_systemzeilen_sind_heute_italienisch_und_anteil_null():
    """a5ab681/b954c37 haben genau die Systemzeilen uebersetzt, die live
    englisch an die Gruppen gingen (``ablauf._TEXT_HINWEIS``,
    ``aufnahme._TEXT_ZWISCHENMELDUNG``,
    ``knoepfe.texte._TEXT_SZENE_ANDERS_FRAGE``) -- der Nachweis, dass der
    gemessene Anteil fuer diese drei heute 0 ist."""
    from interview_theater import ablauf, aufnahme, sprache
    from interview_theater.knoepfe import texte as knoepfe_texte

    heutige_fassungen = [
        sprache.text(ablauf.__name__, "_TEXT_HINWEIS", "it"),
        sprache.text(aufnahme.__name__, "_TEXT_ZWISCHENMELDUNG", "it"),
        sprache.text(knoepfe_texte.__name__, "_TEXT_SZENE_ANDERS_FRAGE", "it"),
    ]
    assert sprachmessung.anteil_englisch(heutige_fassungen) == 0.0
    for text in heutige_fassungen:
        assert not sprachmessung.ist_englisch(text)

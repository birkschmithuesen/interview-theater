"""Karte-Treue eines Buehnenscripts (Padua Phase 7, P7-Audit-Karte).

Material aus dem echten Fall (Live-Workshop 08.10.2026, siehe
docs/handoffs bzw. die Nachtlauf-Protokolle cc-p7audit):

* Klasse 8b (Gruppe 2): Karte 3 verneinte ausdruecklich, dass Arlecchino dem
  Fremden sagt, welchen Platz er im Reklutierungsplan einnimmt
  ("senza dire che posto occupa nell'ordine di reclutamento") -- das
  gespeicherte Script sollte diesen Wortlaut nie tragen.
* Klasse 9 (Gruppe 3): ein Kartenpunkt "OBBLIGATORIO (richiesta del
  gruppo): entrano anche le citazioni qui sotto su lockdown, Millennium Bug
  e fine del mondo 12-12-12." -- das gespeicherte Script liess "Millennium
  Bug" komplett aus.

Kein Modellaufruf, kein SQL."""

from interview_theater import kartentreue

# --- Klasse 8b: verneinte Hakenpunkte --------------------------------------

KARTE_SASRESTI = {
    "punkte": [
        "✔ No: Arlecchino gli dice solo di sedersi, senza dire che posto "
        "occupa nell'ordine di reclutamento.",
    ],
}


def test_widersprueche_findet_woertliche_verneinte_angabe():
    text = (
        "ARLECCHINO: Siediti con noi.\n"
        "Gli dico che posto occupa nell'ordine di reclutamento: e l'ultimo."
    )
    funde = kartentreue.widersprueche(KARTE_SASRESTI, text)
    assert funde
    assert "che posto occupa nell'ordine di reclutamento" in funde[0]


def test_widersprueche_leer_wenn_text_die_angabe_nicht_nennt():
    text = "ARLECCHINO: Ti va di sederti con noi? Sono circa quindici minuti."
    assert kartentreue.widersprueche(KARTE_SASRESTI, text) == []


def test_widersprueche_ignoriert_punkte_ohne_verneinungsmarker():
    karte = {"punkte": ["Anna recluta prima lo sconosciuto."]}
    text = "Anna recluta prima lo sconosciuto e poi Francesco."
    assert kartentreue.widersprueche(karte, text) == []


def test_widersprueche_englischer_marker_ohne_treffer():
    karte = {"punkte": ["No: the host answers the question without saying who called."]}
    text = "The host just says: sit down with us, dinner is ready."
    assert kartentreue.widersprueche(karte, text) == []


def test_widersprueche_englischer_marker_mit_treffer():
    karte = {"punkte": ["No: she replies without saying the neighbour called."]}
    text = "She says the neighbour called."
    assert kartentreue.widersprueche(karte, text) != []


# --- Klasse 9: OBBLIGATORIO-Stichworte -------------------------------------

KARTE_MILLENNIUM = {
    "punkte": [
        "Le domande della nostra guida d'intervista, dal tappeto sonoro "
        "registrato, montate senza logica e mai abbinate alla risposta "
        "delle voci.",
        "OBBLIGATORIO (richiesta del gruppo): entrano anche le citazioni "
        "qui sotto su lockdown, Millennium Bug e fine del mondo 12-12-12.",
    ],
}

KARTE_NOMI = {
    "punkte": [
        "OBBLIGATORIO (richiesta del gruppo): in questa scena entrano "
        "TUTTE le citazioni qui sotto -- Cecchettin, Pietro Maso (Verona), "
        "il quartiere queer di Milano, Caparezza, Maniero e la lingua del "
        "Santo, Mara Venier.",
    ],
}


def test_obbligatorio_stichworte_liest_liste_nach_su():
    assert kartentreue.obbligatorio_stichworte(KARTE_MILLENNIUM) == [
        "lockdown", "Millennium Bug", "fine del mondo 12-12-12",
    ]


def test_obbligatorio_stichworte_liest_liste_nach_strich():
    stichworte = kartentreue.obbligatorio_stichworte(KARTE_NOMI)
    assert "Cecchettin" in stichworte
    assert "Pietro Maso (Verona)" in stichworte
    assert "Mara Venier" in stichworte


def test_fehlende_stichworte_findet_den_live_befund():
    """Der reale Fall: Sz.2 hatte 'lockdown' und 'fine del mondo 12-12-12',
    aber nicht 'Millennium Bug' -- genau das muss fehlen."""
    text = (
        "VOCE 2: Ero disorientato in reparto durante il lockdown.\n"
        "VOCE 3: Si diceva che il mondo sarebbe finito, fine del mondo 12-12-12."
    )
    fehlend = kartentreue.fehlende_stichworte(KARTE_MILLENNIUM, text)
    assert fehlend == ["Millennium Bug"]


def test_fehlende_stichworte_leer_wenn_alles_drin():
    text = (
        "VOCE 2: durante il lockdown pensavo al Millennium Bug e alla fine "
        "del mondo 12-12-12."
    )
    assert kartentreue.fehlende_stichworte(KARTE_MILLENNIUM, text) == []


def test_fehlende_stichworte_ignoriert_klammerzusatz():
    """'Pietro Maso (Verona)' gilt als drin, wenn der Name ohne die
    Ortsangabe im Text steht -- die Karte haengt den Ort oft nur als
    Kontext an."""
    text = "Cecchettin, Pietro Maso, il quartiere queer di Milano, Caparezza, Mara Venier."
    fehlend = kartentreue.fehlende_stichworte(KARTE_NOMI, text)
    assert "Pietro Maso (Verona)" not in fehlend


def test_fehlende_stichworte_ohne_obbligatorio_punkt_ist_leer():
    karte = {"punkte": ["Un punto normale senza marcatore."]}
    assert kartentreue.fehlende_stichworte(karte, "qualsiasi testo") == []

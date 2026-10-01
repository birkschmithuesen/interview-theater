"""Der Beweis, dass die Ruecknahme wirklich ALLES erfasst (Karte U, Aufgabe 9).

Die Gefahr, gegen die dieser Test steht: der Diff vergisst eine Spalte, weil
sie in ``ruecknahme.AUSSEN`` gelandet ist oder weil ein Schreibpfad eine
Tabelle anfasst, die niemand verfolgt. Beides faellt im Betrieb erst auf, wenn
eine Gruppe ein Undo druckt und die Haelfte stehen bleibt.

Zwei Waechter:

1. **Rundreise je Art**: Dump aller verfolgten Tabellen -> Lauf anwenden ->
   Undo -> Dump ist wieder derselbe (bis auf Zeitstempel und die weich
   entfernten Neuanlagen).
2. **Vollstaendigkeit von VERFOLGT**: Dump ALLER Spalten ALLER Tabellen dieser
   ``chat_id`` vor und nach dem Anwenden -- jede geaenderte Spalte muss
   verfolgt sein oder in ``AUSSEN_VOR`` stehen, mit Grund. Damit faellt eine
   neue, ungeprueft beschriebene Spalte beim naechsten Umbau hier auf und
   nicht im Workshop.

Kein Netz, kein Modell: ``wende_an`` bekommt die Aenderungen als Liste, wie es
``erkenner.laufe`` nach dem Modellaufruf auch tut. Erfundenes Material.
"""

import json

import pytest

from interview_theater import db, erkenner, repo, ruecknahme
from tests.fixture_spaetstand import baue_spaetstand


#: Spalten, die ``wende_an`` aendert und die bewusst NICHT zurueckgenommen
#: werden -- je Eintrag ein Grund, wie ``BLEIBT_DEUTSCH`` in
#: tests/test_sprache_texte.py. Wer hier etwas eintraegt, trifft eine
#: Entscheidung und schreibt sie hin.
AUSSEN_VOR = {
    "arbeitsstand.phase": "Karte U: kein Undo fuer die Phase, sie setzt allein die Gruppe",
    "arbeitsstand.phase_angeboten": "Phasen-Buchhaltung (Merkposten des Angebots)",
    "arbeitsstand.phase_gesetzt_am": "Phasen-Buchhaltung",
    "arbeitsstand.geaendert_am": "Zeitstempel",
    "figur.geaendert_am": "Zeitstempel",
    "szene.geaendert_am": "Zeitstempel",
    "gruppe.letzte_extrahierte_message_id": "Wasserzeichen des Erkenners, kein Inhalt",
    "gruppe.interviewmodus_seit": "Interviewmodus: eigener Umschalter (Knopf/aufnahme)",
    "gruppe.wortlaut_modus": "wortlaut_an/aus bleiben still und haben ihren eigenen Weg",
    "gruppe.szene_usa_bestaetigt_am": "US-Einwilligung: eigene zwei Knoepfe (offener Punkt fuer Birk)",
    "gruppe.szene_usa_angeboten_am": "dito",
    "gruppe.szene_usa_offener_auftrag": "dito",
    "aufnahme.beendet_am": "Interviewmodus, eigener Umschalter",
    "aufnahme.status": "Interview-Buchhaltung, eigener Umschalter",
    "aufnahme.name": "interview_benennen bleibt still (baue_meldung)",
    "figur.quelle_aufnahme_id": (
        "figur_quelle_setzen bleibt still; die Zeile, die zaehlt, kommt aus "
        "sprachprofil.py -- verfolgt wird die Spalte trotzdem, siehe Test unten"
    ),
}

#: Ein Fall je undo-faehige Art: (Name, Vorbereitung, Aenderungen).
#: ``vorbereiten`` laeuft VOR dem Schnappschuss.
FAELLE = [
    (
        "kernthema_setzen",
        lambda conn: None,
        [{"art": "kernthema_setzen", "wert": "Was uns hier haelt"}],
    ),
    (
        "rahmen_setzen",
        lambda conn: None,
        [{"art": "rahmen_setzen", "wert": "Kiosk am Nordmarkt, Freitagabend"}],
    ),
    (
        "begriffe_setzen",
        lambda conn: None,
        [{"art": "begriffe_setzen", "wert": "Bleiben, Gehen, Geld"}],
    ),
    (
        "figur_setzen-neu",
        lambda conn: None,
        [{"art": "figur_setzen", "wert": "Nuran: zaehlt jeden Cent"}],
    ),
    (
        "figur_setzen-beschreibung",
        lambda conn: None,
        [{"art": "figur_setzen", "wert": "Leyla: will endlich gehoert werden"}],
    ),
    (
        # Der Fall, der den Nachbau je Art unmoeglich macht: ein
        # Platzhalter wird nachbenannt, und repo.fuehre_figur_zusammen
        # beruehrt figur, szene_figur und (weich) eine zweite figur-Zeile.
        "figur_setzen-platzhalter",
        lambda conn: _platzhalter(conn),
        [{"art": "figur_setzen", "wert": "Nesrin: laesst sich nichts gefallen"}],
    ),
    (
        "szene_planen-felder",
        lambda conn: None,
        [{"art": "szene_planen",
          "wert": "Szene 2 | ort: Kiosk | was_passiert: Cemre stellt Leyla"}],
    ),
    (
        "szene_planen-besetzung",
        lambda conn: None,
        [{"art": "szene_planen", "wert": "Szene 2 | figuren: Leyla, Cemre"}],
    ),
    (
        "festlegung_setzen",
        lambda conn: None,
        [{"art": "festlegung_setzen",
          "wert": "figur/Leyla: kommt aus der Nordstadt"}],
    ),
    (
        "entfernen-figur",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Figur Zeynep"}],
    ),
    (
        "entfernen-szene",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Szene 3"}],
    ),
    (
        "entfernen-arbeitsstandfeld",
        lambda conn: None,
        [{"art": "entfernen", "wert": "Kernthema"}],
    ),
    (
        "transkript_korrigieren",
        lambda conn: None,
        [{"art": "transkript_korrigieren", "wert": "TTT -> UUU"}],
    ),
    (
        "entschieden-mit-figurenzahl",
        lambda conn: None,
        [{"art": "entschieden", "wert": "Wir nehmen vier Figuren."}],
    ),
    (
        "zwei-auf-einmal",
        lambda conn: None,
        [{"art": "kernthema_setzen", "wert": "Bleiben oder gehen"},
         {"art": "figur_setzen", "wert": "Nuran: zaehlt jeden Cent"}],
    ),
]


def _platzhalter(conn):
    """Eine Platzhalterfigur mit einer Beschreibung, die der naechste
    ``figur_setzen``-Eintrag wortgleich mitbringt -- das Signal, an dem
    ``erkenner._schmelze_platzhalter_ein`` zusammenfuehrt."""
    repo.setze_figur(conn, 1, "Figur 5", "laesst sich nichts gefallen")
    figur_id = repo.hole_figur(conn, 1, "Figur 5")["id"]
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])


@pytest.fixture
def spaet(tmp_path):
    """Die Spaetstand-Gruppe: Phase 6, vier Figuren, vier Szenen, ein
    Interview mit Themen, ein langer Verlauf. Eine frische Datenbank zeigt
    keinen der interessanten Faelle."""
    conn = db.verbinde(str(tmp_path / "spaet.db"))
    db.initialisiere(conn)
    baue_spaetstand(conn)
    return conn


ZEITSTEMPEL = ("geaendert_am", "erstellt_am", "phase_gesetzt_am")


def _dump(conn, tabellen):
    """Alle Spalten aller Zeilen dieser Gruppe, Zeitstempel ausgenommen --
    ein Vergleichswert, der von der Uhr unabhaengig ist."""
    fertig = {}
    for tabelle in tabellen:
        spalten = [
            name for name, _ in db._tabellenspalten_aus_schema()[tabelle]
            if name not in ZEITSTEMPEL
        ]
        zeilen = conn.execute(
            f"SELECT {', '.join(spalten)} FROM {tabelle} WHERE chat_id = ? "
            f"ORDER BY {', '.join(spalten)}",
            (1,),
        ).fetchall()
        fertig[tabelle] = [
            json.dumps({k: z[k] for k in spalten}, sort_keys=True) for z in zeilen
        ]
    return fertig


#: Die Tabellen, die der Rundreise-Vergleich ansieht -- die verfolgten plus die
#: Materialtabellen, damit eine Transkriptkorrektur mitgemessen wird.
ALLE = tuple(ruecknahme.VERFOLGT) + tuple(ruecknahme.MATERIAL)


def _lauf(conn, aenderungen, einst=None):
    """``wende_an`` mit Schnappschuss davor und danach, Lauf gespeichert --
    derselbe Ablauf wie in ``erkenner.laufe``, ohne Chat und ohne Modell.

    Abweichung vom Brief: statt die Schnappschuesse hier nachzubauen, laeuft
    der Test ueber genau die zwei Funktionen, die ``erkenner.laufe`` seit dem
    Review-Fix Aufgabe 7 ruft (``_wende_an_mit_schnappschuss`` unter
    ``repo._LOCK``, dann ``_lege_ruecknahme_an``) -- ein Nachbau waere eine
    zweite Wahrheit neben dem Produktivpfad."""
    wirkliche, vorher, nachher = erkenner._wende_an_mit_schnappschuss(
        conn, einst, 1, aenderungen)
    assert vorher is not None and nachher is not None, "Schnappschuss ausgefallen"
    lauf_id = erkenner._lege_ruecknahme_an(
        conn, einst, 1, vorher, nachher, wirkliche)
    return lauf_id, wirkliche


def _nimm_zurueck(conn, lauf_id):
    return repo.nimm_erkenner_lauf_zurueck(
        conn, lauf_id, ruecknahme.verweise(),
        ruecknahme.WEICH, ruecknahme.HART, ruecknahme.GELEERT,
    )


@pytest.mark.parametrize("name, vorbereiten, aenderungen",
                         FAELLE, ids=[f[0] for f in FAELLE])
def test_rundreise_je_art_stellt_den_dump_wieder_her(
        spaet, einst, name, vorbereiten, aenderungen):
    """Anwenden, Undo, und der Dump ist wieder derselbe.

    Die eine erlaubte Abweichung: eine im Lauf ANGELEGTE Zeile bleibt als
    weich entfernte stehen (N3, "Weiches Loeschen statt Loeschen") -- sie
    wird deshalb aus dem Vergleich genommen und stattdessen einzeln geprueft.

    Mutation, die diesen Test rot macht: eine Spalte aus ``VERFOLGT``
    streichen (z. B. ``figur.beschreibung`` nach ``AUSSEN`` verschieben) --
    dann kommt der Dump nicht zurueck. Oder die Tabelle ``szene_figur``
    weglassen: dann schlaegt ``figur_setzen-platzhalter`` fehl."""
    vorbereiten(spaet)
    vorher = _dump(spaet, ALLE)

    lauf_id, wirkliche = _lauf(spaet, aenderungen, einst)
    assert wirkliche, f"{name}: der Lauf hat nichts geschrieben -- Fall pruefen"
    assert lauf_id is not None, f"{name}: kein Undo angelegt"
    assert _dump(spaet, ALLE) != vorher, f"{name}: der Lauf hat nichts veraendert"

    assert _nimm_zurueck(spaet, lauf_id) == repo.ZURUECK_OK

    nachher = _dump(spaet, ALLE)
    # Die weich entfernten Neuanlagen aus dem Vergleich nehmen und einzeln
    # pruefen: sie STEHEN noch, aber kein Leser sieht sie mehr.
    neu = [
        s for s in repo.erkenner_lauf_schritte(spaet, lauf_id)
        if s["art"] == "angelegt" and s["tabelle"] in ruecknahme.WEICH
    ]
    for schritt in neu:
        schluessel = json.loads(schritt["schluessel"])
        zeile = spaet.execute(
            f"SELECT entfernt_am FROM {schritt['tabelle']} WHERE id = ?",
            (schluessel["id"],),
        ).fetchone()
        assert zeile["entfernt_am"] is not None, (
            f"{name}: Neuanlage in {schritt['tabelle']} nicht weich entfernt"
        )
        nachher[schritt["tabelle"]] = [
            z for z in nachher[schritt["tabelle"]]
            if json.loads(z).get("id") != schluessel["id"]
        ]
        vorher[schritt["tabelle"]] = [
            z for z in vorher[schritt["tabelle"]]
            if json.loads(z).get("id") != schluessel["id"]
        ]

    assert nachher == vorher, f"{name}: der Stand kam nicht zurueck"


@pytest.mark.parametrize("name, vorbereiten, aenderungen",
                         FAELLE, ids=[f[0] for f in FAELLE])
def test_verfolgt_deckt_jede_geschriebene_spalte(
        spaet, einst, name, vorbereiten, aenderungen):
    """Jede Spalte, die ``wende_an`` tatsaechlich aendert, ist verfolgt -- oder
    steht in ``AUSSEN_VOR`` mit Grund.

    Verglichen wird ALLES: jede Spalte jeder Tabelle mit ``chat_id``, vorher
    und nachher. Damit faellt eine neue, ungeprueft beschriebene Spalte beim
    naechsten Umbau hier auf.

    Mutation, die diesen Test rot macht: eine von ``wende_an`` geschriebene
    Spalte nach ``ruecknahme.AUSSEN`` verschieben, ohne sie in ``AUSSEN_VOR``
    einzutragen.

    Verglichen wird **Zeile fuer Zeile** (ueber die ``rowid``), nicht Spalte
    fuer Spalte ueber alle Zeilen (Abweichung vom Brief, am Code gemessen):
    eine im Lauf ANGELEGTE Zeile bringt jede ihrer Spalten mit -- auch den
    Primaerschluessel und die NULLs in ``figur.sprachprofil``/``zitate``/
    ``geprueft_am``, die ``wende_an`` gar nicht schreibt. Spaltenweise
    gezaehlt, sah das wie ein Schreibzugriff auf diese Spalten aus; sie
    deshalb in ``AUSSEN_VOR`` zu stellen, haette aber einen ECHTEN
    Schreibzugriff auf eine bestehende Figur verdeckt. Eine neue Zeile ist
    gedeckt, wenn ihre Tabelle verfolgt wird und die Ruecknahme fuer sie
    einen Weg hat (``WEICH``/``HART``/``GELEERT``) -- die Rundreise oben
    beweist, dass dieser Weg greift."""
    vorbereiten(spaet)
    tabellen = [t for t in db.TABELLEN_MIT_CHAT_ID
                if t not in ("erkenner_lauf", "erkenner_lauf_schritt", "aufruf")]
    vorher = _alles(spaet, tabellen)

    erkenner.wende_an(spaet, einst, 1, aenderungen)

    verfolgt = ruecknahme.plan(a["art"] for a in aenderungen)
    ganze_zeile = set(ruecknahme.WEICH) | set(ruecknahme.HART) | set(ruecknahme.GELEERT)
    offen = []
    for tabelle, spalte in _unterschiede(vorher, _alles(spaet, tabellen)):
        if f"{tabelle}.{spalte}" in AUSSEN_VOR:
            continue
        if tabelle == "journal":
            continue  # nur-anhaengend, wird nie zurueckgenommen (AGENTS.md)
        if tabelle == "vorfall":
            continue  # Dashboard des Teams, kein Inhalt der Gruppe
        if tabelle in verfolgt and (
                spalte is None and tabelle in ganze_zeile
                or spalte in verfolgt[tabelle][1]):
            continue
        offen.append(f"{name}: {tabelle}.{spalte or '<ganze Zeile>'}")
    assert offen == [], (
        "geschrieben, aber nicht verfolgt und nicht begruendet -- entweder in "
        "ruecknahme.VERFOLGT/MATERIAL aufnehmen oder in AUSSEN_VOR eintragen: "
        f"{offen}"
    )


def _alles(conn, tabellen):
    """Tabelle -> {rowid: {Spalte: Wert}}, ueber alle Zeilen der Gruppe,
    Zeitstempel ausgenommen. Die ``rowid`` ist die Adresse der Zeile (kein
    Schema-Eintrag hier ist ``WITHOUT ROWID``)."""
    fertig = {}
    for tabelle in tabellen:
        spalten = [n for n, _ in db._tabellenspalten_aus_schema()[tabelle]
                   if n not in ZEITSTEMPEL]
        zeilen = conn.execute(
            f"SELECT rowid AS _zeile, {', '.join(spalten)} FROM {tabelle} "
            "WHERE chat_id = ?", (1,)
        ).fetchall()
        fertig[tabelle] = {
            z["_zeile"]: {k: json.dumps(z[k]) for k in spalten} for z in zeilen
        }
    return fertig


def _unterschiede(vorher, nachher):
    """(Tabelle, Spalte) je geaenderter Spalte einer bestehenden Zeile, und
    (Tabelle, None) je angelegter oder verschwundener Zeile."""
    fertig = set()
    for tabelle in set(vorher) | set(nachher):
        alt, neu = vorher.get(tabelle, {}), nachher.get(tabelle, {})
        for zeile in set(alt) | set(neu):
            if zeile not in alt or zeile not in neu:
                fertig.add((tabelle, None))
                continue
            fertig.update((tabelle, spalte) for spalte in neu[zeile]
                          if alt[zeile].get(spalte) != neu[zeile][spalte])
    return sorted(fertig, key=lambda t: (t[0], t[1] or ""))


def test_die_faelle_decken_jede_undo_faehige_art_ab():
    """Kein blinder Fleck: jede ``art``, die in der Notiert-Meldung landen kann
    und nicht ausgeschlossen ist, hat einen Fall."""
    gepruefte = {a["art"] for _, _, aenderungen in FAELLE for a in aenderungen}
    meldbar = {
        "kernthema_setzen", "format_setzen", "rahmen_setzen",
        "geschichte_setzen", "hauptkonflikt_setzen", "begriffe_setzen",
        "fragen_setzen", "figur_setzen", "szene_planen", "festlegung_setzen",
        "transkript_korrigieren", "entfernen", "entschieden",
    }
    fehlend = meldbar - gepruefte - ruecknahme.ZEILEN_OHNE_UNDO
    # format/geschichte/hauptkonflikt/fragen laufen durch denselben Pfad wie
    # kernthema (erkenner._wende_arbeitsstand_an, ein Feld) -- sie sind mit
    # kernthema_setzen und rahmen_setzen abgedeckt.
    assert fehlend <= {
        "format_setzen", "geschichte_setzen", "hauptkonflikt_setzen",
        "fragen_setzen",
    }, f"ohne Fall: {sorted(fehlend)}"

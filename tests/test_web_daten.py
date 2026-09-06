"""Die Lesezugriffe der Weboberflaeche, ohne HTTP.

Gegen eine echte, mit db.verbinde angelegte Datenbank -- die Fragen, die hier
schiefgehen koennen (leere Tabellen, fehlende Zeilen, NULL in fast jeder
Spalte), sind Datenbankfragen und keine Attrappenfragen.
"""

from datetime import datetime, timedelta, timezone

import pytest
from interview_theater import db, repo, web_daten

JETZT = datetime(2026, 9, 5, 14, 0, 0, tzinfo=timezone.utc)


def _iso(minuten_vorher: int) -> str:
    return (JETZT - timedelta(minutes=minuten_vorher)).isoformat(timespec="seconds")


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    repo.sichere_gruppe(c, 2, "gruppe2", "Zwei Staedte")
    return c


@pytest.fixture
def gefuellt(conn):
    """Eine Gruppe mit Material in jeder Schicht -- Arbeitsstand, Figuren,
    Aufnahmen, Verdichtung mit geprueftem und ungeprueftem Zitat, Journal,
    Szene, Vorfall, Aufruf."""
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "kernthema_begruendung", "Dreimal genannt")
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Koffer, Sprache, Warten")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Bleiben gegen Zurueckgehen")
    repo.setze_figur(conn, 1, "Maria", "kam 1998, arbeitet nachts")
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "hallo", _iso(30))
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 180)
    repo.setze_status(conn, aufnahme_id, "fertig")
    repo.setze_aufnahme_name(conn, aufnahme_id, "Maria")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Maria erzaehlt vom Ankommen",
        [
            {"thema": "Warten", "beleg_zitat": "wir haben lange gewartet",
             "zitat_geprueft": 1},
            {"thema": "Sprache", "beleg_zitat": "erfundenes Zitat", "zitat_geprueft": 0},
        ],
    )
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema ist Ankommen", "extraktor")
    conn.execute(
        "INSERT INTO szene (chat_id, nummer, titel, kurzbeschreibung, volltext, geaendert_am)"
        " VALUES (1, 1, 'Am Bahnhof', 'Zwei Frauen warten', 'MARIA: Wo bleibt er denn.', ?)",
        (_iso(5),),
    )
    conn.commit()
    return conn


def test_dashboard_zeigt_alle_gruppen_mit_arbeitsstand(gefuellt):
    daten = web_daten.dashboard(gefuellt, jetzt=JETZT)
    titel = [g["titel"] for g in daten["gruppen"]]
    assert titel == ["Die Ankommenden", "Zwei Staedte"]
    erste = daten["gruppen"][0]
    assert erste["arbeitsstand"]["kernthema"] == "Ankommen"
    assert erste["arbeitsstand"]["kernthema_begruendung"] == "Dreimal genannt"
    assert erste["arbeitsstand"]["format"] == "Musical: Dialog, Lied, Rap"
    assert erste["arbeitsstand"]["rahmen"] == "Eine Nacht im Treppenhaus"
    assert erste["arbeitsstand"]["hauptkonflikt"] == "Bleiben gegen Zurueckgehen"
    # ``id`` und ``quelle_aufnahme_id`` sind seit der Bearbeitung auf der
    # Gruppenseite dabei: das Formular adressiert eine Figur ueber ihre id.
    assert erste["figuren"] == [{
        "id": 1, "name": "Maria", "beschreibung": "kam 1998, arbeitet nachts",
        "sprachprofil": None, "zitate": [], "quelle": None,
        "quelle_aufnahme_id": None,
    }]
    assert erste["aufnahmen"] == {"fertig": 1}
    assert erste["verdichtungen"] == 1
    assert erste["szenen"] == 1
    assert erste["letzte_aktivitaet"] == _iso(30)


def test_dashboard_haelt_eine_leere_gruppe_aus(conn):
    """Am Workshopmorgen ist jede Gruppe leer -- ohne arbeitsstand-Zeile,
    ohne Nachricht. Das darf keine Ausnahme geben."""
    daten = web_daten.dashboard(conn, jetzt=JETZT)
    leer = daten["gruppen"][1]
    assert leer["arbeitsstand"]["kernthema"] is None
    assert leer["figuren"] == []
    assert leer["aufnahmen"] == {}
    assert leer["letzte_aktivitaet"] is None
    assert leer["vorfaelle"] == []
    assert leer["aufrufe"] == []


def test_dashboard_traegt_keinen_nachrichtentext(gefuellt):
    """Die Seite wird projiziert. Was gesprochen wurde, gehoert nicht auf den
    Beamer -- nur Arbeitsstand, Zahlen, Vorfaelle."""
    daten = web_daten.dashboard(gefuellt, jetzt=JETZT)
    text = repr(daten)
    assert "hallo" not in text
    assert "wir haben lange gewartet" not in text


def test_vorfaelle_nur_aus_den_letzten_zwei_stunden(conn):
    repo.merke_vorfall(conn, 1, "gruppe1", "kuerzung", "Stufe 1 gegriffen", stufe=1)
    conn.execute("UPDATE vorfall SET erstellt_am = ?", (_iso(10),))
    repo.merke_vorfall(conn, 1, "gruppe1", "http_5xx", "vorgestern")
    conn.execute("UPDATE vorfall SET erstellt_am = ? WHERE art = 'http_5xx'", (_iso(300),))
    conn.commit()

    vorfaelle = web_daten.dashboard(conn, jetzt=JETZT)["gruppen"][0]["vorfaelle"]
    assert [v["art"] for v in vorfaelle] == ["kuerzung"]
    assert vorfaelle[0]["stufe"] == 1
    assert vorfaelle[0]["bot_weit"] is False


def test_botweite_vorfaelle_landen_bei_der_gruppe_dieses_bots(conn):
    """chat_id IS NULL heisst 'betrifft den ganzen Bot' -- ein Prozess je
    Gruppe, also gehoert der Vorfall genau auf deren Karte und auf keine
    andere."""
    repo.merke_vorfall(conn, None, "gruppe1", "http_5xx", "Sprachmodell antwortet nicht")
    conn.execute("UPDATE vorfall SET erstellt_am = ?", (_iso(1),))
    conn.commit()

    gruppen = web_daten.dashboard(conn, jetzt=JETZT)["gruppen"]
    assert [v["art"] for v in gruppen[0]["vorfaelle"]] == ["http_5xx"]
    assert gruppen[0]["vorfaelle"][0]["bot_weit"] is True
    assert gruppen[1]["vorfaelle"] == [], "Gruppe 2 laeuft auf einem anderen Bot"


def test_aufrufkennzahlen_zaehlen_nur_heute_und_nehmen_den_median(conn):
    for dauer, erfolg, alter in [(100, 1, 5), (300, 1, 10), (500, 0, 15), (999, 1, 60 * 26)]:
        repo.merke_aufruf(conn, 1, "gespraech", dauer_ms=dauer, erfolg=erfolg)
        conn.execute(
            "UPDATE aufruf SET erstellt_am = ? WHERE id = (SELECT max(id) FROM aufruf)",
            (_iso(alter),),
        )
    repo.merke_aufruf(conn, 1, "verdichter", dauer_ms=8000, erfolg=1)
    conn.execute(
        "UPDATE aufruf SET erstellt_am = ? WHERE id = (SELECT max(id) FROM aufruf)",
        (_iso(20),),
    )
    conn.commit()

    aufrufe = web_daten.dashboard(conn, jetzt=JETZT)["gruppen"][0]["aufrufe"]
    nach_art = {a["art"]: a for a in aufrufe}
    assert nach_art["gespraech"]["anzahl"] == 3, "der Aufruf von gestern zaehlt nicht mit"
    assert nach_art["gespraech"]["fehlschlaege"] == 1
    assert nach_art["gespraech"]["median_ms"] == 300
    assert nach_art["verdichter"]["anzahl"] == 1


def test_bot_zuordnung_zeigt_gruppe_und_letzte_aktivitaet(conn):
    repo.setze_update_id(conn, "gruppe1", 4711)
    zuordnung = web_daten.bot_zuordnung(conn)
    nach_bot = {z["bot_name"]: z for z in zuordnung}
    assert nach_bot["gruppe1"]["titel"] == "Die Ankommenden"
    assert nach_bot["gruppe1"]["letzte_aktivitaet_am"] is not None
    assert nach_bot["gruppe2"]["letzte_aktivitaet_am"] is None, "Bot 2 lief noch nie"


def test_bot_zuordnung_zeigt_zwei_bots_in_derselben_gruppe(conn):
    """SPEC § 9.4: die Zuordnung soll den Betriebsfehler sichtbar machen.
    Ein zweiter Bot in derselben Gruppe ueberschreibt gruppe.bot_name -- auf
    dem Dashboard steht dann ein Bot ohne Gruppe."""
    repo.sichere_gruppe(conn, 1, "gruppe2", "Die Ankommenden")
    repo.setze_update_id(conn, "gruppe1", 1)
    zuordnung = web_daten.bot_zuordnung(conn)
    verwaist = [z for z in zuordnung if z["bot_name"] == "gruppe1"]
    assert verwaist and verwaist[0]["chat_id"] is None


def test_gruppenseite_ueber_token(gefuellt):
    token = repo.stelle_web_token_sicher(gefuellt, 1)
    daten = web_daten.gruppe_nach_token(gefuellt, token)
    assert daten["titel"] == "Die Ankommenden"
    assert daten["arbeitsstand"]["kernthema"] == "Ankommen"
    assert daten["arbeitsstand"]["fragen"] == "Was war in deinem Koffer?"
    assert daten["figuren"][0]["name"] == "Maria"
    assert daten["szenen"][0]["volltext"] == "MARIA: Wo bleibt er denn."
    assert daten["interviews"][0]["name"] == "Maria"
    assert daten["interviews"][0]["zusammenfassung"] == "Maria erzaehlt vom Ankommen"
    assert daten["journal"][0]["text"] == "Kernthema ist Ankommen"


def test_gruppenseite_zeigt_interviews_mit_teilen_und_dauer(gefuellt):
    """§ 10.6: die Gruppenseite zeigt je Interview eine Einheit -- Name,
    Teile-Zahl, Gesamtdauer, Verdichtung. Die einzelnen Sprachnachrichten
    tauchen nicht als eigene Eintraege auf."""
    kopf = repo.transkripte(gefuellt, 1)[0]["id"]
    repo.lege_aufnahme_an(gefuellt, 1, 20, "teil", "sprache", "/tmp/t1.ogg", 90, teil_von=kopf)
    repo.lege_aufnahme_an(gefuellt, 1, 21, "teil", "sprache", "/tmp/t2.ogg", 45, teil_von=kopf)

    interviews = web_daten.gruppe_nach_token(
        gefuellt, repo.stelle_web_token_sicher(gefuellt, 1)
    )["interviews"]

    assert len(interviews) == 1
    assert interviews[0]["teile"] == 2
    assert interviews[0]["dauer_sekunden"] == 135


def test_gruppenseite_zeigt_auch_ein_unverdichtetes_interview(gefuellt):
    """Ein Interview ohne Verdichtung faellt nicht unter den Tisch: die
    Gruppe soll sehen, dass die Aufnahme da ist."""
    repo.lege_aufnahme_an(gefuellt, 1, 30, "lang", "sprache", status="laeuft")

    interviews = web_daten.gruppe_nach_token(
        gefuellt, repo.stelle_web_token_sicher(gefuellt, 1)
    )["interviews"]

    assert [i["zusammenfassung"] for i in interviews] == ["Maria erzaehlt vom Ankommen", None]
    assert interviews[1]["status"] == "laeuft"


def test_gruppenseite_zeigt_nur_gepruefte_belegzitate(gefuellt):
    """zitat_geprueft = 0 heisst: das Modell hat den Satz vermutlich erfunden.
    Das Thema bleibt, das Zitat faellt weg."""
    token = repo.stelle_web_token_sicher(gefuellt, 1)
    themen = web_daten.gruppe_nach_token(gefuellt, token)["interviews"][0]["themen"]
    assert themen[0] == {
        "thema": "Warten", "kurz": "Warten", "zitat": "wir haben lange gewartet",
    }
    assert themen[1] == {"thema": "Sprache", "kurz": "Sprache", "zitat": None}


def test_figuren_tragen_sprachprofil_zitate_und_quelle(gefuellt):
    """05.09.2026: die Gruppenseite zeigt, wie eine Figur spricht und aus
    welchem Interview das kommt."""
    figur_id = repo.hole_figur(gefuellt, 1, "Maria")["id"]
    aufnahme_id = repo.transkripte(gefuellt, 1)[0]["id"]
    repo.setze_figur_quelle(gefuellt, figur_id, aufnahme_id)
    repo.setze_sprachprofil(
        gefuellt, figur_id, "Kurze Saetze.\nSagt 'halt'.",
        ["wir haben lange gewartet", "halt so, ne?"],
    )
    token = repo.stelle_web_token_sicher(gefuellt, 1)

    figur = web_daten.gruppe_nach_token(gefuellt, token)["figuren"][0]

    assert figur["quelle"] == "Interview 1"
    assert figur["sprachprofil"] == "Kurze Saetze.\nSagt 'halt'."
    assert figur["zitate"] == ["wir haben lange gewartet", "halt so, ne?"]


def test_szenen_tragen_ihre_planung(gefuellt):
    szene_id = repo.hole_szenen(gefuellt, 1)[0]["id"]
    repo.setze_szenenfeld(gefuellt, szene_id, "form", "Lied")
    repo.setze_szenenfeld(gefuellt, szene_id, "ort", "Treppenhaus")
    repo.setze_szene_figuren(
        gefuellt, 1, szene_id, [repo.hole_figur(gefuellt, 1, "Maria")["id"]]
    )
    token = repo.stelle_web_token_sicher(gefuellt, 1)

    szene = web_daten.gruppe_nach_token(gefuellt, token)["szenen"][0]

    assert szene["form"] == "Lied"
    assert szene["ort"] == "Treppenhaus"
    assert szene["figuren"] == ["Maria"]


def test_dashboard_zaehlt_szenen_nach_form(gefuellt):
    """"3 Szenen: 2 Dialog, 1 Lied" -- eine blosse Zahl sagt am Beamer wenig."""
    szene_id = repo.hole_szenen(gefuellt, 1)[0]["id"]
    repo.setze_szenenfeld(gefuellt, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(gefuellt, repo.stelle_szene_sicher(gefuellt, 1, 2), "form", "Dialog")
    repo.setze_szenenfeld(gefuellt, repo.stelle_szene_sicher(gefuellt, 1, 3), "form", "Lied")

    erste = web_daten.dashboard(gefuellt, jetzt=JETZT)["gruppen"][0]

    assert erste["szenen"] == 3
    assert erste["szenen_formen"] == [("Dialog", 2), ("Lied", 1)]


def test_dashboard_zeigt_je_interview_die_ergebnisse_als_kurzform(gefuellt):
    """N6: die eine Zeile je Interview -- Kurzformen, keine Zitate, keine
    Zusammenfassung."""
    erste = web_daten.dashboard(gefuellt, jetzt=JETZT)["gruppen"][0]

    assert erste["interview_kurzformen"] == [
        {"name": "Interview 1", "kurzformen": ["Warten", "Sprache"]}
    ]


def test_gruppenseite_traegt_kein_volltranskript(gefuellt):
    repo.setze_transkript(gefuellt, 1, "Das komplette Interview im Wortlaut")
    token = repo.stelle_web_token_sicher(gefuellt, 1)
    daten = web_daten.gruppe_nach_token(gefuellt, token)
    assert "komplette Interview" not in repr(daten)


def test_unbekanntes_token_gibt_none(gefuellt):
    assert web_daten.gruppe_nach_token(gefuellt, "gibtsnicht") is None


@pytest.mark.parametrize("token", ["", None])
def test_leeres_token_trifft_keine_gruppe(conn, token):
    """Sonst wuerde /g/ jede Gruppe treffen, deren web_token noch NULL ist."""
    conn.execute("UPDATE gruppe SET web_token = NULL")
    conn.commit()
    assert web_daten.gruppe_nach_token(conn, token) is None


def test_lesende_verbindung_darf_nicht_schreiben(tmp_path):
    pfad = str(tmp_path / "t.db")
    schreibend = db.verbinde(pfad)
    db.initialisiere(schreibend)
    repo.sichere_gruppe(schreibend, 1, "gruppe1", "Die Ankommenden")

    lesend = web_daten.oeffne_lesend(pfad)
    assert web_daten.dashboard(lesend, jetzt=JETZT)["gruppen"][0]["titel"] == "Die Ankommenden"
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        lesend.execute("UPDATE gruppe SET titel = 'geklaut' WHERE chat_id = 1")


def test_gruppe_ohne_web_token_spalte_liefert_none(tmp_path):
    """Live-Fall 04.09.2026: der Webserver lief gegen eine DB, deren Bot noch
    den alten Code ohne ``web_token`` hatte -- HTTP 500 statt 404. Die
    Spalte kommt per Migration im Bot; bis dahin ist jede Gruppenseite
    schlicht unbekannt."""
    import sqlite3

    from interview_theater import web_daten

    conn = sqlite3.connect(tmp_path / "alt.db")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE gruppe (chat_id INTEGER PRIMARY KEY, bot_name TEXT)")
    conn.execute("INSERT INTO gruppe VALUES (1, 'bot')")
    assert web_daten.gruppe_nach_token(conn, "irgendein-token") is None


# ---------------------------------------------------------------------------
# Phase und weiches Loeschen (Brief A5, NACHTRAG N3)
# ---------------------------------------------------------------------------


def test_phase_steht_im_arbeitsstand_beider_ansichten(gefuellt):
    repo.setze_phase(gefuellt, 1, 5)

    dashboard = web_daten.dashboard(gefuellt, JETZT)
    gruppe = web_daten.gruppe_nach_token(
        gefuellt, repo.hole_gruppe(gefuellt, 1)["web_token"]
    )

    erste = next(g for g in dashboard["gruppen"] if g["chat_id"] == 1)
    assert erste["arbeitsstand"]["phase"] == 5
    assert gruppe["arbeitsstand"]["phase"] == 5


def test_ohne_gesetzte_phase_steht_none_im_dict(gefuellt):
    """Roh wie in der Datenbank -- dass NULL wie 1 gilt, ist eine
    Anzeigeregel und steht in web.py."""
    dashboard = web_daten.dashboard(gefuellt, JETZT)

    erste = next(g for g in dashboard["gruppen"] if g["chat_id"] == 1)
    assert erste["arbeitsstand"]["phase"] is None


def test_entfernte_figuren_szenen_und_journalzeilen_fehlen_in_der_ansicht(gefuellt):
    repo.setze_figur(gefuellt, 1, "Peter", "Nachbar")
    repo.schreibe_journal(gefuellt, 1, "verworfen", "Kindheitsfragen", "erkenner")
    token = repo.hole_gruppe(gefuellt, 1)["web_token"]

    repo.entferne_figur(gefuellt, 1, "Peter")
    repo.entferne_szene(gefuellt, 1, 1)
    repo.entferne_journal(gefuellt, 1, "Kindheitsfragen")

    gruppe = web_daten.gruppe_nach_token(gefuellt, token)

    assert [f["name"] for f in gruppe["figuren"]] == ["Maria"]
    assert gruppe["szenen"] == []
    assert [e["text"] for e in gruppe["journal"]] == ["Kernthema ist Ankommen"]


def test_dashboard_zaehlt_entfernte_szenen_nicht_mit(gefuellt):
    repo.entferne_szene(gefuellt, 1, 1)

    dashboard = web_daten.dashboard(gefuellt, JETZT)

    erste = next(g for g in dashboard["gruppen"] if g["chat_id"] == 1)
    assert erste["szenen"] == 0


def test_interviews_chronologisch_nach_beginn_mit_zeitpunkt(conn):
    """06.09.2026 14:00 (Gruppe 1): ein nachtraeglich getrenntes Interview
    bekam eine hoehere id als das spaeter gestartete und stand als 'Interview 3'
    hinter dem laufenden. Sortiert wird nach dem Beginn (fruehester Teil),
    und jede Zeile traegt ihren Beginn."""
    from interview_theater import repo, web_daten

    a = repo.lege_aufnahme_an(conn, 1, 0, "lang", "sprache", status="laeuft")   # 11:44 gestartet
    b = repo.lege_aufnahme_an(conn, 1, 0, "lang", "sprache", status="fertig")   # spaeter angelegt ...
    conn.execute("UPDATE aufnahme SET empfangen_am = '2026-09-06T11:44:48+00:00' WHERE id = ?", (a,))
    conn.execute("UPDATE aufnahme SET empfangen_am = '2026-09-06T11:46:03+00:00' WHERE id = ?", (b,))
    # ... traegt aber einen Teil von 11:41 -> beginnt frueher
    t = repo.lege_aufnahme_an(conn, 1, 5, "teil", "sprache", status="fertig")
    conn.execute("UPDATE aufnahme SET teil_von = ?, empfangen_am = '2026-09-06T11:41:53+00:00', dauer_sekunden = 218 WHERE id = ?", (b, t))
    conn.commit()

    liste = web_daten._interviews(conn, 1)
    assert [i["bezeichnung"] for i in liste] == ["Interview 1", "Interview 2"]
    assert liste[0]["beginn"].startswith("2026-09-06T11:41:53")
    assert liste[1]["beginn"].startswith("2026-09-06T11:44:48")
    assert [i["id"] for i in web_daten.interview_liste(conn, 1)] == [b, a] if hasattr(web_daten, "interview_liste") else True

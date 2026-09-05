"""Bearbeiten auf der Gruppenseite, ueber echtes HTTP.

Wie ``tests/test_web.py``: der Server laeuft auf 127.0.0.1:0 in einem Thread,
angesprochen wird er mit urllib -- kein Netzzugriff nach draussen. Ueber HTTP
statt ueber ``web_schreiben`` allein, weil hier die ganze Kette geprueft wird:
Nonce, Token, JSON rein, Datenbankzeile und Journaleintrag raus, Antwort-JSON
zurueck.

Die Wegwerf-Datenbank traegt mit Absicht ein **Transkript mit einem
Markerwort** und eine Nachricht mit einem zweiten. Beide duerfen auf keiner
gerenderten Seite auftauchen -- das ist die eine Zusage, die durch das
Bearbeiten nicht weicher werden darf.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest
from interview_theater import db, repo, web, web_daten, web_schreiben

#: Kommt im Transkript des ersten Interviews vor und darf in keiner Seite
#: stehen. Ein Fantasiewort, damit ein Treffer nur ein echter Treffer sein
#: kann.
MARKER_TRANSKRIPT = "Zwirbelkiste"

#: Dasselbe fuer einen Nachrichtentext im Chat.
MARKER_NACHRICHT = "Quastenflosser"

#: Und fuer ein ungeprueftes Belegzitat.
MARKER_ZITAT = "Schnarrhupfer"


@pytest.fixture
def db_pfad(tmp_path):
    """Eine Gruppe in Phase 4, mit angebotenen Kernthemen und Richtungen,
    zwei Figuren, zwei Interviews und einer Szene -- der Zustand, in dem eine
    Gruppe am Nachmittag wirklich steht."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")

    repo.setze_phase(conn, 1, 4)
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Ankommen, Arbeit, Nacht")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen und Bleiben")
    repo.setze_arbeitsstand(conn, 1, "kernthema_richtung", "Heimat")

    # Was der Bot im Chat schon einmal zur Auswahl gestellt hat -- die Quelle
    # der Dropdowns (web_daten.KNOPFARTEN).
    for wert in ("Heimat", "Arbeit", "Nachtschicht"):
        repo.lege_knopf_an(conn, 1, "richtung", wert)
    for wert in ("Ankommen und Bleiben", "Zwei Staedte, ein Koffer"):
        repo.lege_knopf_an(conn, 1, "kernthema", wert)
    repo.lege_knopf_an(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")

    repo.setze_figur(conn, 1, "Mira", "24, arbeitet nachts")
    repo.setze_figur(conn, 1, "Pola", "58, will zurueck")

    # Zwei Interviews. Das erste hat ein Transkript mit dem Markerwort --
    # es steht in der Datenbank und darf trotzdem auf keiner Seite stehen.
    for nummer in (1, 2):
        repo.merke_nachricht(
            conn, 1, 100 + nummer, "Ada", 0, "sprache", "",
            f"2026-09-05T09:0{nummer}:00+00:00",
        )
        aufnahme_id = repo.lege_aufnahme_an(
            conn, 1, 100 + nummer, "lang", "sprache", f"/tmp/a{nummer}.ogg", 200
        )
        if nummer == 1:
            repo.setze_transkript(
                conn, aufnahme_id,
                f"Ich hatte nur einen Koffer und eine {MARKER_TRANSKRIPT} dabei.",
            )
            repo.speichere_verdichtung(
                conn, 1, aufnahme_id, "Mira erzaehlt vom ersten Winter",
                [
                    {"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
                     "zitat_geprueft": 1},
                    {"thema": "Arbeit", "beleg_zitat": MARKER_ZITAT,
                     "zitat_geprueft": 0},
                ],
            )

    # Ein Nachrichtentext, wie ihn die Gruppe schreibt.
    repo.merke_nachricht(
        conn, 1, 200, "Ada", 0, "text",
        f"Also ich finde ja {MARKER_NACHRICHT} passt gar nicht.",
        "2026-09-05T09:30:00+00:00",
    )

    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Im Treppenhaus")
    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")
    repo.setze_szenenfeld(conn, szene_id, "ort", "Treppenhaus")

    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema steht", "extraktor")
    conn.commit()
    # Die Verbindung bleibt offen: sie haelt die WAL-Dateien am Leben, so wie
    # im Betrieb der Bot-Prozess.
    return pfad


@pytest.fixture
def conn(db_pfad):
    """Eine zweite, schreibende Verbindung -- der Test schaut damit in die
    Datenbank, waehrend der Server auf derselben Datei arbeitet. Genau die
    Konstellation, die WAL und busy_timeout tragen muessen."""
    return db.verbinde(db_pfad)


@pytest.fixture
def token(conn):
    return repo.stelle_web_token_sicher(conn, 1)


#: Ein fester Schluessel statt eines gewuerfelten: so kann der Test den Nonce
#: selbst ausrechnen, ohne die Seite zu parsen.
SCHLUESSEL = b"testschluessel"


@pytest.fixture
def basis(db_pfad):
    server = web.baue_server(db_pfad, bind="127.0.0.1:0", schluessel=SCHLUESSEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def hole(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def sende(basis: str, token: str, feld: str, wert, ziel=None,
          nonce=None) -> tuple[int, str]:
    """Ein POST wie ihn die Seite schickt. ``nonce=None`` heisst: den
    gueltigen nehmen; ``nonce=""`` heisst: gar keinen."""
    rumpf = {
        "nonce": web.nonce(SCHLUESSEL, token) if nonce is None else nonce,
        "feld": feld,
        "wert": wert,
        "ziel": ziel,
    }
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}",
        data=json.dumps(rumpf).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=5) as antwort:
            return antwort.status, antwort.read().decode("utf-8")
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read().decode("utf-8")


def stand(conn, feld: str):
    return repo.hole_arbeitsstand(conn, 1)[feld]


def journalzeilen(conn) -> list[tuple[str, str, str]]:
    return [(e["art"], e["quelle"], e["text"]) for e in repo.journal(conn, 1)]


def letzte_webzeile(conn) -> str:
    zeilen = [t for _, quelle, t in journalzeilen(conn) if quelle == "web"]
    assert zeilen, "kein Journaleintrag mit quelle='web'"
    return zeilen[-1]


# --- Die Seite selbst ------------------------------------------------------


def test_gruppenseite_traegt_die_formulare(basis, token):
    """Was die Gruppenseite an Bedienelementen haben muss: ein Dropdown fuer
    das Kernthema, eines fuer die Phase, Textfelder und den Nonce."""
    status, koerper = hole(f"{basis}/g/{token}")

    assert status == 200
    assert "<select" in koerper
    for feld in ("kernthema", "kernthema_richtung", "phase", "kernfrage",
                 "rahmen", "figur_name", "figur_quelle", "figur_entfernen",
                 "figur_neu", "szene_form", "szene_figuren"):
        assert f'data-feld="{feld}"' in koerper, feld
    assert 'id="nonce"' in koerper


def test_kernthema_dropdown_hat_die_vorschlaege_und_den_gesetzten(basis, token):
    """Birks Beispiel: es gab mehrere Vorschlaege, einer wurde gewaehlt --
    im Dropdown stehen alle, der gewaehlte ist vorausgewaehlt."""
    koerper = hole(f"{basis}/g/{token}")[1]

    assert "Zwei Staedte, ein Koffer" in koerper
    assert '<option value="Ankommen und Bleiben" selected>' in koerper
    # Und die drei Richtungen, die je angeboten wurden.
    for richtung in ("Heimat", "Arbeit", "Nachtschicht"):
        assert richtung in koerper


def test_dashboard_bleibt_ohne_formulare(basis):
    """Das Dashboard haengt am Beamer und bleibt read-only -- dort soll
    niemand im Vorbeigehen etwas umstellen."""
    koerper = hole(f"{basis}/")[1]

    assert "data-feld=" not in koerper
    assert 'id="nonce"' not in koerper


def test_dashboard_nimmt_kein_post(basis, token):
    anfrage = urllib.request.Request(
        f"{basis}/", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


# --- Die drei Grenzen ------------------------------------------------------


def test_kein_transkript_und_kein_nachrichtentext_auf_der_seite(basis, token):
    """Die Zusage, die durch das Bearbeiten nicht weicher werden darf: kein
    Transkript, kein Nachrichtentext, kein ungepruefter Satz -- auch nicht in
    einem Dropdown."""
    gruppenseite = hole(f"{basis}/g/{token}")[1]
    dashboard = hole(f"{basis}/")[1]

    for seite in (gruppenseite, dashboard):
        assert MARKER_TRANSKRIPT not in seite
        assert MARKER_NACHRICHT not in seite
        assert MARKER_ZITAT not in seite
    # Das geprüfte Zitat steht weiter da -- die Grenze ist die Pruefung, nicht
    # das Zitat.
    assert "Ich hatte nur einen Koffer" in gruppenseite


def test_interview_dropdown_nennt_nur_nummern(basis, token):
    """Die Interview-Zuordnung bietet 'Interview 1' und 'Interview 2' an --
    nie den Aufnahmenamen und nie ein Stueck Transkript."""
    koerper = hole(f"{basis}/g/{token}")[1]

    assert ">Interview 1</option>" in koerper
    assert ">Interview 2</option>" in koerper


# --- Zugang: Token und Nonce ----------------------------------------------


def test_unbekanntes_token_bekommt_404(basis, token):
    status, _ = sende(basis, "gibtesnicht", "kernthema", "Egal")
    assert status == 404


def test_fehlender_nonce_bekommt_403(basis, token, conn):
    status, text = sende(basis, token, "kernthema", "Heimlich", nonce="")

    assert status == 403
    assert "neu laden" in text
    assert stand(conn, "kernthema") == "Ankommen und Bleiben"


def test_falscher_nonce_bekommt_403(basis, token, conn):
    status, _ = sende(basis, token, "kernthema", "Heimlich", nonce="0.abc")
    assert status == 403
    assert stand(conn, "kernthema") == "Ankommen und Bleiben"


def test_nonce_einer_fremden_gruppe_gilt_nicht(basis, token):
    """Der Nonce haengt am Token: einer fuer eine andere Adresse oeffnet
    diese hier nicht."""
    fremd = web.nonce(SCHLUESSEL, "ein-anderes-token")
    status, _ = sende(basis, token, "kernthema", "Heimlich", nonce=fremd)
    assert status == 403


def test_nonce_gilt_noch_im_naechsten_fenster():
    """Eine Seite, die kurz vor dem Stundenwechsel geoeffnet wurde, soll eine
    Minute spaeter noch schreiben duerfen."""
    alt = web.nonce(SCHLUESSEL, "t", jetzt=0)

    assert web.nonce_gueltig(SCHLUESSEL, "t", alt, jetzt=web.NONCE_FENSTER + 5)
    assert not web.nonce_gueltig(
        SCHLUESSEL, "t", alt, jetzt=2 * web.NONCE_FENSTER + 5
    )


def test_kaputter_rumpf_bekommt_400(basis, token):
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}", data=b"kein json", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 400


def test_unbekanntes_feld_bekommt_400(basis, token):
    status, text = sende(basis, token, "volltext", "Ich schreibe die Szene um")
    assert status == 400
    assert "volltext" in text


# --- Je Parameter einmal setzen -------------------------------------------


def test_phase_setzen(basis, token, conn):
    status, antwort = sende(basis, token, "phase", "6")

    assert status == 200
    assert json.loads(antwort) == {"ok": True, "feld": "phase", "wert": "6", "id": None}
    assert repo.hole_phase(conn, 1) == 6
    assert ("entschieden", "web", "Phase 6 · Szenen (über die Gruppenseite)") \
        in journalzeilen(conn)


@pytest.mark.parametrize("wert", ["0", "8", "vier", ""])
def test_phase_ausserhalb_1_bis_7_bekommt_400(basis, token, conn, wert):
    status, text = sende(basis, token, "phase", wert)

    assert status == 400
    assert "1 bis 7" in text
    assert repo.hole_phase(conn, 1) == 4


@pytest.mark.parametrize(
    "feld,wert,label",
    [
        ("begriffe", "Ankommen, Nacht, Koffer", "Begriffe"),
        ("fragen", "Was war im Koffer?\nWer hat gewartet?", "Fragen"),
        ("kernthema", "Zwei Staedte, ein Koffer", "Kernthema"),
        ("kernthema_richtung", "Nachtschicht", "Kernthema-Richtung"),
        ("kernfrage", "Frage: Was passiert, wenn man bleibt?", "Kernfrage"),
        ("rahmen", "Eine Nacht im Treppenhaus", "Rahmen"),
    ],
)
def test_arbeitsstandfeld_setzen(basis, token, conn, feld, wert, label):
    alt = stand(conn, feld)
    status, antwort = sende(basis, token, feld, wert)

    assert status == 200
    assert json.loads(antwort) == {"ok": True, "feld": feld, "wert": wert, "id": None}
    assert stand(conn, feld) == wert
    zeile = letzte_webzeile(conn)
    assert zeile.startswith(f"{label} geändert über die Gruppenseite: ")
    assert (alt or web_schreiben.LEER).split("\n")[0][:20] in zeile
    assert wert.split("\n")[0][:20] in zeile


def test_leeres_feld_wird_null_und_nicht_leerstring(basis, token, conn):
    """Ein geleertes Formularfeld leert das Datenbankfeld -- nur so gilt es
    anschliessend wieder als ungesetzt (phasen.voraussetzungen)."""
    sende(basis, token, "kernfrage", "Frage: bleiben?")
    sende(basis, token, "kernfrage", "   ")

    assert stand(conn, "kernfrage") is None
    assert web_schreiben.LEER in letzte_webzeile(conn)


def test_langer_wert_wird_im_journal_gekuerzt(basis, token, conn):
    lang = "Ankommen " * 60
    sende(basis, token, "kernthema", lang)

    zeile = letzte_webzeile(conn)
    assert "…" in zeile
    # Zwei Seiten a 120 Zeichen plus die feste Formulierung -- nie die vollen
    # 540 Zeichen des Werts.
    assert len(zeile) < 300
    assert stand(conn, "kernthema") == lang.strip()


# --- Figuren ---------------------------------------------------------------


def figur(conn, name: str):
    return repo.hole_figur(conn, 1, name)


def test_figur_umbenennen(basis, token, conn):
    mira = figur(conn, "Mira")
    status, antwort = sende(basis, token, "figur_name", "Meryem", ziel=mira["id"])

    assert status == 200
    assert json.loads(antwort)["wert"] == "Meryem"
    assert repo.hole_figur_nach_id(conn, mira["id"])["name"] == "Meryem"
    # Kein zweiter Eintrag in der Tabelle: umbenennen ist umbenennen.
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Meryem", "Pola"]
    assert "Figur Mira · Name geändert über die Gruppenseite: Mira → Meryem" \
        == letzte_webzeile(conn)


def test_figur_ohne_namen_bekommt_400(basis, token, conn):
    mira = figur(conn, "Mira")
    status, text = sende(basis, token, "figur_name", "  ", ziel=mira["id"])

    assert status == 400
    assert "Namen" in text
    assert figur(conn, "Mira") is not None


def test_figur_beschreibung_aendern(basis, token, conn):
    pola = figur(conn, "Pola")
    status, _ = sende(
        basis, token, "figur_beschreibung", "58, bleibt doch", ziel=pola["id"]
    )

    assert status == 200
    assert figur(conn, "Pola")["beschreibung"] == "58, bleibt doch"
    assert "Figur Pola · Beschreibung" in letzte_webzeile(conn)


def test_figur_wechselt_das_interview(basis, token, conn):
    """Der Wechsel setzt die Quelle, leert das Sprachprofil und nimmt die
    Abnahme zurueck -- damit knoepfe.stelle_figur_vor beim naechsten Zug ein
    neues Profil erzeugt. Hier laeuft kein Modell."""
    mira = figur(conn, "Mira")
    interviews = repo.transkripte(conn, 1)
    repo.setze_figur_quelle(conn, mira["id"], interviews[0]["id"])
    repo.setze_sprachprofil(conn, mira["id"], "Kurze Saetze.", ["Ich hatte nur einen Koffer"])
    repo.setze_figur_geprueft(conn, mira["id"], repo._jetzt())

    status, _ = sende(
        basis, token, "figur_quelle", str(interviews[1]["id"]), ziel=mira["id"]
    )

    assert status == 200
    frisch = repo.hole_figur_nach_id(conn, mira["id"])
    assert frisch["quelle_aufnahme_id"] == interviews[1]["id"]
    assert not (frisch["sprachprofil"] or "").strip()
    assert frisch["geprueft_am"] is None
    texte = [t for _, quelle, t in journalzeilen(conn) if quelle == "web"]
    assert any("Interview 1 → Interview 2" in t for t in texte)
    assert any(t.startswith("Sprachprofil neu nötig") for t in texte)


def test_figur_ohne_interview(basis, token, conn):
    mira = figur(conn, "Mira")
    repo.setze_figur_quelle(conn, mira["id"], repo.transkripte(conn, 1)[0]["id"])

    status, _ = sende(basis, token, "figur_quelle", "", ziel=mira["id"])

    assert status == 200
    assert repo.hole_figur_nach_id(conn, mira["id"])["quelle_aufnahme_id"] is None


def test_fremdes_interview_bekommt_400(basis, token, conn):
    mira = figur(conn, "Mira")
    status, text = sende(basis, token, "figur_quelle", "9999", ziel=mira["id"])

    assert status == 400
    assert "Interview" in text


def test_figur_entfernen_ist_weich(basis, token, conn):
    pola = figur(conn, "Pola")
    status, _ = sende(basis, token, "figur_entfernen", "", ziel=pola["id"])

    assert status == 200
    assert figur(conn, "Pola") is None
    # Weich: die Zeile steht noch da, mit entfernt_am.
    assert repo.hole_figur_nach_id(conn, pola["id"])["entfernt_am"]
    assert letzte_webzeile(conn) == "Figur Pola entfernt über die Gruppenseite"


def test_figur_hinzufuegen(basis, token, conn):
    status, antwort = sende(basis, token, "figur_neu", "Pal")

    assert status == 200
    assert json.loads(antwort)["wert"] == "Pal"
    assert figur(conn, "Pal") is not None
    assert letzte_webzeile(conn) == "Figur Pal angelegt über die Gruppenseite"


def test_figur_doppelt_anlegen_bekommt_400(basis, token, conn):
    status, text = sende(basis, token, "figur_neu", "mira")

    assert status == 400
    assert "schon" in text
    assert len(repo.figuren(conn, 1)) == 2


def test_figur_einer_fremden_gruppe_bleibt_unberuehrt(basis, token, conn):
    """Das Token adressiert EINE Gruppe -- eine id im Formular darf daran
    nicht vorbeigreifen. Alle Gruppen teilen sich eine Datenbank."""
    repo.sichere_gruppe(conn, 2, "gruppe2", "Zwei Staedte")
    repo.setze_figur(conn, 2, "Fremde", "gehoert nicht hierher")
    fremd = repo.hole_figur(conn, 2, "Fremde")

    status, text = sende(basis, token, "figur_name", "Gekapert", ziel=fremd["id"])

    assert status == 400
    assert "nicht gefunden" in text
    assert repo.hole_figur(conn, 2, "Fremde") is not None


# --- Szenen ----------------------------------------------------------------


def szene(conn):
    return repo.hole_szenen(conn, 1)[0]


@pytest.mark.parametrize(
    "feld,wert",
    [
        ("titel", "Auf der Treppe"),
        ("form", "Lied"),
        ("ort", "Hinterhof"),
        ("zeit", "kurz vor Mitternacht"),
        ("anlass", "der Aufzug steht"),
        ("was_passiert", "Mira und Pola treffen sich."),
        ("was_anders", "Pola bleibt."),
        ("ton", "leise"),
    ],
)
def test_szenenfeld_setzen(basis, token, conn, feld, wert):
    szene_id = szene(conn)["id"]
    status, antwort = sende(basis, token, f"szene_{feld}", wert, ziel=szene_id)

    assert status == 200
    assert json.loads(antwort)["wert"] == wert
    assert repo.hole_szene(conn, szene_id)[feld] == wert
    assert "Szene 1 · " in letzte_webzeile(conn)


def test_szenenfeld_ruehrt_kein_anderes_an(basis, token, conn):
    """Die Regel, an der die additive Szenenplanung haengt."""
    szene_id = szene(conn)["id"]
    sende(basis, token, "szene_ort", "Hinterhof", ziel=szene_id)

    frisch = repo.hole_szene(conn, szene_id)
    assert frisch["titel"] == "Im Treppenhaus"
    assert frisch["form"] == "Dialog"


def test_szenen_volltext_ist_nicht_aenderbar(basis, token, conn):
    """Der Szenentext entsteht im Chat und wird dort abgenommen."""
    szene_id = szene(conn)["id"]
    status, _ = sende(basis, token, "szene_volltext", "Mira: Hallo.", ziel=szene_id)

    assert status == 400
    assert "szene_volltext" not in web_schreiben.FELDER


def test_besetzung_setzen(basis, token, conn):
    szene_id = szene(conn)["id"]
    ids = [f["id"] for f in repo.figuren(conn, 1)]

    status, antwort = sende(basis, token, "szene_figuren", ids, ziel=szene_id)

    assert status == 200
    assert json.loads(antwort)["wert"] == "Mira, Pola"
    assert [f["name"] for f in repo.szene_figuren(conn, szene_id)] == ["Mira", "Pola"]
    assert "Szene 1 · Besetzung" in letzte_webzeile(conn)


def test_besetzung_leeren(basis, token, conn):
    szene_id = szene(conn)["id"]
    ids = [f["id"] for f in repo.figuren(conn, 1)]
    repo.setze_szene_figuren(conn, 1, szene_id, ids)

    status, _ = sende(basis, token, "szene_figuren", [], ziel=szene_id)

    assert status == 200
    assert repo.szene_figuren(conn, szene_id) == []


def test_szene_einer_fremden_gruppe_bleibt_unberuehrt(basis, token, conn):
    repo.sichere_gruppe(conn, 2, "gruppe2", "Zwei Staedte")
    fremd = repo.stelle_szene_sicher(conn, 2, 1)
    repo.setze_szenenfeld(conn, fremd, "ort", "Woanders")

    status, _ = sende(basis, token, "szene_ort", "Gekapert", ziel=fremd)

    assert status == 400
    assert repo.hole_szene(conn, fremd)["ort"] == "Woanders"


# --- Kein Material, kein zweiter Schreibweg -------------------------------


def test_material_steht_in_keinem_feld():
    """Was die Gruppenseite NICHT schreiben darf. Als Test, nicht nur als
    Kommentar: die Liste soll nicht beim naechsten Umbau aus Versehen
    wachsen."""
    verboten = (
        "volltext", "transkript", "verdichtung", "zusammenfassung",
        "beleg_zitat", "zitat", "journal", "usa", "sprachprofil", "format",
    )
    for feld in web_schreiben.FELDER:
        assert not any(wort in feld for wort in verboten), feld


def test_alle_felder_schreiben_ins_journal(basis, token, conn):
    """Jeder Parameter hinterlaesst genau eine Spur mit quelle='web' -- die
    einzige Art, wie der Gespraechs-Bot von einer Web-Aenderung erfaehrt
    (kontext._baue_journal)."""
    vorher = len([1 for _, quelle, _ in journalzeilen(conn) if quelle == "web"])
    sende(basis, token, "begriffe", "Koffer")
    sende(basis, token, "phase", "5")

    nachher = [t for _, quelle, t in journalzeilen(conn) if quelle == "web"]
    assert len(nachher) == vorher + 2


def test_web_schreiben_hat_kein_sql():
    """Die Zusage: der Webserver schreibt ausschliesslich ueber repo. Kein
    SELECT, kein UPDATE, kein INSERT in web_schreiben.py."""
    from pathlib import Path

    quelltext = Path(web_schreiben.__file__).read_text(encoding="utf-8")
    for wort in ("SELECT ", "INSERT ", "UPDATE ", "DELETE "):
        assert wort not in quelltext, wort


def test_web_daten_bleibt_ohne_schreibpfad():
    """web_daten.py oeffnet read-only und bekommt keinen Schreibpfad dazu."""
    from pathlib import Path

    quelltext = Path(web_daten.__file__).read_text(encoding="utf-8")
    for wort in ("INSERT ", "UPDATE ", "DELETE ", "conn.commit"):
        assert wort not in quelltext, wort


def test_bot_sieht_die_aenderung_im_journalblock(basis, token, conn):
    """Der Webserver spricht nicht mit Telegram. Der Bot erfaehrt von einer
    Aenderung, weil er das Journal bei jedem Zug frisch liest."""
    from interview_theater import kontext

    sende(basis, token, "kernthema", "Zwei Staedte, ein Koffer")

    block = kontext._baue_journal(conn, 1)
    assert "Kernthema geändert über die Gruppenseite" in block

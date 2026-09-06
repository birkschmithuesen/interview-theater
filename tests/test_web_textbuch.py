"""Die Probenansicht: `/g/<token>/textbuch` und die beiden Dateiwege.

Ueber echtes HTTP wie ``tests/test_web.py`` -- geprueft wird die Verdrahtung
(Routing, Statuscodes, Praefix, Content-Type) und daneben die beiden reinen
Funktionen, die den Rollenfilter tragen (``sprecher_der_zeile``,
``szenentext_html``).

Die harte Grenze steht in ``test_kein_material_in_der_probenansicht``: auf
dieser Seite darf **nichts** stehen, was nicht Szenentext oder Szenenplanung
ist -- kein Transkript, kein Nachrichtentext, kein Journal, kein Belegzitat.
Der Link geht in der Probe von Hand zu Hand.
"""

import threading
import urllib.error
import urllib.request

import pytest
from interview_theater import db, repo, szenenfolge, web

#: Kommt in Transkript, Nachricht, Verdichtung, Journal und Zitat vor -- und
#: darf in der Probenansicht nirgends auftauchen.
MARKER_MATERIAL = "Zwirbelkiste"

#: Ein Szenentext in der Grundform aus ``prompts/szene.md``: Versalien,
#: Doppelpunkt, Replik -- mit Inline-Regie und einer Regiezeile, wie sie
#: ``prompts/formen/dialog.md`` vorgibt.
SZENENTEXT = (
    "(Treppenhaus, kurz nach Mitternacht.)\n"
    "\n"
    "MIRA:(schliesst die Tuer)Du bist noch wach.\n"
    "POLA: Ich schlafe hier nicht mehr.\n"
    "(Pause. Niemand sagt etwas.)\n"
    "MIRA: Dann komm runter.\n"
)


@pytest.fixture
def db_pfad(tmp_path):
    """Eine Gruppe mit zwei Szenen -- eine geschrieben, eine nur geplant --
    und mit Material an allen Stellen, an denen es in der Datenbank steht."""
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_figur(conn, 1, "Mira", "24, arbeitet nachts")
    repo.setze_figur(conn, 1, "Pola", "58, will zurueck")
    repo.schreibe_journal(
        conn, 1, "entschieden", f"Setting steht: {MARKER_MATERIAL}", "extraktor"
    )
    repo.merke_nachricht(
        conn, 1, 9, "Ada", 0, "text", f"Meine Mutter sagte {MARKER_MATERIAL}",
        "2026-09-05T09:00:00+00:00",
    )
    repo.merke_nachricht(
        conn, 1, 10, "Ada", 0, "sprache", None, "2026-09-05T09:01:00+00:00"
    )
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "sprache", "/tmp/a.ogg", 200)
    repo.setze_transkript(conn, aufnahme_id, f"Ich hatte eine {MARKER_MATERIAL} dabei.")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, f"Mira erzaehlt von der {MARKER_MATERIAL}",
        [{"thema": f"Die {MARKER_MATERIAL} im Koffer", "kurz": MARKER_MATERIAL,
          "beleg_zitat": f"Ich hatte eine {MARKER_MATERIAL} dabei",
          "zitat_geprueft": 1}],
    )

    eins = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, eins, "titel", "Im Treppenhaus")
    repo.setze_szenenfeld(conn, eins, "form", "dialog")
    repo.setze_szenenfeld(conn, eins, "ort", "Treppenhaus")
    repo.setze_szenenfeld(conn, eins, "zeit", "kurz nach Mitternacht")
    repo.setze_szenenfeld(conn, eins, "anlass", "Pola will packen")
    repo.aktualisiere_szene(conn, eins, "Im Treppenhaus", None, SZENENTEXT)
    repo.setze_szene_figuren(
        conn, 1, eins,
        [repo.hole_figur(conn, 1, name)["id"] for name in ("Mira", "Pola")],
    )

    zwei = repo.stelle_szene_sicher(conn, 1, 2)
    repo.setze_szenenfeld(conn, zwei, "titel", "Am Bahnhof")
    repo.setze_szenenfeld(conn, zwei, "form", "lied")
    repo.setze_szenenfeld(conn, zwei, "ort", "Bahnhof")
    repo.setze_szenenfeld(conn, zwei, "was_passiert", "Mira faehrt nicht mit")
    conn.commit()
    return pfad


@pytest.fixture
def token(db_pfad):
    conn = db.verbinde(db_pfad)
    return repo.stelle_web_token_sicher(conn, 1)


@pytest.fixture
def basis(db_pfad):
    server = web.baue_server(db_pfad, bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def hole(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8")


def hole_mit_kopf(url: str) -> tuple[int, str, dict]:
    with urllib.request.urlopen(url, timeout=5) as antwort:
        return antwort.status, antwort.read().decode("utf-8"), dict(antwort.headers)


# --- Die Route -------------------------------------------------------------


def test_probenansicht_mit_gueltigem_token(basis, token):
    status, koerper = hole(f"{basis}/g/{token}/textbuch")
    assert status == 200
    assert "Probenansicht" in koerper


def test_probenansicht_ohne_token_gibt_404(basis):
    for pfad in ("/g//textbuch", "/g/falsch/textbuch", "/g/falsch/textbuch.md"):
        with pytest.raises(urllib.error.HTTPError) as fehler:
            hole(f"{basis}{pfad}")
        assert fehler.value.code == 404, pfad


def test_ein_unbekannter_unterpfad_gibt_404_statt_der_gruppenseite(basis, token):
    """Vor der Probenansicht war alles hinter ``/g/`` das Token. Wer jetzt
    ``/g/<token>/quatsch`` aufruft, soll 404 bekommen und nicht stumm die
    Gruppenseite -- sonst waere jede kuenftige Route schon belegt."""
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g/{token}/quatsch")
    assert fehler.value.code == 404


def test_probenansicht_geht_auch_mit_nginx_praefix(basis, token):
    assert hole(f"{basis}/theatersoap/g/{token}/textbuch")[0] == 200
    assert hole(f"{basis}/theatersoap/g/{token}/textbuch.md")[0] == 200


def test_die_probenansicht_nimmt_kein_post_an(basis, token):
    """Rein lesend: kein POST, kein Formular, kein Nonce."""
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/textbuch", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)
    assert fehler.value.code == 404


def test_der_server_schreibt_auch_hier_nicht_in_die_datenbank(basis, db_pfad, token):
    conn = db.verbinde(db_pfad)
    vorher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    hole(f"{basis}/g/{token}/textbuch")
    hole(f"{basis}/g/{token}/textbuch.md")
    hole(f"{basis}/g/{token}/textbuch.txt")
    nachher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    assert vorher == nachher


# --- Der Inhalt ------------------------------------------------------------


def test_die_szenen_stehen_in_reihenfolge_mit_ihren_angaben(basis, token):
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert koerper.index("Szene 1") < koerper.index("Szene 2")
    assert "Im Treppenhaus" in koerper and "Am Bahnhof" in koerper
    assert "Form: dialog" in koerper
    assert "Ort: Treppenhaus" in koerper
    assert "Zeit: kurz nach Mitternacht" in koerper
    assert "Anlass: Pola will packen" in koerper
    assert "Besetzung: Mira, Pola" in koerper
    assert "Du bist noch wach." in koerper


def test_eine_ungeschriebene_szene_ist_ein_platzhalter_keine_luecke(basis, token):
    """Wie in ``szenenfolge.textbuch``: eine fehlende Szene 2 saehe aus wie
    ein Fehler, ein Platzhalter mit ihrer Planung sagt die Wahrheit."""
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert web.TEXT_UNGESCHRIEBEN in koerper
    assert "Mira faehrt nicht mit" in koerper


def test_kein_material_in_der_probenansicht(basis, token):
    """Die harte Grenze (AGENTS.md, "Weboberflaeche"): Szenentexte und
    Szenenplanung -- sonst nichts."""
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert MARKER_MATERIAL not in koerper
    assert "Journal" not in koerper
    assert "Interview" not in koerper


def test_szenentext_wird_maskiert(basis, token, db_pfad):
    conn = db.verbinde(db_pfad)
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    repo.aktualisiere_szene(
        conn, szene_id, "Im Treppenhaus", None, "MIRA: <img src=x onerror=alert>"
    )
    conn.commit()

    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    # Der Text darf dastehen, das Tag nicht -- entscheidend ist die spitze
    # Klammer (wie in test_web.test_alles_aus_der_datenbank_wird_maskiert).
    assert "<img" not in koerper
    assert "&lt;img src=x onerror=alert&gt;" in koerper


def test_die_probenansicht_laedt_sich_nicht_nach(basis, token):
    """Kein meta refresh und kein sanftes Nachladen: ein Austausch des
    ``<body>`` risse Rollenfilter und Schriftgroesse mit."""
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert "meta refresh" not in koerper.lower()
    assert "http-equiv" not in koerper.lower()
    assert "setInterval" not in koerper


def test_die_gruppenseite_verlinkt_die_probenansicht(basis, token):
    koerper = hole(f"{basis}/g/{token}")[1]

    assert f'href="/theatersoap/g/{token}/textbuch"' in koerper
    assert "Probenansicht" in koerper


# --- Rollenfilter, Schrift, Regie -----------------------------------------


def test_die_rollenleiste_nennt_die_sprecher_und_alle(basis, token):
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert 'data-figur="MIRA"' in koerper
    assert 'data-figur="POLA"' in koerper
    assert ">alle<" in koerper
    # Die Schreibweise der Figurenliste, nicht die Versalien aus dem Text --
    # sie steht auch im teilbaren Link (#figur=Mira).
    assert 'data-name="Mira"' in koerper


def test_ohne_sprecherzeilen_gibt_es_keine_rollenleiste(basis, token, db_pfad):
    """Der defensive Fall: eine Szene, die als Geschichte dasteht (Phase 6,
    Prosa) hat keine Repliken. Dann fehlt die Leiste ganz, statt falsch zu
    markieren."""
    conn = db.verbinde(db_pfad)
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    repo.aktualisiere_szene(
        conn, szene_id, "Im Treppenhaus", None,
        "Mira kommt nach Hause und findet Pola im Treppenhaus sitzen.\n"
        "Sie sagt nichts, sie setzt sich dazu.",
    )
    conn.commit()

    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert "class=\"leiste rollen\"" not in koerper
    assert "Mira kommt nach Hause" in koerper, "der Text steht trotzdem da"


def test_die_repliken_tragen_ihre_figur_und_die_regie_ihr_span(basis, token):
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    assert '<p class="replik" data-figur="MIRA">' in koerper
    assert '<span class="regie">(schliesst die Tuer)</span>' in koerper
    assert '<p class="regie regie-zeile">(Pause. Niemand sagt etwas.)</p>' in koerper


def test_die_leseeinstellungen_stehen_als_knoepfe_da(basis, token):
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    for stufe in ("klein", "mittel", "gross"):
        assert f'data-schrift="{stufe}"' in koerper
    assert "Regieanweisungen ausblenden" in koerper
    # Der Zustand steht in der URL, nicht auf dem Server.
    assert "location.hash" in koerper


def test_die_druckansicht_setzt_ein_manuskript(basis, token):
    koerper = hole(f"{basis}/g/{token}/textbuch")[1]

    druck = koerper.split("@media print", 1)[1]
    assert "page-break-after: always" in druck
    assert "serif" in druck
    assert ".leiste" in druck and "display: none" in druck
    assert "font-weight: 700" in druck


# --- Die Dateien -----------------------------------------------------------


def test_md_und_txt_liefern_szenenfolge_textbuch(basis, token, db_pfad):
    """Keine zweite Wahrheit: beide Dateien sind woertlich das, was der Knopf
    "Textbuch als Datei" im Chat verschickt."""
    conn = db.verbinde(db_pfad)
    erwartet = szenenfolge.textbuch(conn, 1)

    status_md, md, kopf_md = hole_mit_kopf(f"{basis}/g/{token}/textbuch.md")
    status_txt, txt, kopf_txt = hole_mit_kopf(f"{basis}/g/{token}/textbuch.txt")

    assert (status_md, status_txt) == (200, 200)
    assert md == erwartet
    assert txt == erwartet
    assert kopf_md["Content-Type"] == "text/markdown; charset=utf-8"
    assert kopf_txt["Content-Type"] == "text/plain; charset=utf-8"
    assert kopf_md["Content-Disposition"] == 'attachment; filename="textbuch.md"'
    assert kopf_txt["Content-Disposition"] == 'attachment; filename="textbuch.txt"'


def test_die_datei_traegt_die_ungeschriebene_szene_mit(basis, token):
    md = hole(f"{basis}/g/{token}/textbuch.md")[1]

    assert "## Szene 1: Im Treppenhaus" in md
    assert "## Szene 2: Am Bahnhof" in md
    assert "(noch nicht geschrieben)" in md


# --- Die reinen Funktionen -------------------------------------------------


@pytest.mark.parametrize(
    "zeile, erwartet",
    [
        ("MIRA: Da.", "MIRA"),
        ("MIRA:(steht auf)Da.", "MIRA"),
        ("CHOR: Wir warten seit zwei Stunden hier.", "CHOR"),
        ("FRAU MUELLER: Guten Tag.", "FRAU MUELLER"),
        ("SZENE 1: EINUNDFUENFZIG STUNDEN ca. 10 min", None),
        ("TITEL: Einundfuenfzig Stunden", None),
        ("KURZ: Leyla wartet auf dem Schulhof.", None),
        ("Sie sagte: das war es dann.", None),
        ("(Pause. Niemand sagt etwas.)", None),
        ("Mira: Da.", None),
        ("", None),
        ("A: Da.", None),
        ("12: Da.", None),
        ("EIN SEHR LANGER NAME, DER KEINER MEHR IST: Da.", None),
    ],
)
def test_sprecher_der_zeile_ist_defensiv(zeile, erwartet):
    assert web.sprecher_der_zeile(zeile) == erwartet


def test_eine_kleingeschriebene_figur_zaehlt_nur_wenn_es_sie_gibt():
    """Die eine Ausnahme von der Versalien-Regel: schreibt ein Modell
    ``Mira:``, gilt das nur, wenn die Gruppe eine Figur Mira hat."""
    assert web.sprecher_der_zeile("Mira: Da.", {"MIRA"}) == "MIRA"
    assert web.sprecher_der_zeile("Mira: Da.", {"POLA"}) is None


def test_szenentext_html_haelt_die_reihenfolge_und_verliert_nichts():
    koerper, sprecher = web.szenentext_html(SZENENTEXT)

    assert sprecher == ["MIRA", "POLA"]
    assert koerper.index("MIRA") < koerper.index("POLA")
    assert "Dann komm runter." in koerper
    assert "Treppenhaus, kurz nach Mitternacht." in koerper


def test_eine_umbrochene_replik_bleibt_bei_ihrer_figur():
    """Eine Zeile ohne eigenen Sprecher direkt unter einer Replik gehoert zu
    ihr -- sonst faellt die zweite Haelfte eines langen Satzes beim
    Rollenfilter aus der Hervorhebung heraus."""
    koerper, _ = web.szenentext_html("MIRA: Erster Teil,\nzweiter Teil.\n")

    assert '<p class="replik weiter" data-figur="MIRA">zweiter Teil.</p>' in koerper


def test_nach_einer_leerzeile_gehoert_der_absatz_niemandem():
    koerper, _ = web.szenentext_html("MIRA: Erster Teil.\n\nEin Absatz.\n")

    assert '<p class="prosa">Ein Absatz.</p>' in koerper

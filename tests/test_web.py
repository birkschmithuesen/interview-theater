"""Der Webserver, ueber echtes HTTP.

Startet ihn auf 127.0.0.1:0 in einem Thread und ruft ihn mit urllib ab --
kein Netzzugriff nach draussen. Ueber HTTP statt ueber die Renderfunktionen
allein, weil hier die Verdrahtung geprueft wird: Routing, Statuscodes, das
Praefix und die read-only geoeffnete Datenbank.
"""

import threading
import urllib.error
import urllib.request

import pytest
from interview_theater import db, repo, web, web_daten


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    repo.setze_arbeitsstand(conn, 1, "kernthema", "Ankommen")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Was war in deinem Koffer?")
    repo.setze_figur(conn, 1, "Maria", "kam 1998")
    repo.schreibe_journal(conn, 1, "entschieden", "Kernthema ist Ankommen", "extraktor")
    # Ein fertig verdichtetes Interview: die Gruppenseite ist neben dem
    # Gespraechs-Prompt der zweite Ort, an dem die Verdichtungen sichtbar
    # werden muessen (Brief-Punkt 3).
    repo.merke_nachricht(conn, 1, 9, "Ada", 0, "sprache", None, "2026-09-05T09:00:00+00:00")
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 9, "lang", "sprache", "/tmp/a.ogg", 200)
    repo.setze_aufnahme_name(conn, aufnahme_id, "Marias Interview")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Maria erzaehlt vom ersten Winter",
        [
            {"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
             "zitat_geprueft": 1},
            {"thema": "Arbeit", "beleg_zitat": "so hat das niemand gesagt",
             "zitat_geprueft": 0},
        ],
    )
    # Die Verbindung bleibt absichtlich offen: sie haelt die WAL-Dateien am
    # Leben, so wie im Betrieb der Bot-Prozess.
    conn.commit()
    return pfad


@pytest.fixture
def token(db_pfad):
    conn = db.verbinde(db_pfad)
    return repo.stelle_web_token_sicher(conn, 1)


@pytest.fixture
def basis(db_pfad):
    """Ein laufender Server auf einem freien Port; liefert seine Basis-URL."""
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


def test_gesund_antwortet_ok(basis):
    status, koerper = hole(f"{basis}/gesund")
    assert status == 200
    assert koerper.strip() == "ok"


def test_dashboard_zeigt_die_gruppentitel(basis):
    status, koerper = hole(f"{basis}/")
    assert status == 200
    assert "Die Ankommenden" in koerper
    assert "Bot-Zuordnung" in koerper
    # Seit 05.09. kein meta refresh mehr (klappte alles zu), sondern sanftes
    # Nachladen per fetch -- der Intervallwert steht im Skript.
    assert 'http-equiv="refresh"' not in koerper
    assert 'INTERVALL_MS = 10000' in koerper


def test_gruppenseite_zeigt_das_kernthema(basis, token):
    status, koerper = hole(f"{basis}/g/{token}")
    assert status == 200
    assert "Ankommen" in koerper
    assert "Maria" in koerper
    assert "Kernthema ist Ankommen" in koerper


def test_gruppenseite_zeigt_die_verdichtungen_mit_belegzitat(basis, token):
    """Brief-Punkt (3) fuer die Gruppenseite: Zusammenfassung und Kernthemen
    stehen da, das Zitat aber nur, wenn es die Pruefung bestanden hat -- ein
    ungepruefter Satz in Anfuehrungszeichen waere genau das, wogegen das
    Belegzitat-Prinzip antritt."""
    koerper = hole(f"{basis}/g/{token}")[1]

    assert "Interview 1" in koerper  # nie der Aufnahmename (Birk 05.09.)
    assert "Maria erzaehlt vom ersten Winter" in koerper
    assert "Ankommen" in koerper and "Arbeit" in koerper
    assert "Ich hatte nur einen Koffer" in koerper
    assert "so hat das niemand gesagt" not in koerper


def test_gruppenseite_zeigt_umfang_je_interview(basis, token):
    """§ 10.6: je Interview eine Einheit -- Name, Teile-Zahl, Gesamtdauer.
    Die Aufnahme in der Testdatenbank hat keine Teile (Zustand vor dem
    Nachtrag), also steht dort nur die Dauer: 200 s = 3:20."""
    koerper = hole(f"{basis}/g/{token}")[1]

    assert "3:20" in koerper


def test_umfang_nennt_teile_und_dauer(basis, token):
    from interview_theater import web

    assert web._umfang(4, 727) == "4 Teile · 12:07"
    assert web._umfang(1, 65) == "1 Teil · 1:05"
    assert web._umfang(0, None) == "", "ohne Teile und ohne Dauer bleibt die Zeile leer"


def test_gruppenseite_zeigt_die_frageliste(basis, token):
    assert "Was war in deinem Koffer?" in hole(f"{basis}/g/{token}")[1]


def test_gruppenseite_klappt_jede_szene_auf_mit_planung_und_volltext():
    """05.09.2026: Summary = Szene N · Titel · Form · Ort · Wer, aufgeklappt
    alle Felder und dann der Volltext."""
    daten = {
        "chat_id": 1, "titel": "Die Ankommenden", "bot_name": "gruppe1",
        "interviewmodus_seit": None, "figuren": [], "interviews": [], "journal": [],
        "arbeitsstand": {"phase": 6, "begriffe": None, "fragen": None,
                         "kernthema": None, "kernthema_begruendung": None,
                         "format": None, "rahmen": None, "hauptkonflikt": None},
        "szenen": [{
            "nummer": 1, "titel": "Im Kessel", "kurzbeschreibung": "Sie warten",
            "volltext": "MIRA: Da.", "geaendert_am": None,
            "figuren": ["Mira", "Pola"], "form": "Dialog", "ort": "Polizeikessel",
            "zeit": None, "anlass": "seit zwei Stunden", "was_passiert": "sie warten",
            "was_anders": None, "kernsaetze": None, "ton": "hitzig",
        }],
    }

    koerper = web.gruppe_html(daten)

    assert "<summary>Szene 1 · Im Kessel · Dialog · Polizeikessel · Mira, Pola</summary>" in koerper
    assert "seit zwei Stunden" in koerper and "hitzig" in koerper
    assert "MIRA: Da." in koerper


def test_eine_geplante_szene_ohne_text_sagt_das(basis, token, db_pfad):
    conn = db.verbinde(db_pfad)
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "Lied")

    koerper = hole(f"{basis}/g/{token}")[1]

    assert "Noch kein Text" in koerper


def test_gruppenseite_zeigt_je_figur_stimme_und_quelle(basis, token, db_pfad):
    conn = db.verbinde(db_pfad)
    figur_id = repo.hole_figur(conn, 1, "Maria")["id"]
    repo.setze_figur_quelle(conn, figur_id, repo.transkripte(conn, 1)[0]["id"])
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Ich hatte nur einen Koffer"])

    koerper = hole(f"{basis}/g/{token}")[1]

    assert "Sprechweise aus Interview 1" in koerper
    assert "Kurze Saetze." in koerper
    assert "Ich hatte nur einen Koffer" in koerper


def test_interview_summary_zeigt_die_kurzformen_nicht_die_zusammenfassung(
    basis, token, db_pfad
):
    """N6: die Summary-Zeile sind die Ergebnisse. Zusammenfassung und Zitat
    stehen im aufgeklappten Teil."""
    koerper = hole(f"{basis}/g/{token}")[1]

    summary = koerper.split("<summary>Interview 1", 1)[1].split("</summary>", 1)[0]
    assert "Ankommen" in summary and "Arbeit" in summary
    assert "ersten Winter" not in summary, "die Zusammenfassung gehoert nicht in die Summary"
    assert "Ich hatte nur einen Koffer" not in summary, "kein Zitat in der Summary"
    # Aufgeklappt steht beides.
    assert "Maria erzaehlt vom ersten Winter" in koerper
    assert "Ich hatte nur einen Koffer" in koerper


def test_dashboard_nennt_den_rahmen_und_die_formen_der_szenen(db_pfad):
    """Das Format des Stuecks steht seit dem 05.09.2026 abends nicht mehr auf
    der Seite -- es wird nicht mehr gefragt. Die Form je Szene schon."""
    conn = db.verbinde(db_pfad)
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied, Rap")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    repo.setze_szenenfeld(conn, repo.stelle_szene_sicher(conn, 1, 1), "form", "Dialog")
    repo.setze_szenenfeld(conn, repo.stelle_szene_sicher(conn, 1, 2), "form", "Dialog")
    repo.setze_szenenfeld(conn, repo.stelle_szene_sicher(conn, 1, 3), "form", "Lied")

    lesend = web_daten.oeffne_lesend(db_pfad)
    koerper = web.dashboard_html(web_daten.dashboard(lesend))
    lesend.close()

    assert "Eine Nacht im Treppenhaus" in koerper
    assert "Musical: Dialog, Lied, Rap" not in koerper
    assert "Szenen: <b>3</b> — 2 Dialog, 1 Lied" in koerper


def test_dashboard_zeigt_die_ergebnisse_je_interview_ohne_zitate(db_pfad):
    """N6 auf dem projizierten Dashboard: die Kurzformen als eine Zeile je
    Interview -- ohne Zitate, ohne Zusammenfassung, ohne Sprachprofil."""
    conn = db.verbinde(db_pfad)
    figur_id = repo.hole_figur(conn, 1, "Maria")["id"]
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Ich hatte nur einen Koffer"])

    lesend = web_daten.oeffne_lesend(db_pfad)
    koerper = web.dashboard_html(web_daten.dashboard(lesend))
    lesend.close()

    assert "Ankommen · Arbeit" in koerper
    assert "Ich hatte nur einen Koffer" not in koerper
    assert "Maria erzaehlt vom ersten Winter" not in koerper
    assert "Kurze Saetze." not in koerper


def test_arbeitsstand_zeigt_den_rahmen_den_konflikt_nur_wenn_gesetzt():
    """Phase 5 (05.09.2026 abends): der Rahmen ist eine eigene Zeile, das
    Format steht nicht mehr da. Der Hauptkonflikt taucht nur auf, wenn es
    einen gibt -- eine leere Zeile daneben sieht aus wie eine unerledigte
    Aufgabe, und genau das ist er nicht."""
    stand = {
        "phase": 5, "begriffe": None, "fragen": None, "kernthema": "Ankommen",
        "kernthema_begruendung": None, "format": "Musical: Dialog, Lied, Rap",
        "rahmen": "Eine Nacht im Treppenhaus", "hauptkonflikt": None,
    }

    ohne = web._arbeitsstand_html(stand, [])
    assert "Musical: Dialog, Lied, Rap" not in ohne
    assert "Eine Nacht im Treppenhaus" in ohne
    assert "Hauptkonflikt" not in ohne

    mit = web._arbeitsstand_html({**stand, "hauptkonflikt": "bleiben gegen gehen"}, [])
    assert "Hauptkonflikt" in mit and "bleiben gegen gehen" in mit


def test_unbekanntes_token_gibt_404_ohne_hinweis(basis):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g/falsch")
    assert fehler.value.code == 404
    koerper = fehler.value.read().decode("utf-8")
    assert "Die Ankommenden" not in koerper, "verraet nicht, dass es Gruppen gibt"


def test_unbekannter_pfad_gibt_404(basis):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/admin")
    assert fehler.value.code == 404


def test_routen_gehen_auch_mit_nginx_praefix(basis, token):
    """Ob nginx /theatersoap weiterreicht oder abschneidet, steht in der
    nginx-Konfiguration -- der Server nimmt deshalb beide Formen."""
    assert hole(f"{basis}/theatersoap/")[0] == 200
    assert hole(f"{basis}/theatersoap/gesund")[1].strip() == "ok"
    assert "Ankommen" in hole(f"{basis}/theatersoap/g/{token}")[1]


def test_alles_aus_der_datenbank_wird_maskiert(basis, db_pfad, token):
    """Gruppentitel und Kernthema kommen aus Telegram bzw. aus einem
    Sprachmodell. Was da an spitzen Klammern ankommt, darf im Browser kein
    Skript werden."""
    conn = db.verbinde(db_pfad)
    repo.setze_arbeitsstand(conn, 1, "kernthema", "<script>alert(1)</script>")
    repo.sichere_gruppe(conn, 1, "gruppe1", "<img src=x onerror=alert(2)>")

    for url in (f"{basis}/", f"{basis}/g/{token}"):
        koerper = hole(url)[1]
        assert "<script>alert(1)</script>" not in koerper
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in koerper
        # Der Text darf dastehen, das Tag nicht: entscheidend ist die spitze
        # Klammer, nicht das Wort onerror.
        assert "<img" not in koerper
        assert "&lt;img src=x onerror=alert(2)&gt;" in koerper


def test_dashboard_zeigt_keinen_nachrichtentext(basis, db_pfad):
    conn = db.verbinde(db_pfad)
    repo.merke_nachricht(conn, 1, 10, "Ada", 0, "text", "Meine Mutter starb 1998",
                         "2026-09-05T10:00:00+00:00")
    assert "Meine Mutter" not in hole(f"{basis}/")[1]


def test_der_server_schreibt_nicht_in_die_datenbank(basis, db_pfad, token):
    """Der einzige Schreibweg bleibt der Chat. Geprueft an der Datei selbst:
    nach Abrufen beider Seiten steht in der Datenbank nichts Neues."""
    conn = db.verbinde(db_pfad)
    vorher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    hole(f"{basis}/")
    hole(f"{basis}/g/{token}")
    nachher = [
        conn.execute(f"SELECT count(*) FROM {tabelle}").fetchone()[0]
        for tabelle in db.TABELLEN_MIT_CHAT_ID
    ]
    assert vorher == nachher


def test_leere_datenbank_ergibt_trotzdem_eine_seite(tmp_path):
    """Am Workshopmorgen hat noch keine Gruppe geschrieben -- das Dashboard
    muss trotzdem stehen, sonst sieht das Team einen Fehler statt einer
    leeren Seite."""
    pfad = str(tmp_path / "leer.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    server = web.baue_server(pfad, bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, koerper = hole(f"http://127.0.0.1:{server.server_address[1]}/")
        assert status == 200
        assert "Noch keine Gruppe" in koerper
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_fehlende_datenbank_gibt_500_statt_abzustuerzen(tmp_path):
    server = web.baue_server(str(tmp_path / "gibtsnicht.db"), bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        basis = f"http://127.0.0.1:{server.server_address[1]}"
        assert hole(f"{basis}/gesund")[1].strip() == "ok", "Health-Check ohne DB"
        with pytest.raises(urllib.error.HTTPError) as fehler:
            hole(f"{basis}/")
        assert fehler.value.code == 500
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("bind", ["0.0.0.0:8010", ":::8010", "8010", "127.0.0.1:abc"])
def test_unbrauchbare_bindadressen_werden_abgelehnt(bind, tmp_path):
    """0.0.0.0 waere ein Tippfehler mit Folgen: die Gruppenseiten haben kein
    Login, und in den Interviews stehen Lebensgeschichten."""
    with pytest.raises(RuntimeError):
        web.baue_server(str(tmp_path / "t.db"), bind=bind)


def test_bind_wird_zerlegt():
    assert web.lies_bind("100.75.24.33:8010") == ("100.75.24.33", 8010)
    assert web.lies_bind("127.0.0.1:0") == ("127.0.0.1", 0)


def test_main_nimmt_die_umgebung_und_startet(monkeypatch, db_pfad):
    """Die Verdrahtung von `python -m interview_theater.web`: main() liest genau
    drei Variablen und reicht sie durch. Ohne diesen Test waere der erste
    echte Start der erste Test."""
    gesehen = {}

    class FalscherServer:
        def serve_forever(self):
            gesehen["gestartet"] = True

    def falsches_baue_server(pfad, bind, praefix):
        gesehen.update(pfad=pfad, bind=bind, praefix=praefix)
        return FalscherServer()

    monkeypatch.setattr(web, "baue_server", falsches_baue_server)
    monkeypatch.setenv("IT_DB", db_pfad)
    monkeypatch.setenv("IT_WEB_BIND", "100.75.24.33:8010")
    monkeypatch.delenv("IT_WEB_PREFIX", raising=False)

    web.main()

    assert gesehen == {"pfad": db_pfad, "bind": "100.75.24.33:8010",
                       "praefix": "/theatersoap", "gestartet": True}


def test_main_ohne_ts_db_bricht_ab(monkeypatch):
    monkeypatch.delenv("IT_DB", raising=False)
    with pytest.raises(SystemExit) as fehler:
        web.main()
    assert fehler.value.code == 1


def test_praefix_wird_nur_am_anfang_abgeschnitten():
    assert web._pfad_ohne_praefix("/theatersoap/g/abc", "/theatersoap") == "/g/abc"
    assert web._pfad_ohne_praefix("/theatersoap", "/theatersoap") == "/"
    assert web._pfad_ohne_praefix("/g/abc", "/theatersoap") == "/g/abc"
    assert web._pfad_ohne_praefix("/g/theatersoap", "/theatersoap") == "/g/theatersoap"


def test_fragen_eine_zeile_je_frage_thema_fett():
    from interview_theater import web
    html_ = web._fragen_html(
        "Küche: Erzähl mir von einem Gericht. | Erste Liebe: Erzähl von einem Moment.\nHawaii: Was fällt dir ein?"
    )
    assert html_.count("<li>") == 3
    assert "<b>Küche</b> Erzähl mir von einem Gericht." in html_
    assert "<b>Hawaii</b> Was fällt dir ein?" in html_


def test_fragen_ohne_thema_bleiben_ganz():
    from interview_theater import web
    html_ = web._fragen_html("Wann warst du zuletzt glücklich?")
    assert "<b>" not in html_ and "Wann warst du zuletzt" in html_


def test_fragen_werden_escaped():
    from interview_theater import web
    assert "<script>" not in web._fragen_html("Thema: <script>x</script>")


def test_dashboard_verlinkt_jede_gruppe_auf_ihre_gruppenseite(tmp_path):
    """Echte Daten statt Attrappe: der Dashboard-Dict hat viele Pflichtfelder."""
    from interview_theater import db, repo, web, web_daten
    pfad = str(tmp_path / "t.db")
    c = db.verbinde(pfad); db.initialisiere(c)
    repo.sichere_gruppe(c, -1, "b", "Gruppe A")
    token = repo.stelle_web_token_sicher(c, -1)
    c.close()
    lesend = web_daten.oeffne_lesend(pfad)
    html_ = web.dashboard_html(web_daten.dashboard(lesend), praefix="/theatersoap")
    assert f'<a href="/theatersoap/g/{token}">Gruppe A</a>' in html_


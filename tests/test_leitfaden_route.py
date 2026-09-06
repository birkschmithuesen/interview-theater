"""Die Leitfaden-Route ``/g/<token>/leitfaden`` (06.09.2026).

Der gebaute Leitfaden wird einmal in den Chat geschickt und versinkt -- dabei
ist genau er das Dokument, das eine Sechzehnjaehrige in der Hand haelt, wenn
sie eine fremde Person anspricht. Die Route stellt ihn gross, kontrastreich
und druckbar hin.

Ueber echtes HTTP wie ``tests/test_web.py``, aus demselben Grund: geprueft
wird die Verdrahtung -- Routing, Statuscodes, das Praefix, die read-only
geoeffnete Datenbank. Dazu die harte Grenze, die auf jeder Seite ohne Login
gilt: **kein Transkript und kein Nachrichtentext im HTML.**
"""

import threading
import urllib.error
import urllib.request

import pytest

from interview_theater import (
    befehle, db, knoepfe, leitfaden, repo, web, web_daten,
)

from test_knoepfe import TelegramAttrappe


FRAGEN = "Was war in deinem Koffer?\nWie war der erste Winter?"
WEICH = "2 — Erzaehl mal, wie der erste Winter fuer dich war."
EROEFFNUNG = "Wir machen ein Theaterstueck und sammeln Geschichten."
ABSCHLUSS = "Danke dir. Wir melden uns, wenn das Stueck steht."


def _fuelle(conn, chat_id=1):
    for feld, wert in (
        ("fragen", FRAGEN),
        ("fragen_weich", WEICH),
        ("interview_eroeffnung", EROEFFNUNG),
        ("interview_abschluss", ABSCHLUSS),
    ):
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)


@pytest.fixture
def db_pfad(tmp_path):
    pfad = str(tmp_path / "t.db")
    conn = db.verbinde(pfad)
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, 1, "gruppe1", "Die Ankommenden")
    _fuelle(conn)
    # Material, das auf dieser Seite nichts zu suchen hat.
    repo.merke_nachricht(
        conn, 1, 10, "Ada", 0, "text", "Meine Mutter starb 1998",
        "2026-09-06T10:00:00+00:00",
    )
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 10, "lang", "text", None, 200)
    repo.setze_transkript(conn, aufnahme_id, "Ich hatte nur einen Koffer dabei.")
    repo.speichere_verdichtung(
        conn, 1, aufnahme_id, "Sie erzaehlt vom ersten Winter",
        [{"thema": "Ankommen", "beleg_zitat": "Ich hatte nur einen Koffer",
          "zitat_geprueft": 1}],
    )
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


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- Routing ---------------------------------------------------------------


def test_mit_token_kommt_200(basis, token):
    status, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert status == 200
    assert EROEFFNUNG in koerper
    assert ABSCHLUSS in koerper


def test_ohne_token_kommt_404(basis):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g//{leitfaden.WEB_PFAD}")
    assert fehler.value.code == 404

    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g/falschestoken/{leitfaden.WEB_PFAD}")
    assert fehler.value.code == 404


def test_unbekannte_unterseite_kommt_404(basis, token):
    with pytest.raises(urllib.error.HTTPError) as fehler:
        hole(f"{basis}/g/{token}/journal")
    assert fehler.value.code == 404


def test_auch_unter_dem_praefix(db_pfad, token):
    """Ob nginx das Praefix durchreicht, entscheidet die nginx-Zeile -- also
    nimmt das Routing beide Formen an, wie bei jeder anderen Route."""
    server = web.baue_server(db_pfad, bind="127.0.0.1:0")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        basis = f"http://127.0.0.1:{server.server_address[1]}"
        status, koerper = hole(
            f"{basis}{web.VORGABE_PRAEFIX}/g/{token}/{leitfaden.WEB_PFAD}"
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200
    assert EROEFFNUNG in koerper


def test_die_route_nimmt_kein_post(basis, token):
    """Rein lesend: kein POST, kein Nonce."""
    anfrage = urllib.request.Request(
        f"{basis}/g/{token}/{leitfaden.WEB_PFAD}",
        data=b'{"feld": "rahmen", "wert": "x"}',
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(urllib.error.HTTPError) as fehler:
        urllib.request.urlopen(anfrage, timeout=5)

    assert fehler.value.code == 404


def test_die_seite_laedt_nicht_nach(basis, token):
    """Kein sanftes Nachladen: einer Interviewerin mitten im Gespraech soll
    der Text nicht unter dem Daumen ausgetauscht werden."""
    _, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert "<script" not in koerper
    assert 'http-equiv="refresh"' not in koerper
    assert "nonce" not in koerper


def test_der_server_schreibt_dabei_nicht(basis, db_pfad, token):
    conn = db.verbinde(db_pfad)
    vorher = [
        conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in db.TABELLEN_MIT_CHAT_ID
    ]

    hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert vorher == [
        conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in db.TABELLEN_MIT_CHAT_ID
    ]


# --- Inhalt ----------------------------------------------------------------


def test_identischer_inhalt_wie_der_chat_text(basis, db_pfad, token):
    """Keine zweite Wahrheit: Route und Chat stehen auf derselben Funktion
    (``leitfaden.bausteine``). Geprueft wird Stueck fuer Stueck -- der Satz,
    den die Interviewerin sagt, und der Kern darunter."""
    conn = db.verbinde(db_pfad)
    chat_text = leitfaden.baue(conn, 1)
    _, seite = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    teil = leitfaden.bausteine(web_daten._arbeitsstand(conn, 1))
    assert teil["eroeffnung"] in chat_text and teil["eroeffnung"] in seite
    assert teil["abschluss"] in chat_text and teil["abschluss"] in seite
    for frage in teil["fragen"]:
        assert frage["text"] in chat_text
        assert frage["text"] in seite
        if frage["kern"]:
            assert frage["kern"] in chat_text and frage["kern"] in seite


def test_jede_frage_steht_einzeln(basis, token):
    _, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert koerper.count('class="frage"') == 2


def test_eine_druckregel_ist_dabei(basis, token):
    _, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert "@media print" in koerper


def test_leerer_zustand_ist_eine_ruhige_seite(basis, db_pfad, token):
    """Steht noch kein Leitfaden, kommt kein Fehler."""
    conn = db.verbinde(db_pfad)
    repo.setze_arbeitsstand(conn, 1, "fragen", None)

    status, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert status == 200
    assert web.TEXT_LEITFADEN_LEER in koerper


def test_kein_transkript_und_kein_nachrichtentext_im_html(basis, token):
    """Die harte Grenze, wie der bestehende Test in ``tests/test_web.py``:
    eine URL ohne Login ist nicht der Ort fuer Interviewmaterial."""
    _, koerper = hole(f"{basis}/g/{token}/{leitfaden.WEB_PFAD}")

    assert "Meine Mutter" not in koerper
    assert "nur einen Koffer" not in koerper
    assert "erste Winter fuer dich" in koerper  # die eigene Frage schon


def test_die_seite_laedt_keine_szenen_und_kein_journal(db_pfad):
    """``leitfaden_nach_token`` holt nur den Arbeitsstand -- was gar nicht
    geladen wird, kann auch nicht versehentlich ausgeliefert werden."""
    conn = web_daten.oeffne_lesend(db_pfad)
    try:
        daten = web_daten.leitfaden_nach_token(
            conn, repo.stelle_web_token_sicher(db.verbinde(db_pfad), 1)
        )
    finally:
        conn.close()

    assert set(daten) == {"chat_id", "titel", "arbeitsstand"}


# --- Verlinkt an zwei Orten ------------------------------------------------


def test_die_gruppenseite_verlinkt_die_ansicht(basis, token):
    _, koerper = hole(f"{basis}/g/{token}")

    assert f'href="{token}/{leitfaden.WEB_PFAD}"' in koerper
    assert web.TEXT_LEITFADEN_LINK in koerper
    # Der bestehende Text bleibt daneben stehen.
    assert EROEFFNUNG in koerper


def test_der_chat_verlinkt_zusaetzlich(conn, einst, tg):
    """Zusaetzlich zum bestehenden Text, der unveraendert bleibt."""
    from dataclasses import replace

    _fuelle(conn)
    mit_url = replace(einst, web_url="https://lab.test/theatersoap")

    leitfaden.sende(conn, tg, 1, e=mit_url)

    text = tg.gesendet[-1][1]
    assert leitfaden.TEXT_KOPF in text
    assert EROEFFNUNG in text
    token = repo.stelle_web_token_sicher(conn, 1)
    assert f"https://lab.test/theatersoap/g/{token}/leitfaden" in text


def test_ohne_web_url_bleibt_der_text_wie_er_war(conn, einst, tg):
    """Kein halber Link: fehlt die Basis-URL, steht die Zeile gar nicht da."""
    _fuelle(conn)

    leitfaden.sende(conn, tg, 1, e=einst)

    assert "leitfaden" not in tg.gesendet[-1][1].lower().split("euer")[0]
    assert "http" not in tg.gesendet[-1][1]


def test_ohne_leitfaden_kommt_kein_link(conn, einst, tg):
    from dataclasses import replace

    leitfaden.sende(conn, tg, 1, e=replace(einst, web_url="https://lab.test/x"))

    assert tg.gesendet[-1][1] == leitfaden.TEXT_LEER


def test_der_befehl_reicht_die_einstellungen_durch(conn, einst, tg):
    """``/leitfaden`` ist der Notausgang -- auch er zeigt den Link."""
    from dataclasses import replace

    _fuelle(conn)
    mit_url = replace(einst, web_url="https://lab.test/theatersoap")

    befehle.behandle(conn, tg, mit_url, 1, "/leitfaden", None)

    assert "https://lab.test/theatersoap/g/" in tg.gesendet[-1][1]


def test_der_knopf_zeigt_den_link_auch(conn, einst, tg):
    from dataclasses import replace

    _fuelle(conn)
    mit_url = replace(einst, web_url="https://lab.test/theatersoap")
    knopf_id = repo.lege_knopf_an(conn, 1, knoepfe.ART_LEITFADEN, None)

    knoepfe.behandle(
        conn, tg, None, mit_url,
        {"callback_query_id": "q1", "data": f"k:{knopf_id}", "chat_id": 1,
         "message_id": 777},
    )

    assert "https://lab.test/theatersoap/g/" in tg.gesendet[-1][1]


def test_der_chat_text_bleibt_sonst_unveraendert(conn, tg):
    """Ohne ``e`` ist die Nachricht wortgleich die von gestern."""
    _fuelle(conn)

    leitfaden.sende(conn, tg, 1)

    assert tg.gesendet[-1][1] == f"{leitfaden.TEXT_KOPF}\n\n{leitfaden.baue(conn, 1)}"

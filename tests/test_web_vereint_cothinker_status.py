"""e2e-Nachweis der CoThinker-Statuszeile OHNE Browser (Task 5, Karte
2026-10-03-cothinker-statuszeile).

Ein echter Playwright-Lauf (wie ``tests/e2e/test_web_chat_e2e.py``) waere
fuer eine reine Statuszeile unverhaeltnismaessig: er braeuchte ein
Fake-Mikrofon, VAD und eine echte Segmentuebertragung durch einen
laufenden Bot-Thread, nur um am Ende dasselbe ``data-zustand``-Attribut zu
pruefen, das dieser Test direkt am Render-Ergebnis liest. Stattdessen faehrt
dieser Test denselben Daten- und Render-Pfad, den der Browser abruft:
``repo`` praepariert die DB-Zeilen, ``web_daten.gruppe_nach_token`` liest sie
read-only zurueck (derselbe Weg wie jede echte HTTP-Antwort), und
``web._buehne_html`` baut daraus genau das Markup, das ``web_vereint``s
``ladeBuehne()`` im Browser einsetzen wuerde. Laut Plan
(``docs/superpowers/plans/2026-10-03-cothinker-statuszeile.md``) ist das
der ausdruecklich erlaubte Ersatz fuer einen echten Browserlauf.

Durchgespielt werden die drei Zustaende aus dem Plan hintereinander gegen
DIESELBE Gruppe -- hoert -> denkt -> schweigt -- wie es der zeitliche
Ablauf einer echten Phase 4 waere, jeweils mit einer DB-Aenderung und
erneutem Rendern dazwischen."""

from interview_theater import db, repo, web, web_daten

CHAT = 1


def test_statuszeile_wechselt_von_hoert_ueber_denkt_zu_schweigt(tmp_path):
    conn = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(conn)
    repo.sichere_gruppe(conn, CHAT, "gruppe1", "Testgruppe")
    repo.setze_phase(conn, CHAT, 4)
    token = repo.stelle_web_token_sicher(conn, CHAT)

    def rendere() -> str:
        daten = web_daten.gruppe_nach_token(conn, token)
        assert daten is not None
        return web._buehne_html(daten)

    # 1. hoert: ein frisches Brainstorm-Segment, noch kein Lauf, keine Karte.
    # ``lege_aufnahme_an`` setzt ``empfangen_am`` selbst auf "jetzt" -- kein
    # manuelles Nachziehen des Zeitstempels noetig (anders als beim
    # ``brainstorm_reaktion_am``-Muster in ``tests/test_repo_brainstorm.py``,
    # das ein bestehendes Segment nachtraeglich markiert).
    segment_id = repo.lege_aufnahme_an(
        conn, CHAT, 1, "kurz", "sprache",
        status="fertig", schnittgrund="pause", brainstorm=True,
    )
    html_hoert = rendere()
    assert 'data-zustand="hoert"' in html_hoert

    # 2. denkt: ein Buehnenkarten-Lauf wird markiert (laeuft gerade).
    # ``denkt`` steht in der Prioritaet aus ``cothinker_status.leite_ab``
    # (denkt > transkribiert > hoert > schweigt) VOR ``hoert`` -- das frische
    # Segment aus Schritt 1 ist also weiterhin da und stoert nicht.
    repo.markiere_buehnenkarten_lauf(conn, CHAT, repo._jetzt())
    html_denkt = rendere()
    assert 'data-zustand="denkt"' in html_denkt

    # 3. schweigt: der Lauf ist zu Ende (Markierung geloescht) und das
    # Ergebnis war ein bewusstes Schweigen (keine Karte, nur der Vermerk).
    # Das Segment aus Schritt 1 wird dafuer auf "nicht mehr frisch"
    # zurueckdatiert (Muster wie in tests/test_repo_aufnahme.py und
    # tests/test_web_daten.py: direktes UPDATE von ``empfangen_am``) --
    # ``leite_ab`` liesse sonst weiterhin ``hoert`` gewinnen
    # (``HOERT_FRISCH_S`` = 60 s), weil ein echter Lauf in der Praxis selbst
    # ein paar Sekunden braucht, ein Testlauf aber in Millisekunden durch
    # alle drei Schritte geht. Das bildet denselben zeitlichen Abstand ab,
    # den ein echtes Modell-Gespraech zwischen Aufnahme und Kartenergebnis
    # braucht.
    conn.execute(
        "UPDATE aufnahme SET empfangen_am = '2000-01-01T00:00:00+00:00' WHERE id = ?",
        (segment_id,),
    )
    conn.commit()
    repo.markiere_buehnenkarten_lauf(conn, CHAT, None)
    repo.lege_buehnenkarte_an(conn, CHAT, "", "infomaniak", schweigen=True)
    html_schweigt = rendere()
    assert 'data-zustand="schweigt"' in html_schweigt

    # Der direkte Nachweis, dass ``ladeBuehne()``s Diff-Vergleich im Browser
    # bei jedem der drei Schritte tatsaechlich eine Aenderung erkannt haette:
    # alle drei gerenderten Strings sind paarweise verschieden.
    assert html_hoert != html_denkt
    assert html_denkt != html_schweigt
    assert html_hoert != html_schweigt

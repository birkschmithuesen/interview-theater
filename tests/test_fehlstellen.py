"""Tests fuer das Fehlstellen-Register (06.09.2026).

Gemessen wird hier dreierlei: dass eine leere Gruppe eine kurze, sortierte
Arbeitsliste bekommt, dass eine **vollstaendige Gruppe eine leere Liste**
bekommt (kein "nichts fehlt"), und dass die Liste an ihren zwei
Ausspielorten -- ``/stand`` und Gruppenseite -- aus derselben Funktion kommt.

Kein Netzzugriff, kein Sprachmodell: das Register ist eine reine Leseabfrage
(``fehlstellen.register``), und genau das wird hier mitgeprueft.
"""

import pytest

from interview_theater import (
    befehle, fehlstellen, phasen, repo, szene, web, web_daten,
)

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _interview(conn, chat_id, message_id, transkript, name=None):
    """Ein beendetes Interview mit Material -- der Kopf, wie ihn
    ``aufnahme.stelle_interview_sicher`` anlegt."""
    aufnahme_id = repo.lege_aufnahme_an(
        conn, chat_id, message_id, "lang", "text", status="fertig",
    )
    repo.setze_transkript(conn, aufnahme_id, transkript)
    repo.setze_interview_beendet(conn, aufnahme_id)
    if name:
        repo.setze_aufnahme_name(conn, aufnahme_id, name)
    return aufnahme_id


def _voll(conn, chat_id=1):
    """Eine Gruppe, der nichts mehr fehlt: Begriffe, geprueft, Leitfaden,
    ausgewertetes Interview, Setting, Geschichte, fixierte Figuren mit
    Sprachprofil und eine fertige Szene."""
    for feld, wert in (
        ("begriffe", "Ankommen, Heimat"),
        ("fragen", "Wo fuehlst du dich zu Hause?"),
        ("fragen_weich", "1 - Erzaehl mal, wo du dich zu Hause fuehlst."),
        ("interview_eroeffnung", "Wir machen ein Theaterstueck."),
        ("interview_abschluss", "Danke dir."),
        ("rahmen", "Schulhof, Freitagnachmittag"),
        ("geschichte", "Sie wartet, er kommt nicht."),
        ("figuren_fixiert_am", "2026-09-06T10:00:00+00:00"),
    ):
        repo.setze_arbeitsstand(conn, chat_id, feld, wert)

    aufnahme_id = _interview(conn, chat_id, 10, "Ich bin hier aufgewachsen.")
    repo.speichere_verdichtung(conn, chat_id, aufnahme_id, "Sie erzaehlt.", [])

    repo.setze_figur(conn, chat_id, "Leyla", "Sechzehn, wartet.")
    figur_id = repo.hole_figur(conn, chat_id, "Leyla")["id"]
    repo.setze_figur_quelle(conn, figur_id, aufnahme_id)
    repo.setze_sprachprofil(conn, figur_id, "Kurze Saetze.", ["Gelesen."])

    szene_id = repo.stelle_szene_sicher(conn, chat_id, 1)
    for feld, wert in (
        ("form", "Dialog"), ("ort", "Schulhof"),
        ("was_passiert", "Sie warten."), ("titel", "Warten"),
    ):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, chat_id, szene_id, [figur_id])
    repo.aktualisiere_szene(
        conn, szene_id, "Warten", "Sie warten.", "LEYLA:Gelesen.",
        "Sie warten.", prosa="Sie stehen auf dem Schulhof.",
    )
    return figur_id, szene_id


# --- leere Gruppe ----------------------------------------------------------


def test_leere_gruppe_nennt_die_begriffe_zuerst(conn):
    """Eine Gruppe ohne alles steht in Phase 1 -- oben steht, was JETZT dran
    ist."""
    eintraege = fehlstellen.register(conn, 1)

    assert eintraege
    assert eintraege[0]["phase"] == 1
    assert eintraege[0]["bereich"] == "begriffe"
    assert "Begriffsliste" in eintraege[0]["text"]


def test_leere_gruppe_bleibt_unter_acht_zeilen(conn):
    """``HOECHSTENS`` deckelt: eine Arbeitsliste, die man scrollen muss, ist
    keine."""
    assert len(fehlstellen.register(conn, 1)) <= fehlstellen.HOECHSTENS


def test_ohne_fragen_kommen_einleitungen_und_eroeffnung_nicht_dazu(conn):
    """Drei Zeilen fuer denselben naechsten Schritt sind keine Liste."""
    texte = [e["text"] for e in fehlstellen.register(conn, 1)]

    assert any("Interviewfragen" in t for t in texte)
    assert not any("Eroeffnung" in t for t in texte)


def test_jede_zeile_ist_ein_satz(conn):
    """Deutsch, lesbar, ein Satz -- kein Feldname."""
    for eintrag in fehlstellen.register(conn, 1):
        assert eintrag["text"].endswith((".", "?"))
        assert eintrag["text"][0].isupper()


# --- vollstaendige Gruppe --------------------------------------------------


def test_vollstaendige_gruppe_liefert_leere_liste(conn):
    """Der wichtigste Fall: **kein** "nichts fehlt", sondern gar nichts."""
    _voll(conn)
    repo.setze_phase(conn, 1, 7)

    assert fehlstellen.register(conn, 1) == []
    assert fehlstellen.zeilen(conn, 1) == []


def test_vollstaendige_gruppe_ohne_abschnitt_in_stand(conn, tg):
    """``/stand`` schreibt die Ueberschrift nur, wenn darunter etwas steht."""
    _voll(conn)
    repo.setze_phase(conn, 1, 7)

    befehle._befehl_stand(conn, tg, 1)

    text = "\n".join(t for _, t in tg.gesendet)
    assert fehlstellen.UEBERSCHRIFT not in text


def test_vollstaendige_gruppe_ohne_abschnitt_auf_der_seite(conn):
    """Dieselbe Regel im Web: kein leerer Abschnitt."""
    _voll(conn)
    repo.setze_phase(conn, 1, 7)
    token = repo.stelle_web_token_sicher(conn, 1)

    daten = web_daten.gruppe_nach_token(conn, token)

    assert daten["fehlstellen"] == []
    assert fehlstellen.UEBERSCHRIFT not in web.gruppe_html(daten)


# --- mitten drin -----------------------------------------------------------


def test_mitten_drin_stellt_die_aktuelle_phase_nach_oben(conn):
    """Eine Gruppe in Phase 4: die Figuren stehen oben, der Rueckstand aus
    Phase 2 darunter, die Szenentexte ganz unten."""
    _voll(conn)
    repo.setze_arbeitsstand(conn, 1, "interview_abschluss", None)
    repo.setze_arbeitsstand(conn, 1, "figuren_fixiert_am", None)
    repo.setze_phase(conn, 1, 4)

    phasenfolge = [e["phase"] for e in fehlstellen.register(conn, 1)]

    assert phasenfolge[0] == 4
    assert 2 in phasenfolge
    assert phasenfolge.index(4) < phasenfolge.index(2)


def test_rueckstand_steht_vor_dem_kommenden(conn):
    """Was blockiert, steht vor dem, was spaeter kommt."""
    eintraege = [
        {"phase": 7, "text": "spaet"},
        {"phase": 2, "text": "rueckstand"},
        {"phase": 5, "text": "jetzt"},
    ]

    sortiert = fehlstellen.sortiere(eintraege, 5)

    assert [e["text"] for e in sortiert] == ["jetzt", "rueckstand", "spaet"]


def test_unausgewertetes_interview_wird_benannt(conn):
    """Ein beendetes Interview ohne Verdichtung ist eine Fehlstelle -- mit
    der Bezeichnung "Interview N", nie mit dem gespeicherten Namen."""
    _voll(conn)
    _interview(conn, 1, 11, "Noch ein Gespraech.", name="Meryem")
    repo.setze_phase(conn, 1, 3)

    texte = [e["text"] for e in fehlstellen.register(conn, 1)]

    assert any("Interview 2" in t and "nicht ausgewertet" in t for t in texte)
    assert not any("Meryem" in t for t in texte)


def test_figur_ohne_sprachprofil_erst_ab_der_schaerfung(conn):
    """In Phase 4 wird erfunden -- die Frage nach dem Quell-Interview waere
    dort die Ruecklenkung aufs Material (``knoepfe.ebene2_erlaubt``)."""
    _voll(conn)
    repo.setze_figur(conn, 1, "Zeynep", "Sechzehn, zaehlt Stunden.")

    repo.setze_phase(conn, 1, 4)
    in_vier = [e["text"] for e in fehlstellen.register(conn, 1)]
    repo.setze_phase(conn, 1, 5)
    in_fuenf = [e["text"] for e in fehlstellen.register(conn, 1)]

    assert not any("Zeynep" in t and "Interview" in t for t in in_vier)
    assert any("Zeynep" in t and "Interview" in t for t in in_fuenf)


def test_szene_ohne_form_und_ohne_text(conn):
    """Die Form steht fuer sich: sie ist die einzige, die die Gruppe per
    Knopf bestaetigt."""
    _voll(conn)
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", None)
    repo.aktualisiere_szene(conn, szene_id, "Warten", None, "", None,
                            prosa="Sie stehen auf dem Schulhof.")
    repo.setze_phase(conn, 1, 7)

    texte = [e["text"] for e in fehlstellen.register(conn, 1)]

    assert any("keine Form bestaetigt" in t for t in texte)
    assert any("keinen Szenentext" in t for t in texte)


def test_szene_ohne_prosa_meldet_nur_die_geschichte(conn):
    """Solange die Szene nicht einmal erzaehlt ist, sind Form und Ton der
    uebernaechste Schritt."""
    _voll(conn)
    szene_id = repo.stelle_szene_sicher(conn, 1, 2)
    repo.setze_phase(conn, 1, 6)

    texte = [
        e["text"] for e in fehlstellen.register(conn, 1) if e["szene"] == 2
    ]

    assert texte == ["Szene 2 ist noch nicht erzaehlt."]
    assert szene_id  # die Szene existiert, sie hat nur keinen Text


def test_fehlende_pflichtfelder_heissen_wie_im_chat(conn):
    """Dieselben Namen wie in der Sperrmeldung (``szene.FELDNAMEN``)."""
    _voll(conn)
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "ort", None)
    repo.setze_phase(conn, 1, 7)

    texte = [e["text"] for e in fehlstellen.register(conn, 1)]

    assert any(szene.FELDNAMEN["ort"] in t and "fehlt noch" in t for t in texte)


# --- die zwei Ausspielorte -------------------------------------------------


def test_stand_haengt_die_liste_an(conn, tg):
    """``/stand`` bekommt den Abschnitt -- unter dem, was schon dasteht."""
    befehle._befehl_stand(conn, tg, 1)

    text = "\n".join(t for _, t in tg.gesendet)
    assert f"{fehlstellen.UEBERSCHRIFT}:" in text
    assert "- Die Begriffsliste aus dem Plenum steht noch nicht." in text


def test_stand_ruft_kein_modell(conn, tg, monkeypatch):
    """Reine Leseabfrage: ``/stand`` kann daran nicht scheitern."""
    def _nein(*a, **kw):  # pragma: no cover -- soll nie laufen
        raise AssertionError("kein Modellaufruf im Fehlstellen-Register")

    monkeypatch.setattr("interview_theater.llm.LLM.chat", _nein, raising=False)
    befehle._befehl_stand(conn, tg, 1)

    assert tg.gesendet


def test_gruppenseite_zeigt_die_liste(conn):
    """Dieselben Saetze auf der Gruppenseite."""
    token = repo.stelle_web_token_sicher(conn, 1)

    daten = web_daten.gruppe_nach_token(conn, token)
    seite = web.gruppe_html(daten)

    assert fehlstellen.UEBERSCHRIFT in seite
    assert "Die Begriffsliste aus dem Plenum steht noch nicht." in seite


def test_web_und_chat_zeigen_dieselbe_liste(conn):
    """Ein Zusammenbau, zwei Aufrufer -- wie beim Leitfaden."""
    _voll(conn)
    repo.setze_arbeitsstand(conn, 1, "geschichte", None)
    repo.setze_phase(conn, 1, 4)
    token = repo.stelle_web_token_sicher(conn, 1)

    ueber_repo = [e["text"] for e in fehlstellen.register(conn, 1)]
    ueber_web = [e["text"] for e in web_daten.fehlstellen(conn, 1)]

    assert ueber_web == ueber_repo
    assert token


def test_kein_transkript_und_kein_nachrichtentext_im_html(conn):
    """Die harte Grenze: auf der Gruppenseite steht kein Interviewtext, auch
    nicht ueber die Fehlstellen."""
    _voll(conn)
    _interview(
        conn, 1, 12, "Mein Vater ist 1998 aus Diyarbakir gekommen.",
        name="Meryem",
    )
    token = repo.stelle_web_token_sicher(conn, 1)

    seite = web.gruppe_html(web_daten.gruppe_nach_token(conn, token))

    assert "Diyarbakir" not in seite
    assert "Meryem" not in seite


def test_phase_ohne_gesetzten_wert_gilt_wie_eins(conn):
    """``phase IS NULL`` heisst Phase 1 -- auf beiden Seiten dieselbe
    Anzeigeregel."""
    assert repo.hole_phase(conn, 1) is None

    assert phasen.aktuelle(conn, 1) == phasen.ERSTE
    assert fehlstellen.register(conn, 1)[0]["phase"] == 1
    assert web_daten.fehlstellen(conn, 1)[0]["phase"] == 1

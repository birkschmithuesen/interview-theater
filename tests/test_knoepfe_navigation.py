"""Tests fuer die Knopf-Navigation der Phasen nach dem Interview
(05.09.2026 abends, Birk).

Gemessen wird hier, was die Navigation ueberhaupt rechtfertigt: dass eine
Gruppe im Raum mit dem Daumen durch Phase 4 und 5 kommt, ohne einen Satz
tippen zu muessen -- und dass an jeder Station etwas in der Datenbank landet.

Kein Netzzugriff, kein Sprachmodell: die Modellwege (``ablauf.starte_auftrag``)
werden mit ``monkeypatch`` aufgezeichnet statt ausgefuehrt. Genau das ist auch
die Zusage, die hier geprueft wird -- **kein Modellaufruf in einem
Knopf-Handler** (AGENTS.md, Zusage 2 in ``knoepfe.py``).
"""

import pytest

from interview_theater import ablauf, knoepfe, phasen, repo

from test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def auftraege(monkeypatch):
    """Zeichnet auf, welche Anweisungen an einen eigenen Thread gegangen
    waeren -- statt ein Modell zu rufen."""
    gesammelt = []

    def _fake(conn, tg_, klm, e, chat_id, anweisung, arbeitszeile=None):
        gesammelt.append(anweisung)
        return object()

    monkeypatch.setattr(ablauf, "starte_auftrag", _fake)
    return gesammelt


def _knopf(tg, beschriftung):
    """Die ``callback_data`` des Knopfes mit dieser Beschriftung aus der
    zuletzt verschickten Leiste."""
    for _, _, leiste in reversed(tg.knoepfe):
        for text, daten in leiste:
            if text == beschriftung:
                return daten
    raise AssertionError(f"kein Knopf {beschriftung!r}, gesehen: {tg.knoepfe}")


def _druecke(conn, tg, einst, beschriftung, klm=None):
    knoepfe.behandle(conn, tg, klm, einst, _druck(_knopf(tg, beschriftung)))


def _interview(conn, name="Interview 1"):
    """Ein beendetes Interview mit Transkript -- Material fuer die
    Figuren-Zuordnung."""
    kopf_id = repo.lege_interview_an(conn, 1)
    repo.setze_transkript(conn, kopf_id, "Wir haben zusammen gearbeitet, jeden Tag.")
    repo.setze_status(conn, kopf_id, "fertig")
    repo.setze_interview_beendet(conn, kopf_id)
    return kopf_id


# --- Die Grundleiste ------------------------------------------------------


def test_jede_vorschlagsnachricht_traegt_dieselben_drei_knoepfe(conn, tg):
    """Die Zusage in einem Test: drei Knoepfe, immer dieselben, immer unten."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")

    assert [b for b, _ in tg.knoepfe[-1][2]][-3:] == [
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
    ]


def test_gefaellt_uns_weiter_speichert_und_fragt_nach_ergaenzungen(conn, tg, einst):
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat"
    assert any(
        "hinzufuegen" in t for _, t in tg.gesendet
    ), "die Frage nach Ergaenzungen fehlt"
    assert tg.entfernt, "die Tastatur ist weg"


def test_nach_passt_aber_anders_kommt_die_leiste_wieder_und_ueberschreibt(
    conn, tg, einst
):
    """Der Kern des zweiten Knopfes: gespeichert ist gespeichert, aber die
    Gruppe kommt an den Wert wieder heran -- sonst waere die Aenderung eine
    Sackgasse."""
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat")
    _druecke(conn, tg, einst, "Passt, aber anders")
    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat"

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG BEGRIFFE:\nHeimat, Arbeit")
    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert repo.hole_arbeitsstand(conn, 1)["begriffe"] == "Heimat, Arbeit"


# --- Kernthema in zwei Stufen ---------------------------------------------


def test_richtungen_werden_zu_knoepfen(conn, tg):
    phasen.setze(conn, 1, 4, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "Woran wollt ihr entlang?\n\nVORSCHLAG RICHTUNGEN:\n"
        "Arbeit, die niemand sieht\nZwischen zwei Sprachen\nWas bleibt",
    )

    beschriftungen = [b for b, _ in tg.knoepfe[-1][2]]
    assert beschriftungen[:3] == [
        "Arbeit, die niemand sieht", "Zwischen zwei Sprachen", "Was bleibt",
    ]
    # Eine Richtung ist noch kein Kernthema -- die Grundleiste haengt hier
    # nicht dran, nur der Weg an der Liste vorbei.
    assert beschriftungen[-1] == "Eigene Idee"


def test_eine_richtung_setzt_kein_kernthema_sondern_die_richtung(
    conn, tg, einst, auftraege
):
    """Stufe 1: eine Richtung ist eine Zwischenentscheidung. Sie darf das
    Kernthema-Feld NICHT fuellen -- eine halbe Festlegung im Arbeitsstand ist
    schlimmer als gar keine."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG RICHTUNGEN:\nArbeit, die niemand sieht\nWas bleibt"
    )

    _druecke(conn, tg, einst, "Arbeit, die niemand sieht", klm=object())

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["kernthema_richtung"] == "Arbeit, die niemand sieht"
    assert not stand["kernthema"]


def test_eine_richtung_loest_einen_gespraechszug_im_thread_aus(
    conn, tg, einst, auftraege
):
    """Zusage 2: der Handler ruft kein Modell -- er gibt einen Auftrag ab."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG RICHTUNGEN:\nArbeit, die niemand sieht"
    )

    _druecke(conn, tg, einst, "Arbeit, die niemand sieht", klm=object())

    assert len(auftraege) == 1
    assert "Arbeit, die niemand sieht" in auftraege[0]
    assert "VORSCHLAG KERNTHEMA:" in auftraege[0]


def test_stufe_zwei_speichert_das_kernthema(conn, tg, einst):
    phasen.setze(conn, 1, 4, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "VORSCHLAG KERNTHEMA:\nArbeit, die niemand sieht\nZwei Sprachen im Kopf",
    )
    _druecke(conn, tg, einst, "Zwei Sprachen im Kopf")

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Zwei Sprachen im Kopf"


def test_bei_stufe_zwei_speichert_passt_aber_anders_den_ersten_vorschlag(
    conn, tg, einst
):
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG KERNTHEMA:\nArbeit, die niemand sieht\nZwei Sprachen"
    )

    _druecke(conn, tg, einst, "Passt, aber anders")

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Arbeit, die niemand sieht"


# --- Figuren, Ebene 1 -----------------------------------------------------

_LISTE = (
    "VORSCHLAG FIGUREN:\n"
    "Mira — Naeherin, will gefragt werden — Interview 1\n"
    "Pal — Taxifahrer, haelt an seiner Route fest — Interview 1"
)


def _ebene1(conn, tg):
    """Der Stand vor der Figurenliste (Umbau 05.09.2026 nachts): in Phase 4
    steht zuerst das SETTING (``rahmen``) offen, danach die Figuren."""
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    knoepfe.sende_mit_speicherleiste(conn, tg, 1, _LISTE)


def test_die_figurenliste_traegt_anzahl_und_namen(conn, tg):
    _ebene1(conn, tg)

    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "Anzahl aendern", "Namen aendern",
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
    ]


def test_die_liste_ist_ein_entwurf_und_legt_noch_keine_figuren_an(conn, tg):
    """Sonst staenden nach drei Runden Namensaenderung neun Figuren in der
    Datenbank, von denen die Gruppe sechs nie gewollt hat."""
    _ebene1(conn, tg)

    assert repo.figuren(conn, 1) == []
    assert "Mira" in repo.hole_arbeitsstand(conn, 1)["figuren_entwurf"]


def test_anzahl_aendern_bietet_eins_bis_sechs_und_andere_zahl(conn, tg, einst):
    _ebene1(conn, tg)

    _druecke(conn, tg, einst, "Anzahl aendern")

    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "1", "2", "3", "4", "5", "6", "Andere Zahl",
    ]


def test_eine_anzahl_fordert_eine_neue_liste_im_thread_an(conn, tg, einst, auftraege):
    _ebene1(conn, tg)
    _druecke(conn, tg, einst, "Anzahl aendern")

    _druecke(conn, tg, einst, "4", klm=object())

    assert len(auftraege) == 1
    assert "genau 4 Figuren" in auftraege[0]


def test_namen_aendern_bietet_einen_knopf_je_figur(conn, tg, einst):
    _ebene1(conn, tg)

    _druecke(conn, tg, einst, "Namen aendern")

    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Figur 1: Mira", "Figur 2: Pal"]


def test_ein_namensvorschlag_ersetzt_nur_den_namen_in_der_zeile(
    conn, tg, einst, auftraege
):
    """Satz und Interview bleiben stehen -- sie sind die Arbeit der Gruppe,
    der Name war nur ihre Beschriftung."""
    _ebene1(conn, tg)
    _druecke(conn, tg, einst, "Namen aendern")
    _druecke(conn, tg, einst, "Figur 1: Mira", klm=object())
    assert "VORSCHLAG NAMEN:" in auftraege[0]

    knoepfe.sende_mit_speicherleiste(conn, tg, 1, "VORSCHLAG NAMEN:\nAmina\nNour\nSelin")
    _druecke(conn, tg, einst, "Amina")

    entwurf = repo.hole_arbeitsstand(conn, 1)["figuren_entwurf"]
    assert entwurf.splitlines()[0] == (
        "Amina — Naeherin, will gefragt werden — Interview 1"
    )
    assert "Pal" in entwurf


# --- Figuren, Ebene 2 -----------------------------------------------------
#
# Ebene 2 (Figur fuer Figur: Interview, Sprachduktus, Entfernen) laeuft seit
# dem Umbau vom 05.09.2026 nachts erst in der **Schaerfung** (Phase 6): in 4
# wird erfunden, und die Frage nach dem Interview waere dort die Ruecklenkung
# aufs Material, die der Umbau vermeidet.


def _ebene2(conn, tg, einst):
    """Ebene 1 abnehmen, in die Schaerfung wechseln, Ebene 2 starten."""
    _ebene1(conn, tg)
    _druecke(conn, tg, einst, "Gefaellt uns, weiter")
    phasen.setze(conn, 1, 6, "befehl")
    knoepfe.stelle_figur_vor(conn, tg, None, einst, 1)


def test_gefaellt_uns_weiter_legt_alle_figuren_an_und_startet_ebene_zwei(
    conn, tg, einst
):
    kopf_id = _interview(conn)
    _ebene2(conn, tg, einst)

    namen = [f["name"] for f in repo.figuren(conn, 1)]
    assert namen == ["Mira", "Pal"]
    # Die Zuordnung aus "Interview 1" ist mitgekommen.
    assert repo.hole_figur(conn, 1, "Mira")["quelle_aufnahme_id"] == kopf_id
    # Und die erste Figur steht schon zur Abnahme da.
    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "Passt", "Anderes Interview", "Anderer Duktus", "Entfernen", "Eigene Idee",
    ]
    assert "Mira" in tg.knoepfe[-1][1]


def test_passt_geht_zur_naechsten_figur_und_dann_zur_fixierung(conn, tg, einst):
    _interview(conn)
    _ebene2(conn, tg, einst)

    _druecke(conn, tg, einst, "Passt")
    assert "Pal" in tg.knoepfe[-1][1]

    _druecke(conn, tg, einst, "Passt")

    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["figuren_fixiert_am"], "die Liste gilt als fixiert"
    assert any("Figuren stehen" in t for _, t in tg.gesendet)


def test_die_fixierung_leitet_ohne_phasenwechsel_zur_geschichte(conn, tg, einst):
    """Seit dem 06.09.2026 (Birk) steht hier KEIN Phasenknopf mehr: Setting,
    Figuren und Geschichte sind eine Station, und der Bot geht mit einer
    kurzen Zeile und der offenen Frage weiter."""
    _interview(conn)
    _ebene1(conn, tg)
    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    # Ebene 2 (Figur fuer Figur mit Interview) laeuft seit dem Umbau erst in
    # der Schaerfung -- in Phase 4 ist die Liste mit Ebene 1 fixiert.
    assert repo.hole_arbeitsstand(conn, 1)["figuren_fixiert_am"]
    text, leiste = tg.knoepfe[-1][1], tg.knoepfe[-1][2]
    assert "Was soll passieren, wie soll es ausgehen?" in text
    assert not any(b.startswith("Weiter zu") for b, _ in leiste), text
    assert [b for b, _ in leiste] == ["Ja, wir zuerst", "Schlag du vor"]


def test_eine_einzige_figur_genuegt(conn, tg, einst):
    """Ein Monolog ist ein Stueck -- die alte Schwelle "zwei Figuren" sperrte
    genau diese Gruppe aus."""
    _interview(conn)
    phasen.setze(conn, 1, 4, "befehl")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Eine Nacht im Treppenhaus")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG FIGUREN:\nMira — Naeherin — Interview 1"
    )
    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert repo.hole_arbeitsstand(conn, 1)["figuren_fixiert_am"]
    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Mira"]


def test_anderes_interview_bietet_je_interview_einen_knopf_und_setzt_die_quelle(
    conn, tg, einst
):
    erstes = _interview(conn)
    zweites = _interview(conn)
    _ebene2(conn, tg, einst)
    assert repo.hole_figur(conn, 1, "Mira")["quelle_aufnahme_id"] == erstes

    _druecke(conn, tg, einst, "Anderes Interview")
    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Interview 1", "Interview 2"]

    _druecke(conn, tg, einst, "Interview 2", klm=object())

    figur = repo.hole_figur(conn, 1, "Mira")
    assert figur["quelle_aufnahme_id"] == zweites
    # Die Figur ist wieder offen und wird erneut vorgestellt.
    assert not figur["geprueft_am"]
    assert "Mira" in tg.knoepfe[-1][1]


def test_anderer_duktus_holt_vorschlaege_im_thread_und_speichert_die_wahl(
    conn, tg, einst, auftraege
):
    _interview(conn)
    _ebene2(conn, tg, einst)

    _druecke(conn, tg, einst, "Anderer Duktus", klm=object())
    assert "VORSCHLAG DUKTUS:" in auftraege[-1]
    assert "Mira" in auftraege[-1]

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG DUKTUS:\nKurze Saetze, viele Abbrueche\nLangsam, ruhig"
    )
    _druecke(conn, tg, einst, "Langsam, ruhig")

    assert repo.hole_figur(conn, 1, "Mira")["sprachprofil"] == "Langsam, ruhig"


def test_entfernen_loescht_weich_und_geht_zur_naechsten(conn, tg, einst):
    _interview(conn)
    _ebene2(conn, tg, einst)

    _druecke(conn, tg, einst, "Entfernen")

    assert [f["name"] for f in repo.figuren(conn, 1)] == ["Pal"]
    assert "Pal" in tg.knoepfe[-1][1]


# --- Phasenknoepfe, Format, proaktive Frage -------------------------------


@pytest.mark.parametrize(
    "nummer,text",
    [
        (2, "Weiter zu Fragen"),
        (3, "Weiter zu Interviews"),
        (4, "Weiter zu Setting, Figuren & Geschichte"),
        (5, "Weiter zu Schaerfung"),
        (6, "Weiter zu Szenen als Geschichte"),
        (7, "Weiter zu Feinschliff"),
    ],
)
def test_phasenknoepfe_heissen_nach_inhalt_nie_nach_nummer(conn, tg, nummer, text):
    """Eine Gruppe, die zum ersten Mal mit dem Bot arbeitet, kennt die
    Nummerierung nicht und soll sie nicht lernen muessen."""
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", nummer)

    beschriftung = tg.knoepfe[-1][2][0][0]
    assert beschriftung == text
    assert not any(z.isdigit() for z in beschriftung)


def test_der_phasenknopf_fragt_zuerst_die_gruppe(conn, tg, einst):
    """Proaktiv, aber nicht vorlaut: beim Eintritt in eine Phase fragt der
    Bot, ob die Gruppe selbst schon Ideen hat."""
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 4)

    knoepfe.behandle(
        conn, tg, None, einst,
        _druck(_knopf(tg, "Weiter zu Setting, Figuren & Geschichte")),
    )

    # Seit dem 06.09.2026 steht der Phasenrahmen in derselben Nachricht
    # darueber: Kopfzeile, Einleitung, Checkliste, dann die Frage.
    assert tg.gesendet[-1][1].startswith(
        "\u25b6\ufe0f Phase 4 von 7 \u00b7 Setting, Figuren & Geschichte"
    )
    assert tg.gesendet[-1][1].endswith(knoepfe._TEXT_PROAKTIV)
    assert [b for b, _ in tg.knoepfe[-1][2]] == ["Ja, wir zuerst", "Schlag du vor"]


def test_wir_zuerst_ruft_kein_modell(conn, tg, einst, auftraege):
    knoepfe.biete_proaktiv(conn, tg, 1, 4)

    _druecke(conn, tg, einst, "Ja, wir zuerst", klm=object())

    assert auftraege == []
    assert tg.gesendet[-1][1] == knoepfe._TEXT_WIR_ZUERST


def test_schlag_du_vor_gibt_einen_auftrag_je_phase_ab(conn, tg, einst, auftraege):
    knoepfe.biete_proaktiv(conn, tg, 1, 4)

    _druecke(conn, tg, einst, "Schlag du vor", klm=object())

    assert len(auftraege) == 1
    # Phase 4 schlaegt seit dem Umbau das SETTING vor, nicht mehr
    # Kernthema-Richtungen -- und ausdruecklich nicht aus dem Material.
    assert "VORSCHLAG RAHMEN:" in auftraege[0]
    assert "NICHT aus Interviews" in auftraege[0]


def test_der_schritt_nach_phase_fuenf_setzt_kein_format(conn, tg, einst):
    """Die Formatfrage ist komplett raus (Birk, 05.09.2026 abends): der
    Phasenknopf setzt nichts mehr, er fuehrt nur weiter."""
    knoepfe.biete_phase(conn, tg, 1, "Weiter?", 5)

    knoepfe.behandle(conn, tg, None, einst, _druck(_knopf(tg, "Weiter zu Schaerfung")))

    assert not (repo.hole_arbeitsstand(conn, 1)["format"] or "")
    assert not any("Urban Dance" in t for _, t in tg.gesendet)


# --- Figurenvorstellung: Belegzitate und Reihenfolge ----------------------


def test_vorstellung_zeigt_die_belegzitate(conn, tg, einst):
    """Der Duktus ist eine Behauptung, die Zitate sind der Beleg -- und genau
    die fehlten am 05.09.2026 in der Vorstellung."""
    kopf_id = _interview(conn)
    repo.setze_figur(conn, 1, "Amina", "will gefragt werden")
    figur = repo.hole_figur(conn, 1, "Amina")
    repo.setze_figur_quelle(conn, figur["id"], kopf_id)
    repo.setze_sprachprofil(
        conn, figur["id"], "Kurze Saetze, bricht ab",
        ["Wir haben zusammen gearbeitet.", "Jeden Tag, halt."],
    )

    text = knoepfe._figurenvorstellung(
        conn, 1, repo.hole_figur(conn, 1, "Amina")
    )

    assert "Sprachduktus: Kurze Saetze, bricht ab" in text
    assert knoepfe._TEXT_ZITATE_VORSPANN in text
    assert "– Wir haben zusammen gearbeitet." in text
    assert "– Jeden Tag, halt." in text


def test_vorstellung_kommt_erst_nach_dem_sprachprofil(conn, tg, einst, monkeypatch):
    """Vorher ging die Vorstellung SOFORT raus, mit \"Sprachduktus: entsteht
    gerade.\" -- und die fertige Fassung kam nie nach. Jetzt: erst eine Zeile,
    was gerade passiert, die Knopfleiste erst nach dem Lauf."""
    from interview_theater import sprachprofil

    kopf_id = _interview(conn)
    repo.setze_figur(conn, 1, "Amina", "will gefragt werden")
    figur = repo.hole_figur(conn, 1, "Amina")
    repo.setze_figur_quelle(conn, figur["id"], kopf_id)
    figur_id = figur["id"]

    def _fake_starte(conn_, tg_, klm_, e_, chat_id_, ids, nachbereitung=None):
        _fake_starte.nachbereitung = nachbereitung
        return object()

    monkeypatch.setattr(sprachprofil, "starte", _fake_starte)
    phasen.setze(conn, 1, 6, "befehl")

    knoepfe.stelle_figur_vor(conn, tg, object(), einst, 1)

    # Vor dem Thread-Ende: nur die Ankuendigung, keine Knopfleiste.
    assert "Amina" in tg.gesendet[-1][1]
    assert "Interview 1" in tg.gesendet[-1][1]
    assert tg.knoepfe == []

    # Der Lauf ist durch, das Profil steht -- jetzt kommt die Vorstellung.
    repo.setze_sprachprofil(
        conn, figur_id, "Kurze Saetze", ["Wir haben zusammen gearbeitet."]
    )
    _fake_starte.nachbereitung()

    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "Passt", "Anderes Interview", "Anderer Duktus", "Entfernen", "Eigene Idee",
    ]
    assert "– Wir haben zusammen gearbeitet." in tg.knoepfe[-1][1]


def test_ohne_belegtes_zitat_kommt_die_vorstellung_trotzdem(
    conn, tg, einst, monkeypatch
):
    """Scheitert das Profil (kein Zitat im Transkript belegbar), darf die
    Gruppe nicht ohne Knopfleiste dastehen -- sie bekommt den Hinweis aus
    ``sprachprofil._TEXT_KEIN_ZITAT`` und kann ein anderes Interview nennen."""
    from interview_theater import sprachprofil

    kopf_id = _interview(conn)
    repo.setze_figur(conn, 1, "Amina", "will gefragt werden")
    figur = repo.hole_figur(conn, 1, "Amina")
    repo.setze_figur_quelle(conn, figur["id"], kopf_id)

    def _fake_starte(conn_, tg_, klm_, e_, chat_id_, ids, nachbereitung=None):
        _fake_starte.nachbereitung = nachbereitung
        return object()

    monkeypatch.setattr(sprachprofil, "starte", _fake_starte)
    phasen.setze(conn, 1, 6, "befehl")

    knoepfe.stelle_figur_vor(conn, tg, object(), einst, 1)
    _fake_starte.nachbereitung()

    text = tg.knoepfe[-1][1]
    assert sprachprofil._TEXT_KEIN_ZITAT.format(name="Amina") in text
    assert knoepfe._TEXT_DUKTUS_FEHLT not in text
    assert [b for b, _ in tg.knoepfe[-1][2]][0] == "Passt"


# --- Stufe 3: die Kernfrage (05.09.2026 abends) ---------------------------


def test_nach_dem_kernthema_kommt_die_kernfrage_im_thread(conn, tg, einst, auftraege):
    """Der Wendepunkt der Phase: das gewaehlte Kernthema wird zur dramatischen
    Frage geschaerft -- als Gespraechszug im Thread, kein Modellaufruf im
    Handler (Zusage 2)."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG KERNTHEMA:\nArbeit, die niemand sieht"
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter", klm=object())

    assert repo.hole_arbeitsstand(conn, 1)["kernthema"] == "Arbeit, die niemand sieht"
    assert len(auftraege) == 1
    assert "VORSCHLAG KERNFRAGE:" in auftraege[0]
    assert "Arbeit, die niemand sieht" in auftraege[0]


def test_das_setting_traegt_die_grundleiste_und_wird_gespeichert(conn, tg, einst):
    """Der Ping-Pong der Phase 4: der Setting-Vorschlag traegt die drei
    Knoepfe, \"Gefaellt uns, weiter\" schreibt ``rahmen``."""
    phasen.setze(conn, 1, 4, "befehl")

    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1,
        "Wo spielt es?\n\nVORSCHLAG RAHMEN:\nEine Nacht im Treppenhaus\n"
        "Ein Kiosk am Morgen",
    )
    assert [b for b, _ in tg.knoepfe[-1][2]][-3:] == [
        "Eigene Idee", "Passt, aber anders", "Gefaellt uns, weiter",
    ]

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert repo.hole_arbeitsstand(conn, 1)["rahmen"] == "Eine Nacht im Treppenhaus"


def test_nach_dem_setting_kommt_die_frage_nach_der_figurenanzahl(conn, tg, einst):
    """Die Kette der Phase 4: steht das Setting, kommt sofort die Frage nach
    der Figurenanzahl -- deterministisch, ohne Modellaufruf."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.sende_mit_speicherleiste(
        conn, tg, 1, "VORSCHLAG RAHMEN:\nEine Nacht im Treppenhaus"
    )

    _druecke(conn, tg, einst, "Gefaellt uns, weiter")

    assert [b for b, _ in tg.knoepfe[-1][2]] == [
        "1", "2", "3", "4", "5", "6", "Andere Zahl",
    ]
    assert "Wie viele Figuren" in tg.knoepfe[-1][1]


# --- Die freie Figurenanzahl ----------------------------------------------


def test_eine_gewaehlte_zahl_speichert_und_fordert_genau_so_viele_an(
    conn, tg, einst, auftraege
):
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.biete_figurenanzahl(conn, tg, 1)

    _druecke(conn, tg, einst, "5", klm=object())

    assert repo.hole_arbeitsstand(conn, 1)["figuren_anzahl"] == "5"
    assert "genau 5 Figuren" in auftraege[0]


def test_andere_zahl_liest_die_naechste_nachricht(conn, tg, einst, auftraege):
    """\"Andere Zahl\" schreibt nichts und ruft nichts -- sie merkt sich nur,
    dass die naechste Nachricht die Zahl ist (``ablauf.antworte``)."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.biete_figurenanzahl(conn, tg, 1)

    _druecke(conn, tg, einst, "Andere Zahl", klm=object())
    assert auftraege == []
    assert knoepfe.nimm_figurenanzahl_erwartung(1) is True

    # Was ``ablauf.antworte`` daraus macht:
    knoepfe.uebernimm_figurenanzahl(
        conn, tg, object(), einst, 1, knoepfe._zahl_aus("wir haetten gern 9")
    )

    assert repo.hole_arbeitsstand(conn, 1)["figuren_anzahl"] == "9"
    assert "genau 9 Figuren" in auftraege[0]


def test_die_erwartung_gilt_nur_fuer_eine_nachricht(conn):
    knoepfe.erwarte_figurenanzahl(1)
    assert knoepfe.nimm_figurenanzahl_erwartung(1) is True
    assert knoepfe.nimm_figurenanzahl_erwartung(1) is False


def test_zahlen_ausserhalb_der_grenzen_gelten_nicht(conn):
    assert knoepfe._zahl_aus("4 Figuren bitte") == 4
    assert knoepfe._zahl_aus("vier") == 4
    assert knoepfe._zahl_aus("0") is None
    assert knoepfe._zahl_aus("40") is None
    assert knoepfe._zahl_aus("keine Ahnung") is None


def test_der_figurenvorschlag_ist_frei_erfunden_und_nicht_aus_den_interviews(
    conn, tg, einst, auftraege
):
    """Der Kern des Umbaus, als Text im Auftrag: die Figuren werden frei
    erfunden -- aus Begriffen, Fragen und Setting, ausdruecklich NICHT aus
    den Interviews."""
    phasen.setze(conn, 1, 4, "befehl")
    knoepfe.uebernimm_figurenanzahl(conn, tg, object(), einst, 1, 3)

    anweisung = auftraege[0]
    assert "frei erfunden" in anweisung
    assert "NICHT aus den Interviews" in anweisung
    assert "Setting" in anweisung

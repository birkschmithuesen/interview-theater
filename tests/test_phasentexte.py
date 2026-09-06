"""Der einheitliche Phasenrahmen im Chat (06.09.2026, Birk).

Gemessen wird hier genau das, was den Rahmen ausmacht: dass alle acht
Phasen dieselbe Form haben, dass die Checkliste aus dem Arbeitsstand kommt
(und nicht aus einer Annahme), dass die Abschlussnachricht die Werte
wirklich traegt -- und dass es sie **einmal** gibt, nicht zweimal.
"""

import pytest

from interview_theater import befehle, knoepfe, phasen, phasentexte, repo

from tests.test_knoepfe import TelegramAttrappe, _druck


@pytest.fixture
def tg():
    return TelegramAttrappe()


# --- Eintritt: dieselbe Form fuer alle acht -------------------------------


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_jede_phase_hat_dieselbe_eintrittsform(conn, nummer):
    """Kopfzeile "▶️ Phase N von 8 · Name", eine Einleitung, die
    Checkliste -- acht Mal gleich aufgebaut."""
    text = phasentexte.eintritt(conn, 1, nummer)

    zeilen = text.split("\n\n")
    assert zeilen[0] == f"▶️ Phase {nummer} von 8 · {phasen.kurzname(nummer)}"
    # Phase 8 hat zwei Einleitungen: eine fuer "alle Szenen stehen" und eine
    # fuer den Fall, dass welche fehlen (06.09.2026). Die Fixture hier hat
    # keine Szene, also greift die zweite.
    assert zeilen[1] == phasentexte._einleitung(conn, 1, nummer)
    assert zeilen[2].startswith("Dafuer braucht es: ")


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_jede_einleitung_ist_kurz_und_vollstaendig(nummer):
    """Zwei bis vier Saetze -- ein Rahmen, kein Vortrag. Die Grenze ist
    gemessen an der Medianlaenge der Bot-Antworten (Soll < 700 Zeichen,
    simulation): eine Nachricht, die man ueberliest, ist keine."""
    text = phasentexte.EINLEITUNGEN[nummer]

    assert len(text) <= phasentexte.EINLEITUNG_GRENZE, (nummer, len(text))
    assert 2 <= text.count(".") + text.count("?") + text.count("!") <= 5


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_keine_einleitung_bewirbt_einen_slash_befehl(nummer):
    """AGENTS.md: Slash-Befehle werden nirgends beworben, beworben wird der
    Knopf."""
    assert "/" not in phasentexte.EINLEITUNGEN[nummer]


@pytest.mark.parametrize("nummer", [n for n, _, _ in phasen.PHASEN])
def test_keine_einleitung_nennt_einen_eigennamen(nummer):
    """Dieselbe Anti-Nachplapper-Regel wie fuer die Prompts
    (``tests/test_anweisungen.py``): ein Beispielname aus einem Bot-Text
    kommt als Vorschlag zurueck. Hier zusaetzlich die Du-Form Plural: die
    Gruppe sind junge Frauen zwischen 15 und 18, angesprochen mit "ihr"."""
    import re

    text = phasentexte.EINLEITUNGEN[nummer]
    verboten = re.compile(r"\b(Kessel|Mira|Pola|Pal|Demo|Birk|Hawaii)\b", re.IGNORECASE)
    assert verboten.findall(text) == []
    assert " Sie " not in text


def test_die_checkliste_kommt_aus_dem_arbeitsstand(conn):
    """Nicht geraten: was gespeichert ist, steht mit ✅ da -- auch beim
    Rueckweg in eine Phase, in der schon etwas steht."""
    assert phasentexte.checkliste(conn, 1, 4) == "⬜ Setting  ⬜ Figuren"

    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Wartezimmer, nachmittags")

    assert phasentexte.checkliste(conn, 1, 4) == "✅ Setting  ⬜ Figuren"


def test_der_eintritt_haengt_die_einstiegsknoepfe_darunter(conn, einst, tg):
    """Nichts Neues erfunden: unter der Eintrittsnachricht steht die
    vorhandene Eintritt-Frage mit ihren zwei Knoepfen."""
    knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, 4)

    _, text, leiste = tg.knoepfe[-1]
    assert text.startswith("▶️ Phase 4 von 8 · Setting & Figuren")
    assert text.endswith(knoepfe._TEXT_PROAKTIV)
    assert [b for b, _ in leiste] == ["Ja, wir zuerst", "Schlag du vor"]


def test_der_eintritt_ruft_kein_modell(conn, einst, tg):
    """Zusage 2: kein Modellaufruf im Knopf-Handler. ``klm=None`` reicht --
    ein Aufruf wuerde hier mit AttributeError enden."""
    for nummer, _, _ in phasen.PHASEN:
        if nummer == knoepfe.PHASE_SCHAERFUNG:
            continue  # gibt an einen Thread ab, eigener Test
        knoepfe.eintritt_in_phase(conn, tg, None, einst, 1, nummer)

    assert any(t.startswith("▶️ Phase 8 von 8") for _, t in tg.gesendet)


# --- Abschluss ------------------------------------------------------------


def test_die_abschlussnachricht_traegt_alle_gesetzten_parameter(conn):
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Wartezimmer, nachmittags")
    repo.setze_figur(conn, 1, "Nesrin", "will weg und bleibt")

    text = phasentexte.abschluss(conn, 1, 4)

    assert text.splitlines() == [
        "✅ Phase 4 · Setting & Figuren abgeschlossen",
        "Setting: Ein Wartezimmer, nachmittags",
        "Figuren: Nesrin — will weg und bleibt",
    ]


def test_die_abschlussnachricht_laesst_leere_parameter_weg(conn):
    """Sie kommt in dem Moment, in dem die naechste Phase moeglich wurde --
    eine Zeile "noch offen" darin waere ein Widerspruch in sich."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt, Klingel")

    text = phasentexte.abschluss(conn, 1, 1)

    assert "noch keine" not in text
    assert text.endswith("Begriffe: Warten, Amt, Klingel")


def test_lange_werte_werden_gekuerzt(conn):
    """~120 Zeichen je Wert: der Abschluss ist eine Quittung, keine Ausgabe
    des ganzen Arbeitsstands."""
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Sie warten. " * 40)

    zeilen = dict(phasentexte.parameterzeilen(conn, 1, 5))

    assert len(zeilen["Geschichte"]) <= phasentexte.WERT_GRENZE
    assert zeilen["Geschichte"].endswith("…")


def test_listen_werden_mit_punkt_getrennt(conn):
    """Figuren und Szenen stehen in EINER Zeile, mit ``·`` getrennt -- die
    Parameterzeile ist eine Zeile."""
    repo.setze_figur(conn, 1, "Nesrin", "will weg")
    repo.setze_figur(conn, 1, "Ayla", "bleibt")

    zeilen = dict(phasentexte.parameterzeilen(conn, 1, 4))

    assert zeilen["Figuren"] == "Nesrin — will weg · Ayla — bleibt"


def test_szenen_stehen_als_nummer_titel_form(conn):
    """Die Form nur, wenn sie bestaetigt ist (``szene.form``) -- ein
    Vorschlag ist keine Entscheidung (AGENTS.md, 06.09.2026)."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "titel", "Vor der Tuer")
    repo.setze_szenenfeld(conn, szene_id, "form_vorschlag", "Monolog")

    zeilen = dict(phasentexte.parameterzeilen(conn, 1, 5))
    assert zeilen["Szenen"] == "1 · Vor der Tuer"

    repo.setze_szenenfeld(conn, szene_id, "form", "Dialog")

    zeilen = dict(phasentexte.parameterzeilen(conn, 1, 5))
    assert zeilen["Szenen"] == "1 · Vor der Tuer · Dialog"


# --- Verschmelzung mit der proaktiven Phasenmeldung ------------------------


def test_die_proaktive_meldung_ist_die_abschlussnachricht(conn, tg):
    """Nicht zwei Nachrichten: der Abschluss der fertigen Phase und die
    Frage nach der naechsten stehen zusammen."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt, Klingel")

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True

    _, text, leiste = tg.knoepfe[-1]
    assert text.startswith("✅ Phase 1 · Begriffe abgeschlossen")
    assert "Begriffe: Warten, Amt, Klingel" in text
    assert text.endswith(f"Weiter zu {phasen.knopfbezeichnung(2)}?")
    assert [b for b, _ in leiste] == [
        f"Weiter zu {phasen.knopfbezeichnung(2)}", "Noch etwas aendern",
    ]


def test_keine_doppelsendung_je_stufe(conn, tg):
    """Der Merkposten ``arbeitsstand.phase_angeboten`` gilt weiter: EIN
    Abschluss je Stufe, nicht einer je Zug."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt")

    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is True
    assert knoepfe.biete_phase_proaktiv(conn, tg, 1) is False
    assert len(tg.knoepfe) == 1


def test_abgeschlossen_wird_die_phase_der_gruppe_nicht_das_ziel(conn, tg):
    """``offenes_angebot`` liefert die HOECHSTE moegliche Stufe -- sind
    zwei auf einmal moeglich, darf trotzdem nur die abgeschlossen werden, in
    der die Gruppe wirklich steht."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt")
    repo.setze_arbeitsstand(conn, 1, "fragen", "Worauf wartest du?")
    repo.setze_arbeitsstand(conn, 1, "interview_eroeffnung", "Wir machen Theater.")

    knoepfe.biete_phase_proaktiv(conn, tg, 1)

    _, text, _ = tg.knoepfe[-1]
    assert text.startswith("✅ Phase 1 · Begriffe abgeschlossen")
    assert text.endswith(f"Weiter zu {phasen.knopfbezeichnung(3)}?")


def test_der_weiter_knopf_fuehrt_in_den_phasenrahmen(conn, einst, tg):
    """Die Kette am Stueck: Abschluss -> "Weiter zu ..." -> Eintritt."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt")
    knoepfe.biete_phase_proaktiv(conn, tg, 1)
    weiter = tg.knoepfe[-1][2][0][1]

    knoepfe.behandle(conn, tg, None, einst, _druck(weiter))

    assert phasen.aktuelle(conn, 1) == 2
    assert tg.gesendet[-1][1].startswith("▶️ Phase 2 von 8 · Fragen")


# --- /stand nutzt dieselbe Liste ------------------------------------------


def test_stand_nutzt_dieselben_parameterzeilen(conn, einst, tg):
    """Eine Liste, drei Leser: ``/stand`` baut aus ``phasentexte`` und
    nicht aus einer zweitgepflegten Aufzaehlung."""
    repo.setze_arbeitsstand(conn, 1, "begriffe", "Warten, Amt, Klingel")
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Wartezimmer")

    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada")

    text = tg.gesendet[0][1]
    for nummer, _, _ in phasen.PHASEN:
        for zeile in phasentexte.standzeilen(conn, 1, nummer):
            assert zeile in text, (nummer, zeile)


def test_stand_ruft_weiter_kein_modell(conn, einst, tg):
    """Unveraendert: ``/stand`` beantwortet sich allein aus der Datenbank
    (``klm`` wird gar nicht durchgereicht)."""
    befehle.behandle(conn, tg, einst, 1, "/stand", "Ada", klm=None)

    assert len(tg.gesendet) == 1

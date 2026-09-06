"""Phase 6 als EINE Kurzgeschichte mit freier Abschnittszahl (06.09.2026,
Birk 11:50) -- und die Sperre gegen erfundene Systemzeilen (12:25).

Im Wortlaut: *"Phase 6 soll EINE Kurzgeschichte sein, ein Lauf, und das
Modell waehlt selbst, wie viele Abschnitte es braucht. Die Abschnitte
werden dann die Szenen."* Gemessen wird deshalb genau das: dieselbe
Zerlegung liefert bei vier Ueberschriften vier Szenen und bei sechs
Ueberschriften sechs -- die Zahl steht nirgends im Code und nirgends im
Prompt.

Dazu die zweite Zusage vom selben Vormittag: der Lauf startet **nur** aus
dem Knopf, die USA-Frage steht beim EINTRITT in Phase 6, und ein
Gespraechs-Bot, der "Start frei" sagt, ohne dass ein Lauf laeuft, wird
verworfen.
"""

import dataclasses

import pytest

from interview_theater import (
    ablauf, knoepfe, kurzgeschichte, phasen, repo, szene,
)


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.naechste_message_id = 900

    def sende(self, chat_id, text, **_kw):
        self.gesendet.append((chat_id, text))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def sende_mit_knoepfen(self, chat_id, text, knoepfe_, **_kw):
        self.gesendet.append((chat_id, text))
        self.knoepfe.append((chat_id, text, list(knoepfe_)))
        self.naechste_message_id += 1
        return self.naechste_message_id

    def beantworte_knopf(self, callback_query_id, text=""):
        self.beantwortet.append((callback_query_id, text))

    def entferne_knoepfe(self, chat_id, message_id):
        self.entfernt.append((chat_id, message_id))

    @property
    def texte(self):
        return [t for _, t in self.gesendet]

    @property
    def knopftexte(self):
        return [b[0] for _, _, leiste in self.knoepfe for b in leiste]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture(autouse=True)
def freie_sperren():
    kurzgeschichte._sperren.clear()
    knoepfe._geschichte_notiz_erwartet.clear()
    yield
    kurzgeschichte._sperren.clear()
    knoepfe._geschichte_notiz_erwartet.clear()


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    return {
        "callback_query_id": query_id,
        "data": daten,
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
    }


def _antwort(anzahl: int) -> str:
    """Eine Modellantwort mit genau ``anzahl`` Abschnitten."""
    stuecke = []
    for n in range(1, anzahl + 1):
        stuecke.append(
            f"{n}. Abschnitt Nummer {n}\n"
            f"Zusammenfassung: Im {n}. Abschnitt passiert etwas Bestimmtes.\n\n"
            f"Sie steht am Fenster, zum {n}. Mal an diesem Tag, und wartet.\n"
            f"Draussen faehrt ein Wagen vorbei."
        )
    return "\n\n".join(stuecke)


def _vorbereitet(conn, chat_id=1):
    repo.setze_arbeitsstand(conn, chat_id, "rahmen", "Ort: Treppenhaus, Zeit: nachts")
    repo.setze_arbeitsstand(conn, chat_id, "geschichte", "Sie geht, er bleibt.")
    repo.setze_figur(conn, chat_id, "Maria", "Naeherin")


# --- (a) Zerlegung und Szenenanlage ------------------------------------


@pytest.mark.parametrize("anzahl", [3, 4, 6, 7])
def test_zerlegung_liefert_genau_die_abschnitte_des_modells(anzahl):
    """Die Zahl der Abschnitte kommt aus der Antwort, nicht aus dem Code."""
    abschnitte = kurzgeschichte.zerlege(_antwort(anzahl))
    assert len(abschnitte) == anzahl
    titel, fassung, prosa = abschnitte[0]
    assert titel == "Abschnitt Nummer 1"
    assert fassung.startswith("Im 1. Abschnitt")
    assert "Sie steht am Fenster" in prosa
    assert "Zusammenfassung:" not in prosa


def test_zerlegung_nimmt_markdown_ueberschriften():
    text = (
        "## 1. Der Anfang\nZusammenfassung: Es faengt an.\n\nEin Satz.\n\n"
        "ABSCHNITT 2: Das Ende\nZusammenfassung: Es hoert auf.\n\nNoch ein Satz."
    )
    abschnitte = kurzgeschichte.zerlege(text)
    assert [a[0] for a in abschnitte] == ["Der Anfang", "Das Ende"]


def test_zerlegung_wirft_ueberschrift_ohne_text_weg():
    text = "1. Leer\nZusammenfassung: nichts\n\n2. Voll\nZusammenfassung: was\n\nEin Satz."
    assert [a[0] for a in kurzgeschichte.zerlege(text)] == ["Voll"]


@pytest.mark.parametrize("anzahl", [4, 6])
def test_abschnitte_werden_szenen(conn, anzahl):
    """Vier Abschnitte -> vier Szenen, sechs -> sechs; Ort aus dem Setting,
    ``form`` bleibt leer (die entscheidet der Feinschliff)."""
    _vorbereitet(conn)
    nummern = kurzgeschichte.lege_szenen_an(
        conn, 1, kurzgeschichte.zerlege(_antwort(anzahl))
    )
    assert nummern == list(range(1, anzahl + 1))
    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == anzahl
    for zeile in szenen:
        assert (zeile["ort"] or "") == "Treppenhaus"
        assert (zeile["zeit"] or "") == "nachts"
        assert not (zeile["form"] or "")
        assert (zeile["prosa"] or "").strip()
        assert (zeile["was_passiert"] or "").strip()
    assert szenen[0]["titel"] == "Abschnitt Nummer 1"


def test_neue_geschichte_ersetzt_die_alte_folge_nicht(conn):
    """Der zweite Prosa-Lauf loescht keine Szene (06.09.2026, Analyse
    Abschnitt B): drei neue Abschnitte aktualisieren 1-3, die Szenen 4-6
    bleiben stehen."""
    _vorbereitet(conn)
    kurzgeschichte.lege_szenen_an(conn, 1, kurzgeschichte.zerlege(_antwort(6)))
    vorher = {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, 1)}
    kurzgeschichte.lege_szenen_an(conn, 1, kurzgeschichte.zerlege(_antwort(3)))
    szenen = repo.hole_szenen(conn, 1)
    assert [s["nummer"] for s in szenen] == [1, 2, 3, 4, 5, 6]
    assert {s["nummer"]: s["id"] for s in szenen} == vorher


def test_journal_haelt_die_herkunft_fest(conn):
    _vorbereitet(conn)
    kurzgeschichte.lege_szenen_an(conn, 1, kurzgeschichte.zerlege(_antwort(5)))
    eintraege = [z["text"] for z in repo.journal(conn, 1)]
    assert any("Kurzgeschichte" in t and "5" in t for t in eintraege)


# --- (a) Der Prompt -----------------------------------------------------


def test_prompt_ohne_theatermasse_und_ohne_szenenzahl():
    """Keine Dialoglaengen, keine Regie-Prozente, keine Zahl an Abschnitten."""
    system = kurzgeschichte.systemanweisung()
    # Die Zahlen des Sprechtheaters (Herkules-Mass) und die Regie-Prozente
    # haben hier nichts zu suchen -- der Auftrag ist eine Geschichte.
    for verboten in ("700", "1500", "80 %", "20 %", "jede dritte Replik"):
        assert verboten not in system, verboten
    assert "Abschnitte selbst" in system
    assert "Zusammenfassung" in system


def test_prompt_traegt_prosaregeln_und_tells():
    system = kurzgeschichte.systemanweisung()
    assert "erzaehlende Prosa" in system
    assert "dritte Person" in system


def test_nutzertext_traegt_setting_figuren_und_sprachstil(conn):
    _vorbereitet(conn)
    repo.setze_figur(conn, 1, "Jonas", "Nachbar")
    for figur in repo.figuren(conn, 1):
        if figur["name"] == "Jonas":
            repo.setze_figur_sprachstil(conn, figur["id"], "Kurze Saetze, viel Pause")
    nutzer = kurzgeschichte.baue_nutzertext(conn, 1)
    assert "Treppenhaus" in nutzer
    assert "Jonas" in nutzer
    assert "Kurze Saetze" in nutzer


def test_regienotiz_geht_in_den_naechsten_lauf(conn):
    _vorbereitet(conn)
    nutzer = kurzgeschichte.baue_nutzertext(conn, 1, "Mehr Konflikt am Schluss")
    assert "Mehr Konflikt am Schluss" in nutzer


class LLMAttrappe:
    def __init__(self, antwort):
        self._antwort = antwort
        self.gesehen = {}

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None):
        self.gesehen = {"system": system, "nutzer": nutzer, "art": art}
        return self._antwort


@pytest.mark.parametrize("anzahl", [4, 6])
def test_ein_lauf_legt_genau_die_abschnitte_als_szenen_an(conn, tg, einst, anzahl):
    """Der ganze Weg: ein Lauf, N Abschnitte, N Szenen -- und im Chat steht
    die Geschichte abschnittsweise mit EINER Knopfleiste darunter."""
    _vorbereitet(conn)
    klm = LLMAttrappe(_antwort(anzahl))
    thread = kurzgeschichte.starte(conn, tg, klm, einst, 1)
    assert thread is not None
    thread.join(timeout=10)

    szenen = repo.hole_szenen(conn, 1)
    assert len(szenen) == anzahl
    assert all(not (z["form"] or "") for z in szenen)
    assert klm.gesehen["art"] == kurzgeschichte.ART
    verbunden = "\n".join(tg.texte)
    assert "Abschnitt Nummer 1" in verbunden
    assert f"Abschnitt Nummer {anzahl}" in verbunden
    # Genau EINE Leiste mit den drei Wegen -- nicht je Abschnitt eine.
    leisten = [
        leiste for _, _, leiste in tg.knoepfe
        if any("Passt" in b[0] for b in leiste)
    ]
    assert len(leisten) == 1
    beschriftungen = [b[0] for b in leisten[0]]
    assert len(beschriftungen) == 3


def test_zweiter_lauf_waehrend_des_ersten_wird_abgewiesen(conn, tg, einst):
    _vorbereitet(conn)
    sperre = kurzgeschichte._sperre_fuer(1)
    sperre.acquire()
    try:
        assert kurzgeschichte.laeuft(1) is True
        assert kurzgeschichte.starte(conn, tg, LLMAttrappe(_antwort(3)), einst, 1) is None
    finally:
        sperre.release()


def test_anders_knopf_wartet_auf_die_notiz_und_startet_damit(conn, tg, einst):
    """"Etwas aendern" startet nichts -- es fragt. Die naechste Nachricht ist
    die Regie-Notiz und geht in den naechsten Lauf."""
    _vorbereitet(conn)
    kurzgeschichte.lege_szenen_an(conn, 1, kurzgeschichte.zerlege(_antwort(3)))
    tg.knoepfe.clear()
    knoepfe.zeige_kurzgeschichte(conn, tg, 1)
    ziel = None
    for _, _, leiste in tg.knoepfe:
        for text, daten in leiste:
            if "aendern" in text:
                ziel = daten
    assert ziel is not None
    knoepfe.behandle(conn, tg, None, einst, _druck(ziel))
    assert knoepfe.nimm_geschichte_notiz(1) is True
    # Und einmal genommen ist der Merker verbraucht.
    assert knoepfe.nimm_geschichte_notiz(1) is False


# --- (b) Eintritt in Phase 6 -------------------------------------------


def test_eintritt_phase6_stellt_die_usa_frage_vor_dem_lauf(conn, tg, einst):
    """Einleitung, dann die USA-Frage als eigene Nachricht -- und noch KEIN
    Startknopf: erst die Antwort, dann der Knopf."""
    mit_claude = dataclasses.replace(einst, szene_anbieter="claude")
    knoepfe.eintritt_in_phase(conn, tg, None, mit_claude, 1, 6)
    verbunden = "\n".join(tg.texte)
    assert "Phase 6 von 7" in verbunden
    assert "USA" in verbunden
    assert "Ja, US-Modell" in tg.knopftexte
    assert "Nein, Schweiz" in tg.knopftexte
    assert knoepfe.TEXT_GESCHICHTE_SCHREIBEN_KNOPF not in tg.knopftexte


def test_eintritt_phase6_ohne_us_modell_zeigt_den_startknopf(conn, tg, einst):
    ohne_claude = dataclasses.replace(einst, szene_anbieter="infomaniak")
    knoepfe.eintritt_in_phase(conn, tg, None, ohne_claude, 1, 6)
    assert knoepfe.TEXT_GESCHICHTE_SCHREIBEN_KNOPF in tg.knopftexte


def test_usa_antwort_in_phase6_bringt_den_startknopf(conn, tg, einst):
    mit_claude = dataclasses.replace(einst, szene_anbieter="claude")
    phasen.setze(conn, 1, 6, "test")
    tg.knoepfe.clear()
    knoepfe.biete_szene_usa(conn, tg, 1)
    ziel = None
    for _, _, leiste in tg.knoepfe:
        for text, daten in leiste:
            if text == "Nein, Schweiz":
                ziel = daten
    assert ziel is not None
    tg.knoepfe.clear()
    knoepfe.behandle(conn, tg, None, mit_claude, _druck(ziel))
    assert knoepfe.TEXT_GESCHICHTE_SCHREIBEN_KNOPF in tg.knopftexte


# --- (c) Erfundene Systemzeilen ----------------------------------------


@pytest.mark.parametrize("text", [
    "Start frei!",
    "Gut, ich schreibe die Szene aus.",
    "Das laeuft jetzt auf einem US-Server.",
    "Soll ich das US-Modell nehmen oder in der Schweiz bleiben?",
    "Ich schreibe eure Szene jetzt aus, das dauert ein paar Minuten.",
])
def test_systemzeilen_werden_erkannt(text):
    assert ablauf.ist_erfundene_systemzeile(text) is True


@pytest.mark.parametrize("text", [
    "Wollt ihr noch etwas zur Szene sagen?",
    "Ihr habt drei Figuren notiert.",
    "",
    None,
])
def test_normale_antworten_gehen_durch(text):
    assert ablauf.ist_erfundene_systemzeile(text) is False


def test_system_prompt_verbietet_die_ansage():
    from interview_theater import anweisungen

    system = anweisungen.hole("system")
    assert "Start frei" in system
    assert "Geschichte schreiben" in system

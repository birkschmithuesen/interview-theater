"""Der EINE Ueberarbeitungslauf nach einem Szenentext (30.09.2026, Karte R).

Drei Zusagen, jede als Test:
1. Nachzaehlen und Sprachpass ergeben EINE Notiz und EINEN Lauf -- sonst
   waeren es bis zu zwei je Szene, und der Kostendeckel der Karte (+1 im
   Schnitt) waere gerissen.
2. Auch zwei zu lange Ergebnisse hintereinander ergeben genau einen Lauf: der
   Pfad ist gerade, ohne Schleife.
3. Verliert der Lauf ein geprueftes Belegzitat, wird er verworfen und die
   alte Fassung bleibt.

Kein Netz: Telegram und Sprachmodell sind Attrappen.
"""

import pytest

from interview_theater import (
    kuerzung, laengen, nachpass, phasen, repo, sprachpass, szene, workshop,
)

from test_knoepfe import TelegramAttrappe


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _vorfallarten(conn, chat_id: int = 1) -> list[str]:
    """Die ``art``-Werte der Vorfaelle dieser Gruppe.

    Direkt gelesen und nicht ueber ``repo``: es gibt dort keinen Leser
    (``merke_vorfall`` schreibt nur), und der einzige vorhandene liegt in
    ``web_daten`` an der read-only geoeffneten Verbindung. Dieselbe Bauart wie
    in ``tests/test_festlegung_erkenner.py``."""
    return [z["art"] for z in conn.execute(
        "SELECT art FROM vorfall WHERE chat_id = ? ORDER BY id", (chat_id,))]


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _szenentext(koerper: str) -> str:
    return (
        "TITEL: Am Steg\nKURZ: Sie treffen sich.\n"
        "ZUSAMMENFASSUNG: Mira und Pal treffen sich.\nANDERS GEMACHT: nichts\n\n"
        + koerper
    )


#: Ein Text weit ueber jedem Dialog-Budget (450 * 1,3 = 585).
LANG = _szenentext("MIRA: " + ("wort " * 900) + "\n")

#: Derselbe Text, aber kurz -- und sauber.
KURZ = _szenentext("MIRA: Du bist zu spaet.\nPAL: Ich war da.\n")


class LLMAttrappe:
    """Liefert der Reihe nach die vorgegebenen Antworten und merkt jeden
    Aufruf samt ``art``. Ist die Liste leer, wiederholt sie die letzte."""

    def __init__(self, *antworten):
        self.antworten = list(antworten) or [KURZ]
        self.aufrufe = []

    def prosa(self, chat_id, system, nutzer, art, max_tokens=None, timeout=None,
              bei_teil=None):
        self.aufrufe.append({"system": system, "nutzer": nutzer, "art": art})
        i = min(len(self.aufrufe) - 1, len(self.antworten) - 1)
        return self.antworten[i]


@pytest.fixture
def szene7(conn, padua):
    """Phase 7, eine planungsvollstaendige Szene 1 mit Form ``dialog``."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Am Kanal, nachts")
    repo.setze_arbeitsstand(conn, 1, "geschichte", "Zwei verlieren sich.\nEnde: offen")
    repo.setze_figur(conn, 1, "Mira", "will gefragt werden")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    for feld, wert in (("form", "dialog"), ("ort", "Steg"),
                       ("was_passiert", "Sie treffen sich.")):
        repo.setze_szenenfeld(conn, szene_id, feld, wert)
    repo.setze_szene_figuren(conn, 1, szene_id, [figur_id])
    phasen.setze(conn, 1, 7, "test")
    return conn


# --- Der Befund (reine Leseabfrage) --------------------------------------


def test_ein_kurzer_sauberer_text_meldet_nichts(szene7):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", KURZ, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["zu_lang"] is False
    assert befund["gemeldet"] == []


def test_ein_zu_langer_text_wird_gemeldet(szene7):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["budget"] > 0
    assert befund["woerter"] > befund["budget"]
    assert befund["zu_lang"] is True


def test_der_befund_ruft_kein_modell(szene7):
    """Reine Leseabfrage wie ``phasen.voraussetzungen`` -- damit ihn jeder
    Ort rufen darf, auch ein Knopf-Handler (Zusage 2)."""
    import inspect
    quelle = inspect.getsource(nachpass.befund)
    for verboten in ("klm", ".prosa(", "schreibe("):
        assert verboten not in quelle, verboten


def test_ohne_aktives_profil_meldet_der_befund_nichts(szene7, monkeypatch):
    monkeypatch.delenv(workshop.VARIABLE, raising=False)
    workshop.vergiss()
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    befund = nachpass.befund(szene7, 1, 1)
    assert befund["budget"] == 0
    assert befund["zu_lang"] is False
    assert befund["gemeldet"] == []


# --- Genau EIN Lauf -----------------------------------------------------


def test_ein_sauberer_text_loest_keinen_lauf_aus(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", KURZ, "passiert")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_szene(szene7, tg, klm, einst, 1, 1) is None
    assert klm.aufrufe == []


def test_ein_zu_langer_text_loest_genau_einen_lauf_aus(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert notiz and str(kuerzung.PROZENT) in notiz
    assert len(klm.aufrufe) == 1
    assert klm.aufrufe[0]["art"] == nachpass.ART_SZENE


def test_zwei_zu_lange_ergebnisse_ergeben_trotzdem_einen_lauf(szene7, tg, einst):
    """Der Kern des Kostendeckels: auch wenn der gekuerzte Text noch ueber dem
    Budget liegt, gibt es keinen zweiten Lauf. Nur einen Vorfall."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    klm = LLMAttrappe(LANG)          # der Nachpass liefert wieder zu viel
    nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert len(klm.aufrufe) == 1
    arten = _vorfallarten(szene7)
    assert nachpass.VORFALL_IMMER_NOCH in arten


def test_laenge_und_sprache_ergeben_EINE_notiz(szene7, tg, einst):
    """Nachzaehlen und Sprachpass buendeln in einem Lauf. Waeren es zwei Wege,
    waeren es bis zu zwei Laeufe je Szene."""
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    # Abweichung vom Plan: je Muster DREI Vorkommen. Eines in rund 920
    # Woertern sind ~1,1 je 1.000 und liegen unter dem Grenzwert 2,0 -- der
    # Sprachpass meldete dann gar nichts, und der Test pruefte nur die Laenge.
    text = _szenentext(
        "MIRA: " + ("wort " * 900) + "\n"
        + "PAL: She was tired, angry, and alone.\n" * 3
        + "MIRA: It was not a home but a waiting room.\n" * 3
    )
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert len(klm.aufrufe) == 1
    # Padua spricht Englisch: die Notiz kommt ueber ``T``.
    assert str(kuerzung.PROZENT) in notiz            # die Laenge
    assert sprachpass.T.NOTIZ_KOPF in notiz          # die Sprache
    assert sprachpass.T.NOTIZ_ZITATE in notiz        # der Zitatschutz


def test_nur_sprache_ohne_laenge_laeuft_auch(szene7, tg, einst):
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    text = _szenentext(
        "MIRA: She was tired, angry, and alone.\n"
        "PAL: It felt cold, wet, empty.\n"
        "MIRA: Maybe home is just where you stop explaining.\n"
    )
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    notiz = nachpass.nach_szene(szene7, tg, klm, einst, 1, 1)
    assert notiz and sprachpass.T.NOTIZ_KOPF in notiz
    assert str(kuerzung.PROZENT) not in notiz
    assert len(klm.aufrufe) == 1


def test_bei_ausgeschaltetem_sprachpass_zaehlt_nur_die_laenge(szene7, tg, einst,
                                                              monkeypatch):
    monkeypatch.setattr(laengen, "sprachpass_aktiv", lambda profil=None: False)
    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    text = _szenentext("MIRA: She was tired, angry, and alone.\n")
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", text, "passiert")
    klm = LLMAttrappe(KURZ)
    assert nachpass.nach_szene(szene7, tg, klm, einst, 1, 1) is None
    assert klm.aufrufe == []


# --- Der Zitatschutz ----------------------------------------------------


@pytest.fixture
def mit_zitat(szene7):
    """Ein geprueftes Belegzitat, das im Szenentext woertlich vorkommt."""
    conn = szene7
    repo.setze_figur(conn, 1, "Mira", "wartet")
    figur_id = repo.figuren(conn, 1)[0]["id"]
    # Ueber ``setze_sprachprofil`` -- ``setze_figur_feld`` kennt nur Name und
    # Beschreibung (Abweichung vom Plan).
    repo.setze_sprachprofil(conn, figur_id, "kurze Saetze",
                            ["also ich, ja, ich weiss nicht"])
    szene_id = repo.hole_szenen(conn, 1)[0]["id"]
    text = _szenentext(
        "MIRA: also ich, ja, ich weiss nicht. " + ("wort " * 900) + "\n")
    repo.aktualisiere_szene(conn, szene_id, "Am Steg", "kurz", text, "passiert")
    return conn


def test_ein_lauf_der_das_zitat_behaelt_bleibt_stehen(mit_zitat, tg, einst):
    gut = _szenentext("MIRA: also ich, ja, ich weiss nicht.\nPAL: Und?\n")
    klm = LLMAttrappe(gut)
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    aktuell = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    assert "also ich, ja, ich weiss nicht" in aktuell
    assert "wort wort" not in aktuell, "der gekuerzte Text ist nicht angekommen"


def test_ein_veraendertes_zitat_verwirft_den_lauf(mit_zitat, tg, einst):
    """Die Attrappe glaettet den Interviewsatz -- genau theater-tells Nr. 21.
    Dann bleibt die alte Fassung, und es gibt einen Vorfall."""
    schlecht = _szenentext("MIRA: Es war eine schwierige Zeit fuer mich.\n")
    klm = LLMAttrappe(schlecht)
    vorher = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    nachher = repo.hole_szenen(mit_zitat, 1)[0]["volltext"]
    assert nachher == vorher, "die alte Fassung muss stehenbleiben"
    arten = _vorfallarten(mit_zitat)
    assert nachpass.VORFALL_VERWORFEN in arten


def test_die_fassungszeile_des_verworfenen_laufs_bleibt_stehen(mit_zitat, tg, einst):
    """``szenenfassung`` wird nur angehaengt (AGENTS.md). Der Lauf hat
    stattgefunden -- die Spur ist richtig, und wer den Text sehen will, findet
    ihn auf der Gruppenseite."""
    szene_id = repo.hole_szenen(mit_zitat, 1)[0]["id"]
    vorher = len(repo.szenenfassungen(mit_zitat, szene_id))
    klm = LLMAttrappe(_szenentext("MIRA: Es war eine schwierige Zeit.\n"))
    nachpass.nach_szene(mit_zitat, tg, klm, einst, 1, 1)
    assert len(repo.szenenfassungen(mit_zitat, szene_id)) == vorher + 1


def test_ein_gescheiterter_lauf_laesst_die_szene_unberuehrt(szene7, tg, einst):
    """Der Nachpass ist eine Zugabe. Reisst er, bleibt die Szene, die die
    Gruppe schon hat -- und die Gruppe erfaehrt nichts davon: sie kann nichts
    tun und wartet nicht darauf (SPEC § 11.1)."""
    class Kaputt:
        def prosa(self, *a, **k):
            raise RuntimeError("Modell weg")

    szene_id = repo.hole_szenen(szene7, 1)[0]["id"]
    repo.aktualisiere_szene(szene7, szene_id, "Am Steg", "kurz", LANG, "passiert")
    vorher = repo.hole_szenen(szene7, 1)[0]["volltext"]
    assert nachpass.nach_szene(szene7, tg, Kaputt(), einst, 1, 1) is None
    assert repo.hole_szenen(szene7, 1)[0]["volltext"] == vorher
    fehler = szene.T._TEXT_FEHLER
    assert all(fehler not in t for t in tg.texte), tg.texte

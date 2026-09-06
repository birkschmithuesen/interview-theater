"""Die Stil-Auswahl im Feinschliff (06.09.2026, Birk 12:50).

Im Wortlaut: *"alle Gruppen sollen auf alle Stile zugreifen koennen, als
Auswahl, mit Nennung des Originalmaterials."* Bis dahin hing ein Stil am
Bot -- eine Overlay-Datei je Gruppe, die niemand waehlen konnte.

Gemessen wird deshalb dreierlei: dass das Menue **alle** Stile mit ihrer
Herkunft zeigt, dass die Wahl in ``szene.stil`` landet, und dass der
Stil-Block nur bei ``form != prosa`` in den Prompt geht -- die Prosafassung
ist eine Geschichte, kein Buehnentext.
"""

import pytest

from interview_theater import knoepfe, repo, stile, szene, web_schreiben


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
        self.beantwortet = []
        self.entfernt = []
        self.naechste_message_id = 700

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


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _druck(daten, chat_id=1, message_id=777, query_id="q1"):
    return {
        "callback_query_id": query_id,
        "data": daten,
        "chat_id": chat_id,
        "chat_titel": "Testgruppe",
        "message_id": message_id,
    }


# --- Der Katalog --------------------------------------------------------


def test_jeder_stil_hat_titel_satz_und_herkunft():
    assert len(stile.alle()) >= 3
    for eintrag in stile.alle():
        assert eintrag["slug"] and eintrag["titel"]
        assert eintrag["satz"].strip()
        assert eintrag["herkunft"].strip(), eintrag["slug"]


def test_die_herkunft_nennt_das_originalmaterial():
    """Birk, 12:50: mit Nennung des Originalmaterials -- Titel UND Urheber."""
    nach_slug = {e["slug"]: e["herkunft"] for e in stile.alle()}
    assert "Schatten" in nach_slug["schlagabtausch"]
    assert "Morpheuz" in nach_slug["schlagabtausch"]
    assert "Lovesong" in nach_slug["litanei"]
    assert "Adele" in nach_slug["litanei"]
    assert "Herkules.exe" in nach_slug["herkules"]
    assert "ArtesMobiles" in nach_slug["herkules"]


def test_zu_jedem_stil_gibt_es_eine_promptdatei():
    for eintrag in stile.alle():
        block = stile.regelblock(eintrag["slug"])
        assert block.strip(), eintrag["slug"]
        # Der Kommentarkopf der Kopie ("<!-- Kopie aus docs/... -->") ist
        # eine Notiz an den Menschen und gehoert nicht in den Prompt.
        assert "<!--" not in block


def test_ohne_und_unbekannt_liefern_keinen_block():
    assert stile.regelblock(None) == ""
    assert stile.regelblock("") == ""
    assert stile.regelblock(stile.OHNE) == ""
    assert stile.regelblock("gibtsnicht") == ""


# --- Das Menue ----------------------------------------------------------


def test_menue_zeigt_alle_stile_mit_herkunft(conn, tg):
    """Eine Nachricht, alle Stile, jeder mit Herkunft -- und ein Knopf je
    Stil plus "Ohne Stilvorlage"."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 2)
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    knoepfe.biete_szenenstil(conn, tg, 1, 2)

    text = tg.texte[-1]
    for eintrag in stile.alle():
        assert eintrag["titel"] in text
        assert eintrag["herkunft"] in text
    assert stile.TEXT_OHNE in text

    leiste = tg.knoepfe[-1][2]
    assert len(leiste) == len(stile.alle()) + 1
    for beschriftung, _ in leiste:
        assert len(beschriftung) <= knoepfe.MENUE_KNOPF_LAENGE


@pytest.mark.parametrize("form,erwartet", [
    ("rap", "schlagabtausch"),
    ("lied", "litanei"),
    ("chor", "litanei"),
    ("dialog", "herkules"),
    ("monolog", "herkules"),
])
def test_bot_schlaegt_passend_zur_form_vor(conn, tg, form, erwartet):
    """Der Vorschlag steht ZUERST, traegt "(Vorschlag)" und hat eine
    Begruendung -- ein Vorschlag, keine Vorentscheidung."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", form)
    knoepfe.biete_szenenstil(conn, tg, 1, 1)

    text = tg.texte[-1]
    assert "(Vorschlag)" in text
    kopf = text.split("\n\n")[2]
    assert stile.beschriftung(erwartet) in kopf
    # Die Begruendung steht ueber dem Menue.
    assert stile.VORSCHLAG_GRUND[form] in text
    # Gesetzt ist noch nichts.
    assert not (repo.hole_szene(conn, szene_id)["stil"] or "")


def test_knopf_und_punkt_meinen_dasselbe(conn, tg):
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "rap")
    knoepfe.biete_szenenstil(conn, tg, 1, 1)
    text = tg.texte[-1]
    leiste = tg.knoepfe[-1][2]
    for nummer, eintrag in enumerate(
        stile.reihenfolge_mit_vorschlag("schlagabtausch"), start=1
    ):
        assert leiste[nummer - 1][0].startswith(f"{nummer} · ")
        assert f"{nummer}. **{eintrag['titel']}**" in text


# --- Die Wahl setzt szene.stil -----------------------------------------


def test_wahl_setzt_szene_stil(conn, tg, einst):
    szene_id = repo.stelle_szene_sicher(conn, 1, 3)
    repo.setze_szenenfeld(conn, szene_id, "form", "lied")
    knoepfe.biete_szenenstil(conn, tg, 1, 3)
    ziel = next(
        daten for text, daten in tg.knoepfe[-1][2]
        if "Schlagabtausch" in text
    )
    knoepfe.behandle(conn, tg, None, einst, _druck(ziel))

    assert repo.hole_szene(conn, szene_id)["stil"] == "schlagabtausch"
    # Die Bestaetigung nennt die Vorlage -- wie das Menue.
    verbunden = "\n".join(tg.texte)
    assert "Morpheuz" in verbunden
    assert any(
        "Stil" in z["text"] for z in repo.journal(conn, 1)
    )


def test_ohne_stilvorlage_speichert_null(conn, tg, einst):
    szene_id = repo.stelle_szene_sicher(conn, 1, 4)
    repo.setze_szenenfeld(conn, szene_id, "form", "dialog")
    repo.setze_szenenfeld(conn, szene_id, "stil", "litanei")
    knoepfe.biete_szenenstil(conn, tg, 1, 4)
    ziel = next(
        daten for text, daten in tg.knoepfe[-1][2] if text == stile.TEXT_OHNE
    )
    knoepfe.behandle(conn, tg, None, einst, _druck(ziel))

    assert repo.hole_szene(conn, szene_id)["stil"] is None


def test_formwahl_fuehrt_ins_stilmenue(conn, tg, einst):
    """Die Reihenfolge im Feinschliff: Form, dann Stil, dann schreiben."""
    knoepfe.biete_szenenform(conn, tg, 1, 5)
    ziel = next(daten for text, daten in tg.knoepfe[-1][2] if text.startswith("Rap"))
    tg.knoepfe.clear()
    knoepfe.behandle(conn, tg, None, einst, _druck(ziel))

    verbunden = "\n".join(tg.texte)
    assert "Welcher Stil?" in verbunden
    for eintrag in stile.alle():
        assert eintrag["herkunft"] in verbunden


# --- Der Prompt ---------------------------------------------------------


def test_stilblock_haengt_bei_einer_form_dran():
    ohne = szene.systemanweisung("dialog", None)
    mit = szene.systemanweisung("dialog", "litanei")
    assert len(mit) > len(ohne)
    assert "Satzschablone" in mit
    # Nach dem Formen-Regelblock und VOR den Tells.
    tells_stelle = mit.find("Theater-Tells")
    stil_stelle = mit.find("Satzschablone")
    if tells_stelle >= 0:
        assert stil_stelle < tells_stelle


def test_prosa_traegt_nie_einen_stilblock():
    """Die Prosafassung ist eine Geschichte, kein Buehnentext -- ein
    Rap-Mass darauf waere eine Regel ueber eine Textsorte, die es hier nicht
    gibt."""
    mit = szene.systemanweisung(szene.PROSA, "schlagabtausch")
    ohne = szene.systemanweisung(szene.PROSA, None)
    assert mit == ohne
    assert "Hook" not in mit


def test_szenenlauf_traegt_den_stil_der_szene_in_den_prompt(conn):
    """Prompt-Audit-Pfad: der Stil steht wirklich in der Systemanweisung,
    die der Lauf schickt."""
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.setze_szenenfeld(conn, szene_id, "form", "rap")
    repo.setze_szenenfeld(conn, szene_id, "stil", "schlagabtausch")
    zeile = repo.hole_szene(conn, szene_id)
    system = szene.systemanweisung(zeile["form"], zeile["stil"])
    assert "Hook" in system or "Schlagabtausch" in system
    # Der Stil-Block ist ein Zusatz, kein zweiter Prompt: er bleibt klein
    # gegen die Systemanweisung. ``kontext.zeichengrenze`` gilt fuer den
    # NUTZERtext und nicht hier -- die Systemanweisung ist ohnehin schon
    # groesser (dialog.md ohne Stil: ueber 30.000 Zeichen).
    ohne = szene.systemanweisung(zeile["form"], None)
    assert len(system) - len(ohne) < 8000


# --- Die Weboberflaeche -------------------------------------------------


def test_stile_sind_die_aus_stile():
    """Zwei Listen, ein Wertevorrat -- sonst stuenden fuer denselben Stil
    zwei Schreibweisen in der Datenbank."""
    assert set(web_schreiben.STILE) == {e["slug"] for e in stile.alle()}
    assert set(web_schreiben.STIL_BESCHRIFTUNG) == set(web_schreiben.STILE)


def test_web_beschriftung_nennt_die_vorlage():
    for slug, beschriftung in web_schreiben.STIL_BESCHRIFTUNG.items():
        assert "(" in beschriftung and ")" in beschriftung, slug


def test_web_schreibt_den_stil(conn):
    repo.stelle_szene_sicher(conn, 1, 1)
    zeile = repo.hole_szenen(conn, 1)[0]
    web_schreiben.wende_an(conn, 1, "szene_stil", "litanei", zeile["id"])
    assert repo.hole_szene(conn, zeile["id"])["stil"] == "litanei"
    web_schreiben.wende_an(conn, 1, "szene_stil", "", zeile["id"])
    assert repo.hole_szene(conn, zeile["id"])["stil"] is None

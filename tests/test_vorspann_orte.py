"""Wo der Vorspann erscheint: im Chat vor dem Prosatext und im Textbuch
(07.09.2026).

Die Gruppenseite hat ihre eigene Datei (``test_vorspann_web.py``), weil sie
ueber ``web_daten`` read-only liest und nicht ueber ``repo``.

Gemessen wird die **Reihenfolge**: der Vorspann steht davor, nicht darunter --
eine Besetzungsliste hinter dreitausend Woertern Prosa liest niemand mehr.

Alle Namen und Texte sind erfunden.
"""

import pytest

from interview_theater import db, knoepfe, repo, szenenfolge


class TelegramAttrappe:
    def __init__(self):
        self.gesendet = []
        self.knoepfe = []
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

    def entferne_knoepfe(self, chat_id, message_id):
        pass

    @property
    def texte(self):
        return [t for _, t in self.gesendet]


@pytest.fixture
def tg():
    return TelegramAttrappe()


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Die Ankommenden")
    return c


def _stueck(conn):
    """Ein kleines Stueck: Setting, Konflikt, Form, zwei Szenen mit Prosa,
    drei Figuren -- eine davon entfernt."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ein Hinterhof, Juli, abends")
    repo.setze_arbeitsstand(conn, 1, "hauptkonflikt", "Bleiben oder gehen")
    repo.setze_arbeitsstand(conn, 1, "format", "Musical: Dialog, Lied")
    repo.setze_figur(conn, 1, "Mira", "haelt den Laden zusammen seit Jahren zeigt das")
    repo.setze_figur(conn, 1, "Jonas", "kommt zu spaet.")
    repo.setze_figur(conn, 1, "Karim", "war mal dabei")
    repo.entferne_figur(conn, 1, "Karim")
    for nummer, titel, prosa in (
        (1, "Am Steg", "Sie steht am Wasser und wartet."),
        (2, "Die Kueche", "Der Topf kocht ueber."),
    ):
        szene_id = repo.stelle_szene_sicher(conn, 1, nummer)
        repo.setze_szenenfeld(conn, szene_id, "titel", titel)
        repo.aktualisiere_szene(conn, szene_id, titel, None, None, None, prosa=prosa)


# --- Chat (Phase 6) --------------------------------------------------------


def test_vorspann_steht_im_chat_vor_dem_prosatext(conn, tg):
    _stueck(conn)

    knoepfe.zeige_kurzgeschichte(conn, tg, 1)

    verbunden = "\n\n".join(tg.texte)
    assert "Wer vorkommt" in verbunden
    assert verbunden.index("Wer vorkommt") < verbunden.index("Sie steht am Wasser")


def test_vorspann_im_chat_nennt_rahmen_szenen_und_besetzung(conn, tg):
    _stueck(conn)

    knoepfe.zeige_kurzgeschichte(conn, tg, 1)

    verbunden = "\n\n".join(tg.texte)
    assert "Ein Hinterhof, Juli, abends" in verbunden
    assert "Bleiben oder gehen" in verbunden
    assert "Musical: Dialog, Lied" in verbunden
    assert "2 Szenen" in verbunden
    assert "1. Am Steg" in verbunden
    # Der erste Satz, nicht die Schaerfungsnotiz.
    assert "Mira — haelt den Laden zusammen seit Jahren" in verbunden
    assert "zeigt das" not in verbunden
    # Die entfernte Figur steht nirgends.
    assert "Karim" not in verbunden


def test_ohne_arbeitsstand_kommt_kein_leerer_vorspann(conn, tg):
    szene_id = repo.stelle_szene_sicher(conn, 1, 1)
    repo.aktualisiere_szene(conn, szene_id, None, None, None, None, prosa="Ein Satz.")

    knoepfe.zeige_kurzgeschichte(conn, tg, 1)

    verbunden = "\n\n".join(tg.texte)
    assert "Wer vorkommt" not in verbunden
    assert "Wo und wann" not in verbunden
    assert "Ein Satz." in verbunden


def test_der_vorspann_kostet_keinen_modellaufruf(conn, tg):
    """Zusage aus dem Auftrag: deterministisch. ``zeige_kurzgeschichte``
    bekommt gar kein Modellobjekt -- das ist die strukturelle Garantie."""
    import inspect

    unterschrift = inspect.signature(knoepfe.zeige_kurzgeschichte)

    assert list(unterschrift.parameters) == ["conn", "tg", "chat_id"]


# --- Textbuch --------------------------------------------------------------


def test_textbuch_beginnt_mit_dem_vorspann(conn):
    _stueck(conn)

    text = szenenfolge.textbuch(conn, 1)

    assert text.startswith("# Textbuch")
    assert "## Wer vorkommt" in text
    assert "**Mira** — haelt den Laden zusammen seit Jahren" in text
    assert text.index("## Wer vorkommt") < text.index("## Szene 1")


def test_textbuch_ohne_arbeitsstand_bleibt_wie_bisher(conn):
    repo.stelle_szene_sicher(conn, 1, 1)

    text = szenenfolge.textbuch(conn, 1)

    assert "## Wer vorkommt" not in text
    assert "## Szene 1" in text

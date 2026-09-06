"""Bestehende Szenen werden nie ersetzt, nur abgeglichen (06.09.2026).

Der Bauplan ist ``docs/analyse-phase5-chaos-2026-09-06.md``, Abschnitt B:
eine Festlegung der Gruppe, die im naechsten Lauf neu erfunden wird, ist
keine Festlegung. Gemessener Live-Fall: drei geplante Szenen mit ihrer
Formfestlegung wurden von einem zweiten Vorschlagslauf weich entfernt und
durch sechs neue ersetzt -- und danach noch einmal, diesmal samt der schon
geschriebenen Prosa.

Die Regel, die hier gemessen wird:

* Szene N gibt es schon -> ihre Felder werden **aktualisiert**.
* Szene N fehlt -> sie wird **ergaenzt**.
* Ueberzaehlige Szenen -> sie **bleiben stehen** (Entfernen nur auf
  ausdruecklichen Wunsch, ``repo.entferne_szene``).
* ``form``/``form_vorschlag``/``stil`` und ``volltext``/``prosa``
  **ueberleben** jeden Abgleich.

Alle Daten sind erfunden: Buehnenfiguren, keine Personen, keine
Interviewinhalte.
"""

import pytest

from interview_theater import kurzgeschichte, repo, szenenfolge


def _drei_szenen(conn, chat_id=1):
    return szenenfolge.lege_an(
        conn,
        chat_id,
        [
            ("Am Steg", "sie warten", [], "chor", "Beginn im Kollektiv"),
            ("In der Kueche", "es kippt", [], "dialog", "Zwei gegeneinander"),
            ("Der Kessel", "es eskaliert", [], "rap", "Tempo zum Schluss"),
        ],
    )


# --- Mehr, weniger, gleich viele ------------------------------------------


def test_mehr_szenen_als_vorher_ergaenzt_ohne_zu_loeschen(conn):
    _drei_szenen(conn)
    vorher = {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, 1)}

    nummern = szenenfolge.lege_an(
        conn,
        1,
        [(f"Bild {n}", f"da passiert {n}", [], "dialog", "") for n in range(1, 6)],
    )

    assert nummern == [1, 2, 3, 4, 5]
    szenen = repo.hole_szenen(conn, 1)
    assert [s["nummer"] for s in szenen] == [1, 2, 3, 4, 5]
    for nummer, alte_id in vorher.items():
        assert {s["nummer"]: s["id"] for s in szenen}[nummer] == alte_id


def test_weniger_szenen_laesst_die_ueberzaehligen_stehen(conn):
    _drei_szenen(conn)

    nummern = szenenfolge.lege_an(
        conn, 1, [("Nur noch eine", "alles auf einmal", [], "dialog", "")]
    )

    assert nummern == [1]
    szenen = repo.hole_szenen(conn, 1)
    assert [s["nummer"] for s in szenen] == [1, 2, 3]
    assert szenen[0]["titel"] == "Nur noch eine"
    # Die ueberzaehligen sind unveraendert -- nicht entfernt, nicht umbenannt.
    assert szenen[1]["titel"] == "In der Kueche"
    assert szenen[2]["titel"] == "Der Kessel"


def test_gleiche_anzahl_mit_geaenderten_inhalten_aktualisiert(conn):
    _drei_szenen(conn)
    vorher = {s["nummer"]: s["id"] for s in repo.hole_szenen(conn, 1)}

    szenenfolge.lege_an(
        conn,
        1,
        [
            ("Am Steg, spaeter", "sie warten immer noch", [], "chor", ""),
            ("Im Flur", "es kippt frueher", [], "dialog", ""),
            ("Der Kessel", "es eskaliert leiser", [], "rap", ""),
        ],
    )

    szenen = repo.hole_szenen(conn, 1)
    assert [s["titel"] for s in szenen] == ["Am Steg, spaeter", "Im Flur", "Der Kessel"]
    assert szenen[1]["was_passiert"] == "es kippt frueher"
    assert {s["nummer"]: s["id"] for s in szenen} == vorher


def test_bericht_trennt_neu_aktualisiert_und_ueberzaehlig(conn):
    _drei_szenen(conn)

    bericht = repo.gleiche_szenenfolge_ab(
        conn, 1, [{"titel": "Eins neu"}, {"titel": "Zwei neu"}]
    )

    assert bericht["aktualisiert"] == [1, 2]
    assert bericht["neu"] == []
    assert bericht["ueberzaehlig"] == [3]


# --- Was ueberlebt --------------------------------------------------------


def test_bestaetigte_form_ueberlebt_einen_zweiten_lauf(conn):
    """Die Formfestlegung traegt ein Knopfdruck der Gruppe -- kein Lauf darf
    sie zuruecknehmen (Birk, 06.09.2026 00:30)."""
    _drei_szenen(conn)
    for zeile in repo.hole_szenen(conn, 1):
        repo.setze_szenenfeld(conn, zeile["id"], "form", "chor")
        repo.setze_szenenfeld(conn, zeile["id"], "stil", "litanei")

    szenenfolge.lege_an(
        conn,
        1,
        [("Ganz anders", "ganz anders", [], "monolog", "neuer Vorschlag")] * 3,
    )

    for zeile in repo.hole_szenen(conn, 1):
        assert zeile["form"] == "chor"
        assert zeile["stil"] == "litanei"


def test_formvorschlag_ueberlebt_und_wird_nur_leer_gefuellt(conn):
    _drei_szenen(conn)
    assert [z["form_vorschlag"] for z in repo.hole_szenen(conn, 1)] == [
        "chor", "dialog", "rap",
    ]

    szenenfolge.lege_an(
        conn, 1, [("A", "a", [], "monolog", "x"), ("B", "b", [], "monolog", "x")]
    )

    # Der bestehende Vorschlag bleibt: er ist die Fassung, an der die Gruppe
    # ihren Druck festmacht.
    assert [z["form_vorschlag"] for z in repo.hole_szenen(conn, 1)] == [
        "chor", "dialog", "rap",
    ]
    # Eine frisch ergaenzte Szene bekommt ihn dagegen sehr wohl.
    szenenfolge.lege_an(
        conn,
        1,
        [("A", "a", [], "monolog", "x")] * 4,
    )
    assert repo.hole_szenen(conn, 1)[3]["form_vorschlag"] == "monolog"


def test_volltext_und_prosa_ueberleben_die_szenenfolge(conn):
    _drei_szenen(conn)
    erste = repo.hole_szenen(conn, 1)[0]
    repo.aktualisiere_szene(
        conn, erste["id"], "Am Steg", None, "MIRA: Da bist du ja.",
        None, "Sie stand am Steg und wartete.",
    )

    szenenfolge.lege_an(conn, 1, [("Neuer Titel", "neu", [], "dialog", "")])

    frisch = repo.hole_szenen(conn, 1)[0]
    assert frisch["volltext"] == "MIRA: Da bist du ja."
    assert frisch["prosa"] == "Sie stand am Steg und wartete."
    assert frisch["titel"] == "Neuer Titel"


def test_kurzgeschichte_laesst_form_und_volltext_stehen(conn):
    """Der Prosa-Lauf darf seine eigene ``prosa`` neu schreiben -- die Form
    und einen fertigen Theatertext nicht."""
    repo.setze_arbeitsstand(conn, 1, "rahmen", "Ort: Steg, Zeit: abends")
    _drei_szenen(conn)
    erste = repo.hole_szenen(conn, 1)[0]
    repo.setze_szenenfeld(conn, erste["id"], "form", "chor")
    repo.aktualisiere_szene(
        conn, erste["id"], "Am Steg", None, "CHOR: Wir warten.", None, "alte Prosa",
    )

    kurzgeschichte.lege_szenen_an(
        conn, 1, [("Abschnitt eins", "es beginnt", "Die neue Prosafassung.")]
    )

    frisch = repo.hole_szenen(conn, 1)[0]
    assert frisch["form"] == "chor"
    assert frisch["volltext"] == "CHOR: Wir warten."
    # Die Prosa ist das Ergebnis genau dieses Laufs -- sie wird ersetzt.
    assert frisch["prosa"] == "Die neue Prosafassung."
    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 2, 3]


def test_leerer_vorschlagswert_loescht_nichts(conn):
    _drei_szenen(conn)

    repo.gleiche_szenenfolge_ab(conn, 1, [{"titel": "", "was_passiert": None}])

    erste = repo.hole_szenen(conn, 1)[0]
    assert erste["titel"] == "Am Steg"
    assert erste["was_passiert"] == "sie warten"


def test_unbekanntes_feld_ist_ein_programmierfehler(conn):
    with pytest.raises(ValueError):
        repo.gleiche_szenenfolge_ab(conn, 1, [{"gibtsnicht": "x"}])


def test_entfernen_bleibt_der_ausdrueckliche_weg(conn):
    _drei_szenen(conn)

    assert repo.entferne_szene(conn, 1, 2) == 2

    assert [s["nummer"] for s in repo.hole_szenen(conn, 1)] == [1, 3]

"""Ein ausdruecklicher Reset-/Ersetzen-Wunsch raeumt alte Festlegungen weg
(Live-Fund Padua 07.10.2026, G3, chat 7000000000002, web_post 1873):

"Cancella tutto il workbench. Abbiamo deciso, cioe, e rifai delle nuove
entry. [...] In teatro entra il pubblico. In scena c'e solamente un
bottone [...]"

Der Erkennerlauf auf diese Nachricht (erkenner_lauf 73) schrieb nur Format
und Stil -- die alte Struktur-Festlegung ("a zapping mechanism, ...") hatte
keinerlei Wortueberlapp mit irgendetwas aus diesem Lauf und blieb deshalb
unberuehrt stehen, obwohl die Gruppe ausdruecklich alles neu machen wollte.

Fixtures synthetisch, Wortlaut aus der Kopie-DB (VACUUM INTO einer
Padua-Live-DB, siehe Briefing).
"""

from interview_theater import erkenner, repo
from test_erkenner import LLMAttrappe, TelegramAttrappe, _nachricht

_ALTE_STRUKTUR = (
    "a zapping mechanism, stimulated or not by the spectator via a button, "
    "mixing true news, false news, and personal experiences from interviews"
)

_RESET_NACHRICHT = (
    "Cancella tutto il workbench. Abbiamo deciso, cioè, e rifai delle nuove "
    "entry. Vorremmo creare una... In teatro entra il pubblico. In scena "
    "c'è solamente un bottone, senza scritto niente."
)


def test_ist_reset_wunsch_erkennt_italienisch_und_englisch():
    assert erkenner._ist_reset_wunsch(_RESET_NACHRICHT)
    assert erkenner._ist_reset_wunsch("OK let's start over, clear the whole workbench")
    assert erkenner._ist_reset_wunsch("Delete everything and let's redo it")


def test_ist_reset_wunsch_nicht_bei_normalem_text():
    assert not erkenner._ist_reset_wunsch(
        "five moments of one day, one position per moment"
    )
    assert not erkenner._ist_reset_wunsch("a bar table near the university")


def test_reset_wunsch_raeumt_unverwandte_alte_festlegung_weg(conn, einst):
    """Reproduktion des Live-Funds: der Lauf auf die Reset-Nachricht traegt
    selbst nur Aenderungen in ANDEREN Bereichen (Format, Stil). Die alte
    Struktur-Festlegung hat keinen Wortueberlapp mit diesen und bliebe ohne
    den Reset-Wunsch unberuehrt stehen (der Fast-Dubletten-Schutz allein
    vergleicht nur innerhalb desselben Bereichs/Bezugs, siehe
    test_festlegung_erkenner.py)."""
    repo.schreibe_festlegung(conn, 1, "struktur", _ALTE_STRUKTUR)
    _nachricht(conn, 1, 1873, _RESET_NACHRICHT)
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "format_setzen",
         "wert": "Short scenes, short monologues, short stories"},
        {"art": "festlegung_setzen",
         "wert": "stil: very short scenes, monologues, or stories"},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    bereiche = {z["bereich"] for z in repo.festlegungen(conn, 1)}
    assert bereiche == {"stil"}
    stand = repo.hole_arbeitsstand(conn, 1)
    assert stand["format"] == "Short scenes, short monologues, short stories"


def test_reset_wunsch_journalisiert_die_entfernung(conn, einst):
    repo.schreibe_festlegung(conn, 1, "struktur", _ALTE_STRUKTUR)
    _nachricht(conn, 1, 1873, _RESET_NACHRICHT)
    klm = LLMAttrappe(antwort={"aenderungen": []})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    assert repo.festlegungen(conn, 1) == []
    journal = [
        z["text"] for z in conn.execute(
            "SELECT text FROM journal WHERE chat_id = 1 AND art = 'entschieden'"
        )
    ]
    assert any("Zurueckgenommen" in z and "zapping" in z for z in journal)


def test_ohne_reset_wunsch_bleibt_eine_unverwandte_festlegung_stehen(conn, einst):
    """Gegenprobe: ohne das ausdrueckliche Signalwort bleibt eine alte,
    lexikalisch unverwandte Festlegung unberuehrt stehen -- der Reset-Weg
    greift nur bei einem erkannten Wunsch, nicht bei jeder neuen Festlegung."""
    repo.schreibe_festlegung(conn, 1, "struktur", _ALTE_STRUKTUR)
    _nachricht(conn, 1, 1, "we want to add a new scene about the market square")
    klm = LLMAttrappe(antwort={"aenderungen": [
        {"art": "festlegung_setzen", "wert": "ort: the market square"},
    ]})

    erkenner.laufe(klm, TelegramAttrappe(), conn, einst, 1)

    bereiche = {z["bereich"] for z in repo.festlegungen(conn, 1)}
    assert bereiche == {"struktur", "ort"}

from datetime import datetime, timedelta, timezone

from interview_theater import cothinker_status as cs

JETZT = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)


def vor(sekunden):
    return (JETZT - timedelta(seconds=sekunden)).isoformat()


def test_denkt_wenn_lauf_seit_frisch_ist():
    lauf_seit = vor(10)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=lauf_seit,
        segment_status=None,
        segment_schnittgrund=None,
        segment_empfangen_am=None,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis == (cs.ZUSTAND_DENKT, lauf_seit)


def test_denkt_faellt_weg_nach_timeout():
    lauf_seit = vor(200)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=lauf_seit,
        segment_status=None,
        segment_schnittgrund=None,
        segment_empfangen_am=None,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis is None


def test_transkribiert_bei_status_laeuft():
    segment_empfangen_am = vor(5)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="laeuft",
        segment_schnittgrund=None,
        segment_empfangen_am=segment_empfangen_am,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis == (cs.ZUSTAND_TRANSKRIBIERT, segment_empfangen_am)


def test_transkribiert_bei_status_empfangen():
    segment_empfangen_am = vor(3)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="empfangen",
        segment_schnittgrund=None,
        segment_empfangen_am=segment_empfangen_am,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis == (cs.ZUSTAND_TRANSKRIBIERT, segment_empfangen_am)


def test_hoert_wenn_segment_fertig_und_frisch():
    segment_empfangen_am = vor(30)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="fertig",
        segment_schnittgrund="dauer",
        segment_empfangen_am=segment_empfangen_am,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis == (cs.ZUSTAND_HOERT, segment_empfangen_am)


def test_hoert_faellt_weg_wenn_schnittgrund_ende_ist():
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="fertig",
        segment_schnittgrund="ende",
        segment_empfangen_am=vor(30),
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis is None


def test_hoert_faellt_weg_wenn_zu_alt():
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="fertig",
        segment_schnittgrund="dauer",
        segment_empfangen_am=vor(70),
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis is None


def test_schweigt_wenn_neueste_karte_schweigen_traegt():
    neueste_karte_seit = vor(5)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status=None,
        segment_schnittgrund=None,
        segment_empfangen_am=None,
        neueste_karte_schweigen=True,
        neueste_karte_seit=neueste_karte_seit,
    )
    assert ergebnis == (cs.ZUSTAND_SCHWEIGT, neueste_karte_seit)


def test_kein_status_ohne_jeden_hinweis():
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status=None,
        segment_schnittgrund=None,
        segment_empfangen_am=None,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis is None


def test_denkt_hat_vorrang_vor_hoert():
    lauf_seit = vor(10)
    segment_empfangen_am = vor(30)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=lauf_seit,
        segment_status="fertig",
        segment_schnittgrund="dauer",
        segment_empfangen_am=segment_empfangen_am,
        neueste_karte_schweigen=False,
        neueste_karte_seit=None,
    )
    assert ergebnis == (cs.ZUSTAND_DENKT, lauf_seit)


def test_transkribiert_hat_vorrang_vor_schweigt():
    segment_empfangen_am = vor(5)
    ergebnis = cs.leite_ab(
        jetzt=JETZT,
        lauf_seit=None,
        segment_status="laeuft",
        segment_schnittgrund=None,
        segment_empfangen_am=segment_empfangen_am,
        neueste_karte_schweigen=True,
        neueste_karte_seit=vor(1),
    )
    assert ergebnis == (cs.ZUSTAND_TRANSKRIBIERT, segment_empfangen_am)

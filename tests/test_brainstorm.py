from interview_theater import brainstorm


def test_kein_trigger_unter_der_zeichengrenze():
    assert not brainstorm.soll_reagieren(
        unreagierte_zeichen=1199, sekunden_seit_letzter_reaktion=200,
        letzter_schnittgrund="pause", ist_abschluss=False,
    )


def test_trigger_bei_genug_zeichen_abstand_und_pausenschnitt():
    assert brainstorm.soll_reagieren(
        unreagierte_zeichen=1200, sekunden_seit_letzter_reaktion=90,
        letzter_schnittgrund="pause", ist_abschluss=False,
    )


def test_kein_trigger_bei_kappen_schnitt():
    assert not brainstorm.soll_reagieren(
        unreagierte_zeichen=5000, sekunden_seit_letzter_reaktion=200,
        letzter_schnittgrund="cap", ist_abschluss=False,
    )


def test_kein_trigger_ohne_schnittgrund():
    assert not brainstorm.soll_reagieren(
        unreagierte_zeichen=5000, sekunden_seit_letzter_reaktion=200,
        letzter_schnittgrund=None, ist_abschluss=False,
    )


def test_kein_trigger_zu_kurz_nach_der_letzten_reaktion():
    assert not brainstorm.soll_reagieren(
        unreagierte_zeichen=5000, sekunden_seit_letzter_reaktion=10,
        letzter_schnittgrund="pause", ist_abschluss=False,
    )


def test_abschluss_triggert_schon_ab_150_zeichen_ohne_pausenschnitt():
    assert brainstorm.soll_reagieren(
        unreagierte_zeichen=150, sekunden_seit_letzter_reaktion=5,
        letzter_schnittgrund="cap", ist_abschluss=True,
    )


def test_abschluss_ohne_trigger_unter_150():
    assert not brainstorm.soll_reagieren(
        unreagierte_zeichen=149, sekunden_seit_letzter_reaktion=5,
        letzter_schnittgrund="cap", ist_abschluss=True,
    )


def test_abschluss_braucht_keinen_schnittgrund():
    assert brainstorm.soll_reagieren(
        unreagierte_zeichen=150, sekunden_seit_letzter_reaktion=0,
        letzter_schnittgrund=None, ist_abschluss=True,
    )


def test_min_zeichen_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "500")
    assert brainstorm.min_zeichen() == 500


def test_min_abstand_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "30")
    assert brainstorm.min_abstand_s() == 30


def test_min_zeichen_bei_abschluss_kommt_aus_der_umgebung(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "75")
    assert brainstorm.min_zeichen_bei_abschluss() == 75


def test_ungueltige_umgebungswerte_fallen_auf_die_vorgabe_zurueck(monkeypatch):
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN", "nicht-numerisch")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ABSTAND_S", "-5")
    monkeypatch.setenv("IT_BRAINSTORM_MIN_ZEICHEN_BEI_ABSCHLUSS", "")
    assert brainstorm.min_zeichen() == brainstorm.VORGABE_MIN_ZEICHEN
    assert brainstorm.min_abstand_s() == brainstorm.VORGABE_MIN_ABSTAND_S
    assert (
        brainstorm.min_zeichen_bei_abschluss()
        == brainstorm.VORGABE_MIN_ZEICHEN_BEI_ABSCHLUSS
    )

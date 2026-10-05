from simulation import browser_leitbilder as lb

TOKEN = "AbC123tokenXYZ"


def test_sauberer_text_ist_erlaubt():
    assert lb.pruefe_bild("Phase 1 of 7 · Terms. Start listening.", TOKEN, False) is None


def test_token_link_fehler_und_deutschreste_werden_abgelehnt():
    assert lb.pruefe_bild(f"open /g/{TOKEN}", TOKEN, False) == "token"
    assert lb.pruefe_bild("see http://x", TOKEN, False) == "http"
    assert lb.pruefe_bild("ok", TOKEN, True) == "fehler"
    for rest in ("Begriffe für", "Straße", "Haus und Hof", "das ist nicht gut",
                 "der Plan", "die Gruppe"):
        assert lb.pruefe_bild(rest, TOKEN, False) == "deutsch", rest


def test_unterschriften_decken_die_leitstationen_ab():
    assert set(lb.UNTERSCHRIFTEN) == {
        (1, "start"), (1, "eintritt"), (1, "kalibrierung"), (1, "zuhoeren"),
        (1, "cothinker"), (1, "uebergang"), (2, "eintritt"), (2, "arbeit"),
        (2, "ergebnis"), (2, "uebergang")}
    assert all(lb.pruefe_bild(t, TOKEN, False) is None for t in lb.UNTERSCHRIFTEN.values())

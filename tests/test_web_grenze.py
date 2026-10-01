"""Das gleitende Fenster, ohne HTTP.

Ein fester Minuteneimer liesse 40 Anfragen in zwei Sekunden durch, wenn sie
auf der Minutengrenze liegen. Deshalb Zeitstempel und kein Zaehler.

Die Zeit kommt als Parameter herein -- kein sleep in einem Test, der sonst
eine Minute dauerte.
"""

import threading

import pytest

from interview_theater import web_grenze


@pytest.fixture(autouse=True)
def leer():
    web_grenze.vergiss()
    yield
    web_grenze.vergiss()


def test_bis_zur_grenze_frei_danach_gesperrt():
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0) == 0, i
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0) > 0


def test_gesperrte_anfragen_zaehlen_nicht_mit():
    """Sonst schoebe eine Flut das Fenster vor sich her und die Gruppe kaeme
    auch nach einer Minute nicht wieder hinein."""
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    for _ in range(100):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1005.0)
    assert web_grenze.pruefe(
        web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0 + web_grenze.NACHRICHTEN_FENSTER_S + 1
    ) == 0


def test_das_fenster_gleitet():
    for i in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0 + i)
    # Der aelteste Eintrag (t=1000) faellt bei t=1061 heraus -> genau einer frei.
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1061.0) == 0
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1061.0) > 0


def test_retry_after_zeigt_auf_den_naechsten_freien_platz():
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    warte = web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1010.0)
    assert warte == web_grenze.NACHRICHTEN_FENSTER_S - 10


def test_zwei_gruppen_stoeren_sich_nicht():
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    assert web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 2, jetzt=1000.0) == 0


def test_zwei_toepfe_stoeren_sich_nicht():
    """Uploads kosten Platte und einen Whisper-Aufruf, Nachrichten einen
    Modellaufruf -- zwei Ressourcen, zwei Zaehler."""
    for _ in range(web_grenze.NACHRICHTEN_JE_MINUTE):
        web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
    assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0) == 0


def test_die_uploadgrenze_deckt_eine_volle_stunde_interview():
    """45-Sekunden-Segmente: 3600/45 = 80 Uploads je Stunde. Die Grenze muss
    darueber liegen, sonst schneidet sie ein Interview ab."""
    assert web_grenze.UPLOADS_JE_STUNDE > 3600 // 45
    for i in range(web_grenze.UPLOADS_JE_STUNDE):
        assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0 + i) == 0
    assert web_grenze.pruefe(web_grenze.TOPF_UPLOAD, 1, jetzt=1000.0) > 0


def test_unbekannter_topf_wirft():
    with pytest.raises(KeyError):
        web_grenze.pruefe("gibtsnicht", 1)


def test_nebenlaeufig_wird_nicht_ueberzaehlt():
    """ThreadingHTTPServer bindet je Verbindung einen Thread. Ohne Sperre
    liessen 40 gleichzeitige Anfragen mehr als 20 durch."""
    frei = []
    sperre = threading.Lock()

    def laufe():
        ergebnis = web_grenze.pruefe(web_grenze.TOPF_NACHRICHT, 1, jetzt=1000.0)
        with sperre:
            frei.append(ergebnis)

    faeden = [threading.Thread(target=laufe) for _ in range(200)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()
    assert frei.count(0) == web_grenze.NACHRICHTEN_JE_MINUTE


def test_web_grenze_importiert_kein_projektmodul():
    """Wie vorschlagssperre.py: reine Standardbibliothek, damit es von jeder
    Seite importierbar bleibt und nie einen Zyklus baut."""
    import ast
    from pathlib import Path

    quelle = Path(web_grenze.__file__).read_text(encoding="utf-8")
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.ImportFrom):
            assert not (knoten.module or "").startswith("interview_theater"), knoten.module
            assert knoten.level == 0
        if isinstance(knoten, ast.Import):
            for name in knoten.names:
                assert not name.name.startswith("interview_theater"), name.name

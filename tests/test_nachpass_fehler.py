"""Ein gescheiterter Nachpass ist fuer die Gruppe unsichtbar (01.10.2026,
Karte R, Schlussreview I1).

Der Nachpass laeuft im selben ``try`` wie der Schreiblauf. Reisst er
ausserhalb seines eigenen Modellaufrufs (Befund, Zitate lesen, Rueckschreiben,
``lege_szenen_an``), landete der Fehler im Handler des Schreiblaufs -- und die
Gruppe bekaeme "fehlgeschlagen" ueber einen Text, der schon gespeichert und
verschickt ist. Der Nachpass ist eine Zugabe (SPEC § 11.1): sein Fehler ist
ein Vorfall, keine Zeile im Chat.
"""

import pytest

from interview_theater import kurzgeschichte, nachpass, szene

from test_knoepfe import TelegramAttrappe
from test_nachpass import (  # noqa: F401  (Fixtures: szene7 braucht padua)
    LLMAttrappe, KURZ, _vorfallarten, padua, szene7,
)
from test_nachpass_prosa import (  # noqa: F401
    LLMAttrappe as ProsaAttrappe, KURZ as PROSA_KURZ, prosa6,
)


@pytest.fixture
def tg():
    return TelegramAttrappe()


def _reisst(*_a, **_k):
    raise RuntimeError("Datenbank beschaeftigt")


def test_szene_ein_reissender_nachpass_meldet_keinen_fehler(
    szene7, tg, einst, monkeypatch,  # noqa: F811
):
    monkeypatch.setattr(nachpass, "nach_szene", _reisst)
    klm = LLMAttrappe(KURZ)
    thread = szene.starte(szene7, tg, klm, einst, 1, "Schreib Szene 1")
    thread.join(timeout=20)

    arten = _vorfallarten(szene7)
    assert "szene_fehlgeschlagen" not in arten
    assert nachpass.VORFALL_FEHLER in arten
    assert not any(text == szene.T._TEXT_FEHLER for _c, text in tg.gesendet)
    assert szene._sperre_fuer(1).locked() is False


def test_geschichte_ein_reissender_nachpass_meldet_keinen_fehler(
    prosa6, tg, einst, monkeypatch,  # noqa: F811
):
    monkeypatch.setattr(nachpass, "nach_geschichte", _reisst)
    klm = ProsaAttrappe(PROSA_KURZ)
    thread = kurzgeschichte.starte(prosa6, tg, klm, einst, 1)
    thread.join(timeout=20)

    arten = _vorfallarten(prosa6)
    assert "kurzgeschichte_fehlgeschlagen" not in arten
    assert nachpass.VORFALL_FEHLER in arten
    assert not any(text == kurzgeschichte.T._TEXT_FEHLER
                   for _c, text in tg.gesendet)
    assert kurzgeschichte._sperre_fuer(1).locked() is False

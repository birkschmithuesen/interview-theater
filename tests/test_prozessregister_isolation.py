"""Reproduktion t_b1770186: ``szenenfolge._regienotiz_erwartet`` ist ein
Merker im Prozess, nicht in der Datenbank (bewusst, siehe dort) -- fast alle
Tests teilen ``chat_id = 1`` (``tests/conftest.py``, ``_begriffe_im_zug_leer``).
Ohne einen Reset zwischen Tests hinterlaesst ein Test, der
``szenenfolge.erwarte_regienotiz`` setzt und nie konsumiert, eine Erwartung,
die der naechste Test auf chat_id 1 sieht -- gemessen am 10.10.2026:
``tests/test_knoepfe_wirkung_p67_italienisch.py`` (setzt die Erwartung ueber
``_wirkung_szene_anders``, konsumiert sie nie) macht danach
``tests/test_kostendeckel.py::test_der_deckel_gilt_im_telegram_kanal`` rot,
weil ``ablauf._szene_hat_vorfahrt`` die geerbte Erwartung findet und den
Gespraechszug in den Szenenlauf statt in den Kostendeckel-Check lenkt.

Zwei eigene Testfunktionen (keine lokale Aufraeum-Fixture wie in
``test_szenenfolge.py``), damit genau diese Prozessleiche sichtbar wird."""

from interview_theater import szenenfolge

CHAT = 1


def test_a_hinterlaesst_eine_erwartete_regienotiz_ohne_sie_zu_konsumieren():
    szenenfolge.erwarte_regienotiz(CHAT, 1)


def test_b_sieht_keine_regienotiz_aus_test_a():
    assert szenenfolge.nimm_regienotiz(CHAT) is None

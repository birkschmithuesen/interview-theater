"""Regression (Karte t_50fea3e6): zwei Testdateien hintereinander in genau
dieser Reihenfolge duerfen sich nicht gegenseitig vergiften.

``tests/test_knoepfe_wirkung_p67_italienisch.py`` ruft zweimal
``wirkung._wirkung_szene_anders(conn, d)`` mit ``chat_id=1`` auf, und die
Wirkung merkt sich ueber ``szenenfolge.erwarte_regienotiz`` eine erwartete
Regie-Notiz fuer diese ``chat_id`` -- bewusst im Prozess, nicht in der
Datenbank (``szenenfolge._regienotiz_erwartet``). Ohne Aufraeumen ueberlebte
der Merkposten das Testende und liess den naechsten Test mit derselben
``chat_id`` (``tests/test_kostendeckel.py``, ``CHAT = 1``) in
``ablauf._szene_hat_vorfahrt`` einen Szenenauftrag statt der
Kostendeckel-Pause ausloesen.

Lief isoliert immer gruen, nur in dieser Reihenfolge rot -- deshalb ein
eigener Subprozess-Lauf statt eines In-Prozess-Tests: ein In-Prozess-Test
teilt sich den Interpreter mit dem Rest der Suite und wuerde den Leck-Zustand
selbst wieder einschleppen."""

import subprocess
import sys


def test_italienisch_dann_kostendeckel_bleibt_gruen():
    ergebnis = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-m", "not dortmund",
            "tests/test_knoepfe_wirkung_p67_italienisch.py",
            "tests/test_kostendeckel.py",
        ],
        capture_output=True,
        text=True,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr

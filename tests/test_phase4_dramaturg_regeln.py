"""Phase 4: drei Dramaturgen-Regeln hart im Prompt (07.10.2026, Birk).

Reines Prompt-Hardening, aus dem Formberater-Branch nur diese drei Regeln
uebernommen, ohne den Formberater-Block und ohne die (bereits bestehende)
Phase-4/5-Szenentext-Grenze: (1) dramaturgisches Fachwissen, kritische
Rueckfrage nur bei echtem Bedarf, eine bewusste aesthetische Entscheidung der
Gruppe wird respektiert; (2) das konkrete Beispiel der Gruppe geht eigenen
Richtungen vor; (3) nichts von dir als ihres.
"""

import pytest

from interview_theater import kontext, workshop


@pytest.fixture
def padua(monkeypatch):
    monkeypatch.delenv(workshop.BASIS_VARIABLE, raising=False)
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    yield
    workshop.vergiss()


def _flach(text):
    return " ".join(text.split())


def test_padua_phase_4_traegt_die_neuen_regeln(padua):
    system = _flach(kontext.system("gruppe1", 4))
    # 1. Rolle: einordnen, kritisch nur bei Bedarf, bewusste Entscheidung respektieren
    assert "You also bring the background of a dramaturge" in system
    assert "not a duty in every turn" in system
    assert "you don't steer it back to a familiar pattern such as a rising arc" in system
    # 2. Das konkrete Beispiel der Gruppe geht vor
    assert "The group's own concrete example comes first." in system
    assert "Three directions of your own only when the group has no idea of its own yet." in system
    assert "never three entirely new overall directions" in system
    # 3. Nichts von dir als ihres
    assert "Never attribute to the group what you added yourself." in system


def test_deutsche_fassung_traegt_dieselben_regeln():
    system = _flach(kontext.system("gruppe4", 4))
    assert "Du bringst auch dramaturgisches Fachwissen mit" in system
    assert "Kritisch nachfragen nur bei echtem Bedarf" in system
    assert "Das konkrete Beispiel der Gruppe geht vor." in system
    assert "Drei eigene Richtungen nur, wenn die Gruppe noch keine eigene Idee hat." in system
    assert "Nichts von dir als ihres." in system

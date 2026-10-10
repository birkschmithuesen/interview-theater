"""Problem 1/2 (Karte t_fd88600b): Ort, Besetzung und Karte schreibt NUR
``stueck.py``. Rot, sobald ein Modul wieder einen eigenen Weg zu derselben
Tatsache baut."""

import ast
import pathlib

import pytest

from interview_theater import repo

NUR_STUECK = {"setze_szenenort", "setze_besetzung", "setze_szene_figuren",
              "aktualisiere_szenenkarte", "setze_szenenkarte", "merke_karte_verlauf",
              "lege_offene_frage_an", "setze_frage_status", "nummeriere_szenen"}
#: Ausnahmen mit Grund: szenenkarte schreibt Dialog-/Klaerungsstand und den
#: Verlauf "uebersprungen" (Ablaufzustand, keine Tatsache).
AUSNAHMEN = {("szenenkarte.py", "merke_karte_verlauf")}


def _funde_in(quelltext: str, dateiname: str) -> list[str]:
    """Aufrufe der Tatsachen-Schreiber in einem Quelltext -- auch ueber
    Umbenennung (``from interview_theater import repo as r``), direkten
    Import (``from interview_theater.repo import setze_szenenort``) und
    ``getattr(repo, "setze_szenenort")``."""
    baum = ast.parse(quelltext)
    repo_namen = {"repo"}
    funde = []
    for k in ast.walk(baum):
        if isinstance(k, ast.ImportFrom) and k.module == "interview_theater":
            repo_namen |= {a.asname or a.name for a in k.names if a.name == "repo"}
        elif isinstance(k, ast.Import):
            repo_namen |= {a.asname for a in k.names
                           if a.name == "interview_theater.repo" and a.asname}
        elif isinstance(k, ast.ImportFrom) and k.module == "interview_theater.repo":
            funde += [f"{dateiname}:{k.lineno} from repo import {a.name}"
                      for a in k.names if a.name in NUR_STUECK or a.name == "*"]
    for k in ast.walk(baum):
        if (isinstance(k, ast.Attribute) and isinstance(k.value, ast.Name)
                and k.value.id in repo_namen and k.attr in NUR_STUECK
                and (dateiname, k.attr) not in AUSNAHMEN):
            funde.append(f"{dateiname}:{k.lineno} repo.{k.attr}")
        elif (isinstance(k, ast.Call) and isinstance(k.func, ast.Name)
              and k.func.id == "getattr" and len(k.args) >= 2
              and isinstance(k.args[0], ast.Name) and k.args[0].id in repo_namen
              and isinstance(k.args[1], ast.Constant) and k.args[1].value in NUR_STUECK):
            funde.append(f"{dateiname}:{k.lineno} getattr(repo, {k.args[1].value!r})")
    return funde


def test_nur_stueck_ruft_die_tatsachen_schreiber():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    funde = []
    for datei in wurzel.rglob("*.py"):
        if datei.name in {"stueck.py", "repo.py", "db.py"}:
            continue
        funde += _funde_in(datei.read_text(encoding="utf-8"), datei.name)
    assert funde == []


@pytest.mark.parametrize("quelltext", [
    "from interview_theater import repo\nrepo.setze_szenenort(c, 1, 'x')",
    "from interview_theater import repo as r\nr.setze_szenenort(c, 1, 'x')",
    "import interview_theater.repo as r\nr.setze_besetzung(c, 1, 1, [])",
    "from interview_theater.repo import setze_szenenort",
    "from interview_theater import repo\ngetattr(repo, 'nummeriere_szenen')",
])
def test_waechter_erkennt_umwege(quelltext):
    assert _funde_in(quelltext, "x.py"), quelltext


def test_ort_ist_ueber_setze_szenenfeld_gesperrt(conn):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    with pytest.raises(ValueError):
        repo.setze_szenenfeld(conn, sid, "ort", "Bar")


def test_ort_ist_im_szenenabgleich_gesperrt(conn):
    assert "ort" in repo.NUR_UEBER_STUECK
    with pytest.raises(ValueError):
        repo.gleiche_szenenfolge_ab(conn, 1, [{"ort": "Bar"}])

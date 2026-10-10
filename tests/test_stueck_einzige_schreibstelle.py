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


def test_nur_stueck_ruft_die_tatsachen_schreiber():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    funde = []
    for datei in wurzel.rglob("*.py"):
        if datei.name in {"stueck.py", "repo.py", "db.py"}:
            continue
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if (isinstance(knoten, ast.Attribute) and isinstance(knoten.value, ast.Name)
                    and knoten.value.id == "repo" and knoten.attr in NUR_STUECK
                    and (datei.name, knoten.attr) not in AUSNAHMEN):
                funde.append(f"{datei.relative_to(wurzel)}:{knoten.lineno} repo.{knoten.attr}")
    assert funde == []


def test_ort_ist_ueber_setze_szenenfeld_gesperrt(conn):
    sid = repo.stelle_szene_sicher(conn, 1, 1)
    with pytest.raises(ValueError):
        repo.setze_szenenfeld(conn, sid, "ort", "Bar")


def test_ort_ist_im_szenenabgleich_gesperrt(conn):
    assert "ort" in repo.NUR_UEBER_STUECK
    with pytest.raises(ValueError):
        repo.gleiche_szenenfolge_ab(conn, 1, [{"ort": "Bar"}])

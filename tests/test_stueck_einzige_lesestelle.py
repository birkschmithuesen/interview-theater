"""Problem 1 (Karte t_fd88600b): das Karten-JSON liest NUR das Stueckmodell
(``stueck.karte`` / ``web_daten`` ueber ``stueck_sicht``). Ein Leser, der
``roh_karte_von`` direkt nimmt, saehe wieder eine zweite Wahrheit."""

import pathlib
import re

ERLAUBT = {"stueck.py", "szenenkarte.py", "web_daten.py", "stagescript.py", "ueberarbeitung.py"}
# stagescript/ueberarbeitung: nur fuer ``typ`` (kein Strukturfeld), siehe Plan Task 9.


def test_niemand_liest_das_rohe_karten_json():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    treffer = []
    for datei in wurzel.rglob("*.py"):
        text = datei.read_text(encoding="utf-8")
        if re.search(r"\bkarte_von\(", text):
            treffer.append(f"{datei.name}: karte_von")
        if "roh_karte_von(" in text and datei.name not in ERLAUBT:
            treffer.append(f"{datei.name}: roh_karte_von")
    assert treffer == []


def test_typ_leser_nutzen_kein_strukturfeld():
    wurzel = pathlib.Path(__file__).resolve().parents[1] / "interview_theater"
    for name in ("stagescript.py", "ueberarbeitung.py"):
        for zeile in (wurzel / name).read_text(encoding="utf-8").splitlines():
            if "roh_karte_von(" in zeile:
                assert not re.search(r"\b(ort|wer|fragen)\b", zeile), zeile

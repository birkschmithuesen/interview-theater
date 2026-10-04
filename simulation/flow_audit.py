"""Flow-Audit (Padua Flow Audit, 04.10.2026) -- Schicht 1, Phase 1+2.

Anlass der Karte: der Erkenner (``interview_theater/erkenner.py``) und die
Knopfflaeche (``interview_theater/knoepfe/texte.py``) wachsen unabhaengig
voneinander -- wird fuer eine Handlung nur ein Knopf gebaut und nie ein
Erkenner-Intent (oder umgekehrt), ist der Chat fuer genau diese Handlung
ein toter Weg, und nichts im bestehenden Testlauf meldet das: die
Korpus-Faelle (``tests/test_korpus.py``) pruefen, ob ein Intent *richtig*
erkannt wird, nicht, ob fuer eine Handlung ueberhaupt einer existiert.

Dieses Modul ist **Schicht 1**: statisch, ohne Modellaufruf, laeuft in
pytest (``tests/test_flow_abdeckung.py``). Es vergleicht die von Hand
gepflegte Liste typischer Handlungen je Phase (``simulation/
flow_erwartungen.toml``) mechanisch gegen den Code: hat eine Handlung, die
per Chat ankommen soll, einen Erkenner-Intent (``erkenner.ARTEN``)? Gibt es
ueberhaupt einen Weg -- Intent oder Knopf?

**Geltungsbereich dieser Fassung: ausschliesslich Phase 1 (Begriffe/Terms)
und Phase 2 (Fragen/Questions).** Die Karte, aus der dieses Modul stammt,
grenzt den Umfang bewusst so ein -- eine Erwartungsliste fuer Phase 3-7
waere an einem anderen Codestand entstanden (eine aeltere Fassung existiert
als Referenz unter ``.flow_audit_ref/`` und beschreibt einen Codestand vor
dem Phase-1/2-Umbau; sie ist nicht mehr gueltig und wird hier nicht
fortgeschrieben).

Drei Befundarten:
    - ``sackgasse``           -- weder Intent noch Knopf: kein Weg.
    - ``toter_gespraechsweg`` -- nur der Knopf wirkt, der Chat soll es auch
      koennen (``weg`` ist ``chat`` oder ``beides``).
    - ``geist``               -- die Erwartungsliste nennt einen Intent oder
      Knopf, den es im Code nicht (mehr) gibt -- die Liste ist veraltet,
      nicht der Code.

**Bekannter blinder Fleck dieser Schicht** (siehe die Zeilen in
``flow_erwartungen.toml`` mit ``beleg``-Hinweis darauf): die Pruefung kennt
nur zwei Mechanismen, mit denen eine Handlung per Chat wirken kann --
einen Erkenner-Intent (``erkenner.ARTEN``) oder einen Knopf
(``knoepfe.texte.ART_*``). Phase 2 hat daneben mindestens zwei weitere,
echte Chat-Mechanismen, die keines von beiden sind: einen vom
Gespraechsmodell selbst erzeugten Markerblock
(``VORSCHLAG EIGENE FRAGEN:``, abgefangen in
``interview_theater/knoepfe/basis.py``) und eine deterministische
Text-Weiche ohne Modellaufruf
(``interview_theater/ablauf.py::_war_die_erwartete_antwort`` ->
``knoepfe.fragen.nimm_offene_frage_text``). Fuer Handlungen, die NUR ueber
einen dieser beiden Wege laufen, meldet diese Schicht einen Befund
(``sackgasse`` bzw. ``toter_gespraechsweg``), obwohl der Chat tatsaechlich
funktioniert -- das ist eine Einschraenkung des statischen Modells, keine
Regression im Code. Die betroffenen Zeilen tragen das in ihrem ``beleg``
ausdruecklich, und die Tests in ``tests/test_flow_abdeckung.py`` benennen
sie einzeln, statt sie stillschweigend aus der Liste zu lassen. Schicht 2
(ein dynamischer Persona-Lauf gegen echte Modelle) koennte diesen blinden
Fleck schliessen, ist aber nicht Teil dieser Karte.

Die von Hand gepflegte Liste ist die einzige Instanz, gegen die mechanisch
geprueft wird -- eine zweite, aus dem Code erratene Liste waere der erste
Stand, der ausschert (dieselbe Regel wie bei
``interview_theater/fehlstellen.py``/``roadmap.py``).
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from interview_theater import erkenner
from interview_theater.knoepfe import texte as knopf_texte

#: Die von Hand gepflegte Liste, nur Phase 1+2.
ERWARTUNGEN_PFAD = Path(__file__).resolve().parent / "flow_erwartungen.toml"

#: Sortierung der Befundliste -- schwerstes zuerst.
SCHWERE_RANG = {"sackgasse": 0, "toter_gespraechsweg": 1, "geist": 2}

SCHWERE_TEXT = {
    "sackgasse": "Sackgasse (kein Intent, kein Knopf)",
    "toter_gespraechsweg": "Toter Gespraechsweg (nur Knopf wirkt)",
    "geist": "Veraltete Erwartung (Intent/Knopf existiert nicht mehr)",
}


@dataclass(frozen=True)
class Handlung:
    phase: int
    aktion: str
    weg: str  # "chat" | "knopf" | "beides"
    intent: str  # "" oder "a|b"
    knopf: str  # "" oder "ART_A|ART_B"
    beleg: str


@dataclass(frozen=True)
class Befund:
    schwere: str
    phase: int
    aktion: str
    was_fehlt: str
    vorschlag: str
    beleg: str


def lade_erwartungen(pfad: Path = ERWARTUNGEN_PFAD) -> list[Handlung]:
    """Liest ``flow_erwartungen.toml``. Eine der beiden Phasen ohne
    Eintraege waere ein Zeichen, dass die Liste nicht mitgewachsen ist --
    kein stiller Fall (siehe ``test_erwartungsliste_deckt_phase_1_und_2_ab``)."""
    rohdaten = tomllib.loads(pfad.read_text(encoding="utf-8"))
    handlungen: list[Handlung] = []
    for schluessel, eintraege in rohdaten.get("phase", {}).items():
        phase = int(schluessel)
        for e in eintraege:
            handlungen.append(
                Handlung(
                    phase=phase,
                    aktion=e["aktion"],
                    weg=e["weg"],
                    intent=(e.get("intent") or "").strip(),
                    knopf=(e.get("knopf") or "").strip(),
                    beleg=(e.get("beleg") or "").strip(),
                )
            )
    return handlungen


def bekannte_intents() -> frozenset[str]:
    """Alle Erkenner-Intents, wie sie der Code heute kennt."""
    return frozenset(erkenner.ARTEN)


def bekannte_knoepfe() -> frozenset[str]:
    """Alle ``ART_*``-Konstanten aus ``knoepfe.texte`` -- die vollstaendige
    Knopfflaeche (``tests/test_knoepfe_struktur.py`` haelt bereits fest, dass
    jede ``ART_*`` einen Handler hat)."""
    return frozenset(n for n in dir(knopf_texte) if n.startswith("ART_"))


def _namen(feld: str) -> list[str]:
    return [n.strip() for n in feld.split("|") if n.strip()]


def pruefe(
    handlungen: list[Handlung] | None = None,
    intents: frozenset[str] | None = None,
    knoepfe: frozenset[str] | None = None,
) -> list[Befund]:
    """Die mechanische Pruefung. Nimmt Listen/Mengen als Parameter entgegen
    (statt sie selbst zu laden), damit ein Test sie fuer die Mutationsprobe
    austauschen kann, ohne Dateien oder Module anzufassen."""
    handlungen = lade_erwartungen() if handlungen is None else handlungen
    intents = bekannte_intents() if intents is None else intents
    knoepfe = bekannte_knoepfe() if knoepfe is None else knoepfe

    befunde: list[Befund] = []
    for h in handlungen:
        intent_namen = _namen(h.intent)
        knopf_namen = _namen(h.knopf)

        for name in intent_namen:
            if name not in intents:
                befunde.append(
                    Befund(
                        schwere="geist",
                        phase=h.phase,
                        aktion=h.aktion,
                        was_fehlt=f"Intent '{name}' steht in flow_erwartungen.toml, aber nicht in erkenner.ARTEN",
                        vorschlag="simulation/flow_erwartungen.toml korrigieren oder den Intent wiederherstellen",
                        beleg=h.beleg,
                    )
                )
        for name in knopf_namen:
            if name not in knoepfe:
                befunde.append(
                    Befund(
                        schwere="geist",
                        phase=h.phase,
                        aktion=h.aktion,
                        was_fehlt=f"Knopf '{name}' steht in flow_erwartungen.toml, aber nicht in knoepfe.texte",
                        vorschlag="simulation/flow_erwartungen.toml korrigieren oder den Knopf wiederherstellen",
                        beleg=h.beleg,
                    )
                )

        hat_intent = bool(intent_namen) and all(n in intents for n in intent_namen)
        hat_knopf = bool(knopf_namen) and all(n in knoepfe for n in knopf_namen)

        if not hat_intent and not hat_knopf:
            befunde.append(
                Befund(
                    schwere="sackgasse",
                    phase=h.phase,
                    aktion=h.aktion,
                    was_fehlt="kein Erkenner-Intent und kein Knopf",
                    vorschlag=f"Einen Weg fuer '{h.aktion}' bauen (Phase {h.phase})",
                    beleg=h.beleg,
                )
            )
        elif h.weg in ("chat", "beides") and not hat_intent and hat_knopf:
            befunde.append(
                Befund(
                    schwere="toter_gespraechsweg",
                    phase=h.phase,
                    aktion=h.aktion,
                    was_fehlt="kein Erkenner-Intent -- nur der Knopf wirkt",
                    vorschlag=f"Erkenner-Intent fuer '{h.aktion}' ergaenzen (Phase {h.phase})",
                    beleg=h.beleg,
                )
            )
    return sorted(befunde, key=lambda b: (SCHWERE_RANG[b.schwere], b.phase))


def matrix_text(handlungen: list[Handlung] | None = None) -> str:
    """Die Matrix aus Schicht 1 als Klartext -- fuer den Bericht."""
    handlungen = lade_erwartungen() if handlungen is None else handlungen
    zeilen = ["Phase | Weg | Aktion | Intent | Knopf", "---|---|---|---|---"]
    for h in sorted(handlungen, key=lambda h: h.phase):
        zeilen.append(
            f"{h.phase} | {h.weg} | {h.aktion} | {h.intent or '--'} | {h.knopf or '--'}"
        )
    return "\n".join(zeilen)


def befunde_text(befunde: list[Befund]) -> str:
    if not befunde:
        return "Keine Befunde."
    zeilen = []
    for b in befunde:
        zeilen.append(
            f"[{SCHWERE_TEXT[b.schwere]}] Phase {b.phase}: {b.aktion}\n"
            f"  Was fehlt: {b.was_fehlt}\n"
            f"  Vorschlag: {b.vorschlag}\n"
            f"  Beleg: {b.beleg}"
        )
    return "\n\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    befunde = pruefe()
    print("# Flow-Audit -- Schicht 1 (statisch, Phase 1+2)\n")
    print("## Befunde\n")
    print(befunde_text(befunde))
    print("\n\n## Matrix\n")
    print(matrix_text())
    rot = [b for b in befunde if b.schwere in ("sackgasse", "toter_gespraechsweg")]
    return 1 if rot else 0


if __name__ == "__main__":
    sys.exit(main())

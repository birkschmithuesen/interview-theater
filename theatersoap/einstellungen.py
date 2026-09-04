"""Konfiguration ausschliesslich ueber Umgebungsvariablen (siehe global-constraints.md)."""

import os
from dataclasses import dataclass

# Name der Umgebungsvariable -> Vorgabewert (None = Pflichtvariable)
_VORGABEWERTE = {
    "TS_BOT_TOKEN": None,
    "TS_BOT_NAME": None,
    "TS_DB": None,
    "TS_AUDIO": "audio",
    "TS_LLM_URL": None,
    "TS_LLM_KEY": None,
    "TS_LLM_MODELL": None,
    "TS_MODELL_ERKENNER": "google/gemma-4-31B-it",
    "TS_STT_BASIS": "https://api.infomaniak.com",
    "TS_STT_PRODUKT": None,
}


@dataclass(frozen=True)
class Einstellungen:
    bot_token: str
    bot_name: str
    db_pfad: str
    audio_verz: str
    llm_url: str
    llm_key: str
    llm_modell: str
    stt_basis: str
    stt_produkt: str
    # Modellwahl je Aufruf (SPEC-kontext-architektur.md § 4.3a): der
    # Absichtserkenner laeuft nicht mit dem Gespraechsmodell (llm_modell,
    # Kimi K2.6), sondern mit gemma -- gemessen 0 Falsch-Positive bei 25
    # Negativfaellen, 30/30 Treffer, 0,75 s. Nemotron-Nano faellt bewusst
    # NICHT als Vorgabewert, weil 6/27 Faelle falsch-positiv waren. Ans Ende
    # gestellt mit Vorgabewert, damit bestehende direkte Konstruktionsaufrufe
    # von Einstellungen(...) in anderen Testdateien ohne dieses Feld weiter
    # funktionieren.
    erkenner_modell: str = "google/gemma-4-31B-it"


def laden() -> Einstellungen:
    """Liest die neun Umgebungsvariablen. Wirft RuntimeError bei fehlender Pflichtvariable."""
    werte = {}
    fehlend = []
    for name, vorgabe in _VORGABEWERTE.items():
        wert = os.environ.get(name, vorgabe)
        if wert is None:
            fehlend.append(name)
        werte[name] = wert
    if fehlend:
        raise RuntimeError(
            f"Fehlende Umgebungsvariable(n): {', '.join(fehlend)}")

    return Einstellungen(
        bot_token=werte["TS_BOT_TOKEN"],
        bot_name=werte["TS_BOT_NAME"],
        db_pfad=werte["TS_DB"],
        audio_verz=werte["TS_AUDIO"],
        llm_url=werte["TS_LLM_URL"],
        llm_key=werte["TS_LLM_KEY"],
        llm_modell=werte["TS_LLM_MODELL"],
        stt_basis=werte["TS_STT_BASIS"],
        stt_produkt=werte["TS_STT_PRODUKT"],
        erkenner_modell=werte["TS_MODELL_ERKENNER"],
    )

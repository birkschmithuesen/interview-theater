"""Konfiguration ausschliesslich ueber Umgebungsvariablen (siehe global-constraints.md)."""

import os
from dataclasses import dataclass

# Name der Umgebungsvariable -> Vorgabewert (None = Pflichtvariable)
_VORGABEWERTE = {
    "IT_BOT_TOKEN": None,
    "IT_BOT_NAME": None,
    "IT_DB": None,
    "IT_AUDIO": "audio",
    "IT_LLM_URL": None,
    "IT_LLM_KEY": None,
    "IT_LLM_MODELL": None,
    "IT_MODELL_ERKENNER": "google/gemma-4-31B-it",
    "IT_STT_BASIS": "https://api.infomaniak.com",
    "IT_STT_PRODUKT": None,
    # Oeffentliche Basis-URL der Weboberflaeche; leer = kein Link im Chat.
    "IT_WEB_URL": "https://lab.artesmobiles.art/theatersoap",
    # Szenen-Aufruf (05.09.2026, Birk): "infomaniak" (Vorgabe, Kimi mit
    # Reasoning) oder "claude" (Opus ueber den lokalen Proxy -- dann geht
    # dieser eine Aufruf in die USA, und die Gruppe wird vorher gewarnt).
    "IT_SZENE_ANBIETER": "infomaniak",
    "IT_SZENE_URL": "http://127.0.0.1:28764/v1/messages",
    "IT_SZENE_MODELL": "claude-opus-5",
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
    web_url: str = ""
    # Modellwahl je Aufruf (SPEC-kontext-architektur.md § 4.3a): der
    # Absichtserkenner laeuft nicht mit dem Gespraechsmodell (llm_modell,
    # Kimi K2.6), sondern mit gemma -- gemessen 0 Falsch-Positive bei 25
    # Negativfaellen, 30/30 Treffer, 0,75 s. Nemotron-Nano faellt bewusst
    # NICHT als Vorgabewert, weil 6/27 Faelle falsch-positiv waren. Ans Ende
    # gestellt mit Vorgabewert, damit bestehende direkte Konstruktionsaufrufe
    # von Einstellungen(...) in anderen Testdateien ohne dieses Feld weiter
    # funktionieren.
    erkenner_modell: str = "google/gemma-4-31B-it"
    szene_anbieter: str = "infomaniak"
    szene_url: str | None = None
    szene_modell: str | None = None


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
        bot_token=werte["IT_BOT_TOKEN"],
        bot_name=werte["IT_BOT_NAME"],
        db_pfad=werte["IT_DB"],
        audio_verz=werte["IT_AUDIO"],
        llm_url=werte["IT_LLM_URL"],
        llm_key=werte["IT_LLM_KEY"],
        llm_modell=werte["IT_LLM_MODELL"],
        stt_basis=werte["IT_STT_BASIS"],
        stt_produkt=werte["IT_STT_PRODUKT"],
        web_url=(werte["IT_WEB_URL"] or "").rstrip("/"),
        erkenner_modell=werte["IT_MODELL_ERKENNER"],
        szene_anbieter=(werte["IT_SZENE_ANBIETER"] or "infomaniak").lower(),
        szene_url=werte["IT_SZENE_URL"],
        szene_modell=werte["IT_SZENE_MODELL"],
    )

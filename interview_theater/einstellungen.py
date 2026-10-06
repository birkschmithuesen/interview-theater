"""Konfiguration ausschliesslich ueber Umgebungsvariablen (siehe global-constraints.md)."""

import os
from dataclasses import dataclass

#: Welcher Kanal den Bot bedient (30.09.2026, Karte Padua A2).
#: ``telegram`` ist die Vorgabe, und ohne die Variable ist alles wie vorher
#: (E1: Telegram bleibt Plan B).
KANAL_TELEGRAM = "telegram"
KANAL_WEB = "web"
KANAELE = (KANAL_TELEGRAM, KANAL_WEB)

#: Wie lang ein Aufnahmesegment im Browser ist (Millisekunden). Jedes Segment
#: ist ein eigener MediaRecorder-Lauf und damit eine vollstaendige Datei --
#: eine Zeitscheibe allein ist nicht dekodierbar. 45 s sind der Kompromiss:
#: Netz weg oder Tab zu verliert hoechstens 45 Sekunden, und ein Interview
#: von zehn Minuten kostet dreizehn Uploads statt einem grossen.
#: Der Browsertest setzt die Variable kurz (tests/e2e).
VORGABE_SEGMENT_MS = 45_000

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
    "IT_KANAL": KANAL_TELEGRAM,
    # Die eine Gruppe, die ein Web-Bot-Prozess bedient. Pflicht, sobald
    # IT_KANAL=web -- geprueft in laden().
    "IT_WEB_CHAT_ID": "",
    "IT_WEB_SEGMENT_MS": str(VORGABE_SEGMENT_MS),
    # Tagesdeckel je Gruppe ueber alle bezahlten Modellaufrufe (Karte Padua
    # S, 30.09.2026). Danach pausiert der Bot bis Mitternacht -- empfangen
    # und speichern laeuft weiter.
    "IT_KOSTEN_DECKEL_CHF": "5.0",
    # Wonach "heute" sich richtet. Padua liegt in Italien; der Workshoptag
    # soll nicht um 02:00 Ortszeit umschlagen, weil UTC es tut.
    "IT_ZEITZONE": "Europe/Rome",
    # Internet-Recherche (Karte t_c5117c91): der Loopback-Such-Broker haelt
    # den Brave-Key, interview_theater ruft nur diese URL (Knowledge/Netzwerk-
    # Trennung, docs/refactoring-guidelines.md Punkt 7 im Profil-Repo).
    "IT_SUCHE_URL": "http://127.0.0.1:8789/search",
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
    kanal: str = KANAL_TELEGRAM
    web_chat_id: int | None = None
    web_segment_ms: int = VORGABE_SEGMENT_MS
    # Am Ende mit Vorgabewert, damit bestehende direkte Konstruktionsaufrufe
    # weiter gelten (wie bei erkenner_modell). Gelesen von kosten.deckel /
    # kosten.zeitzone.
    kosten_deckel_chf: float = 5.0
    zeitzone: str = "Europe/Rome"
    suche_url: str = "http://127.0.0.1:8789/search"


#: Variablen, die nur der Telegram-Kanal braucht. Im Web-Kanal gibt es keinen
#: Bot-Token -- ihn dort zur Pflicht zu machen hiesse, einen Platzhalter in
#: jede Env-Datei zu schreiben, und ein Platzhalter-Token ist nicht von einem
#: falschen zu unterscheiden.
_NUR_TELEGRAM = ("IT_BOT_TOKEN",)


def laden() -> Einstellungen:
    """Liest die Umgebungsvariablen. Wirft RuntimeError bei fehlender
    Pflichtvariable und bei einem unbekannten ``IT_KANAL``.

    Ein Tippfehler in ``IT_KANAL`` faellt NICHT still auf Telegram zurueck:
    dann sucht am Workshopmorgen jemand, warum der Browser nichts sieht.
    Fehlerbild am Workshoptag ist die teuerste Waehrung (wie beim
    Workshop-Profil, ``bot.main``)."""
    kanal = (os.environ.get("IT_KANAL") or KANAL_TELEGRAM).strip().lower()
    if kanal not in KANAELE:
        raise RuntimeError(
            f"IT_KANAL muss {' oder '.join(KANAELE)} sein, ist: "
            f"{os.environ.get('IT_KANAL')!r}"
        )

    werte = {}
    fehlend = []
    for name, vorgabe in _VORGABEWERTE.items():
        if kanal != KANAL_TELEGRAM and name in _NUR_TELEGRAM:
            vorgabe = ""
        wert = os.environ.get(name, vorgabe)
        if wert is None:
            fehlend.append(name)
        werte[name] = wert
    if fehlend:
        raise RuntimeError(
            f"Fehlende Umgebungsvariable(n): {', '.join(fehlend)}")

    roh_chat = (werte["IT_WEB_CHAT_ID"] or "").strip()
    if kanal == KANAL_WEB and not roh_chat:
        raise RuntimeError(
            "IT_KANAL=web braucht IT_WEB_CHAT_ID -- die eine Gruppe, die "
            "dieser Prozess bedient. Anlegen mit: "
            "python -m scripts.web_gruppe anlegen <bot_name>"
        )
    try:
        web_chat_id = int(roh_chat) if roh_chat else None
    except ValueError:
        raise RuntimeError(
            f"IT_WEB_CHAT_ID muss eine Zahl sein, ist: {roh_chat!r}") from None
    try:
        segment_ms = int(werte["IT_WEB_SEGMENT_MS"] or VORGABE_SEGMENT_MS)
    except ValueError:
        raise RuntimeError(
            f"IT_WEB_SEGMENT_MS muss eine Zahl sein, ist: "
            f"{werte['IT_WEB_SEGMENT_MS']!r}"
        ) from None

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
        kanal=kanal,
        web_chat_id=web_chat_id,
        web_segment_ms=segment_ms,
        kosten_deckel_chf=_zahl(werte["IT_KOSTEN_DECKEL_CHF"], 5.0),
        zeitzone=(werte["IT_ZEITZONE"] or "").strip() or "Europe/Rome",
        suche_url=(werte["IT_SUCHE_URL"] or "").strip() or "http://127.0.0.1:8789/search",
    )


def _zahl(roh, vorgabe: float) -> float:
    """Eine Kommazahl aus der Umgebung, mit Vorgabewert bei Unsinn.

    Ein Tippfehler in einer Env-Datei soll den Bot nicht am Workshoptag
    stoppen -- aber er soll auch nicht den Deckel abschalten. Deshalb faellt
    ein unlesbarer Wert auf die Vorgabe zurueck und nicht auf 'unendlich'."""
    try:
        wert = float(str(roh).strip())
    except (TypeError, ValueError):
        return vorgabe
    # "nan" und "inf" parst float() klaglos -- beide hiessen "kein Deckel".
    if wert != wert or wert in (float("inf"), float("-inf")):
        return vorgabe
    return wert

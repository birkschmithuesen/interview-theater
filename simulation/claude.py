"""Der Klient fuer die **Simulationsseite**: Claude Opus ueber einen lokalen
Proxy.

**Die Trennlinie.** Alles, was der Bot selbst tut -- Gespraech, Erkenner,
Verdichter, Journal, Sprachprofil, Szene -- laeuft weiter ueber Infomaniak
(``interview_theater/llm.py``). Das ist der Prueflung. Alles, was
*Simulation* ist -- die Stimmen, der Richter, die Erzeugung der fuenfzehn
Interviewdatensaetze -- laeuft hier: ueber Birks Abonnement, das nichts je
Aufruf kostet. Die beiden Wege duerfen nie zusammenfallen, sonst misst der
Simulator sein eigenes Modell mit.

**Anthropic-Messages-Format, nicht OpenAI.** Der Proxy nimmt genau das
entgegen, was auch die Anthropic-API nimmt: ``anthropic-version``-Header,
``{"model", "max_tokens", "system", "messages"}`` im Koerper, Antworttext in
``content[0].text``. Ein Authorization-Header wird bewusst **nicht** gesetzt
-- den setzt der Proxy selbst, und ein eigener wuerde ihn ueberschreiben.

**Kein erzwungenes JSON-Schema.** Der Endpunkt kennt zwar Werkzeuge, aber der
Simulator braucht sie nicht: der Richter wird um reines JSON gebeten und die
Antwort mit ``json.loads`` gelesen, mit genau einem Reparaturversuch (den
```json-Zaun entfernen, den Modelle gern um ein Objekt legen). Schlaegt auch
der fehl, ist das ein Fehler -- und der Richter vermerkt fuer diesen
Abschnitt "nicht bewertet", statt den ganzen Lauf mitzureissen.

**Kostenbuchhaltung.** Diese Aufrufe landen **nicht** in der Tabelle
``aufruf``: dort steht, was der Bot verbraucht hat, und ein Abonnementaufruf
mit 0 CHF darin waere eine Zeile, die zur Kostenrechnung nichts beitraegt und
die Aufrufzahl des Bots verfaelscht. Gezaehlt wird stattdessen hier
(``Claude.statistik``), und der Bericht fuehrt beide Seiten getrennt.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)

#: Der lokale Proxy. Ueberschreibbar mit ``IT_SIM_URL``.
URL_VORGABE = "http://127.0.0.1:28764/v1/messages"

#: Das Modell der Simulationsseite. Ueberschreibbar mit ``IT_SIM_MODELL``.
#: Opus, nicht ein kleineres: die Stimmen sollen wie Menschen schreiben und
#: der Richter soll lesen koennen, was zwischen zwei Nachrichten passiert ist
#: -- und das Abonnement kostet je Aufruf nichts.
MODELL_VORGABE = "claude-opus-5"

#: Pflicht-Header des Anthropic-Formats.
API_VERSION = "2023-06-01"

#: Zeitbudget eines einzelnen Aufrufs.
TIMEOUT_S = 120.0

#: Wartezeiten zwischen den Wiederholungen bei 429/5xx/Transportfehler, plus
#: Jitter. Macht bis zu vier Versuche insgesamt. Deutlich grosszuegiger als
#: ``llm.WARTEZEITEN``: ein 429 des Abonnements ist eine Minutengrenze, keine
#: Ueberlast -- kurz nachfassen bringt dort nichts.
WARTEZEITEN = (3.0, 10.0, 30.0)

#: Vorgabe fuer das Ausgabebudget eines Aufrufs.
MAX_TOKENS = 16_000  # 05.09.: 2.000 lief im Denken leer (nur thinking-Block); Deckel, kein Ziel


class ClaudeFehler(Exception):
    """Fehler beim Zugriff auf den Simulationsklienten."""


def url() -> str:
    return os.environ.get("IT_SIM_URL") or URL_VORGABE


def modell() -> str:
    return os.environ.get("IT_SIM_MODELL") or MODELL_VORGABE


def entzaeune(text: str) -> str:
    """Nimmt einen ```json-Zaun um ein JSON-Objekt weg -- der eine
    Reparaturversuch aus dem Auftrag.

    Mehr wird bewusst nicht repariert: wer anfaengt, fehlende Klammern zu
    ergaenzen, rekonstruiert irgendwann Noten, die das Modell nie vergeben
    hat."""
    nackt = text.strip()
    if not nackt.startswith("```"):
        return nackt
    zeilen = nackt.splitlines()
    # Erste Zeile ist der oeffnende Zaun (```json oder nur ```), die letzte
    # der schliessende -- falls er da ist; ein abgeschnittener Text hat ihn
    # nicht, und dann ist der Rest trotzdem der beste Versuch.
    zeilen = zeilen[1:]
    if zeilen and zeilen[-1].strip().startswith("```"):
        zeilen = zeilen[:-1]
    return "\n".join(zeilen).strip()


def lies_json(text: str) -> dict:
    """``json.loads`` mit genau einem Reparaturversuch (``entzaeune``)."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(entzaeune(text))
    except json.JSONDecodeError as fehler:
        raise ClaudeFehler(
            f"Antwort ist kein JSON-Objekt ({fehler.msg}), auch nicht ohne Zaun"
        ) from fehler


@dataclass
class Statistik:
    """Was die Simulationsseite verbraucht hat -- je Art getrennt.

    Kein Geldbetrag: das Abonnement rechnet nicht je Aufruf ab. Die Zahlen
    stehen trotzdem im Bericht, weil sie die einzige Angabe darueber sind, wie
    teuer ein Lauf *waere*, wenn man ihn ueber die API faehrt -- und weil eine
    ploetzlich verdoppelte Aufrufzahl auf eine Endlosschleife im Skript
    hinweist."""

    aufrufe: dict[str, int] = field(default_factory=dict)
    token_ein: dict[str, int] = field(default_factory=dict)
    token_aus: dict[str, int] = field(default_factory=dict)
    fehler: dict[str, int] = field(default_factory=dict)

    def buche(self, art: str, ein: int, aus: int, erfolg: bool) -> None:
        self.aufrufe[art] = self.aufrufe.get(art, 0) + 1
        self.token_ein[art] = self.token_ein.get(art, 0) + ein
        self.token_aus[art] = self.token_aus.get(art, 0) + aus
        if not erfolg:
            self.fehler[art] = self.fehler.get(art, 0) + 1

    def als_dict(self) -> dict:
        return {
            "sim_aufrufe": sum(self.aufrufe.values()),
            "sim_aufrufe_je_art": dict(sorted(self.aufrufe.items())),
            "sim_token_ein": sum(self.token_ein.values()),
            "sim_token_aus": sum(self.token_aus.values()),
            "sim_fehler": sum(self.fehler.values()),
        }


class Claude:
    """Ein winziger Klient fuer das Anthropic-Messages-Format.

    ``klient`` ist ein ``httpx.Client``; ohne einen legt der Konstruktor
    selbst einen an (dann schliesst ``schliesse()`` ihn auch wieder). Tests
    attrappieren entweder den Transport oder gleich ``text``/``json_objekt``
    -- in beiden Faellen geht kein Byte ins Netz."""

    def __init__(self, klient: httpx.Client | None = None, *,
                 basis_url: str | None = None, modellname: str | None = None,
                 wartezeiten=WARTEZEITEN):
        self._eigener_klient = klient is None
        self._klient = klient or httpx.Client(timeout=TIMEOUT_S)
        self.url = basis_url or url()
        self.modell = modellname or modell()
        self._wartezeiten = tuple(wartezeiten)
        self.statistik = Statistik()

    # -- oeffentlich --------------------------------------------------------

    def text(self, system: str, nutzer: str, art: str = "sim",
             max_tokens: int = MAX_TOKENS) -> str:
        """Ein Aufruf, ein Text. Leere Antworten liefern einen leeren String
        -- der Aufrufer entscheidet, ob ihm das reicht."""
        koerper = self._sende(system, nutzer, art, max_tokens)
        return _inhalt_aus(koerper).strip()

    def json_objekt(self, system: str, nutzer: str, art: str = "sim",
                    max_tokens: int = MAX_TOKENS) -> dict:
        """Wie ``text``, aber die Antwort wird als JSON-Objekt gelesen
        (``lies_json``, ein Reparaturversuch)."""
        return lies_json(self.text(system, nutzer, art, max_tokens))

    def schliesse(self) -> None:
        if self._eigener_klient:
            self._klient.close()

    # -- innen --------------------------------------------------------------

    def _headers(self) -> dict:
        # KEIN Authorization-Header: den setzt der Proxy. Ein eigener wuerde
        # ihn ueberschreiben und der Aufruf schlueg mit 401 fehl.
        return {
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _sende(self, system: str, nutzer: str, art: str, max_tokens: int) -> dict:
        koerper = {
            "model": self.modell,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": nutzer}],
        }
        letzter: Exception | None = None
        gesamt = len(self._wartezeiten) + 1
        for versuch in range(gesamt):
            try:
                antwort = self._klient.post(
                    self.url, headers=self._headers(), json=koerper,
                    timeout=TIMEOUT_S,
                )
                antwort.raise_for_status()
                daten = antwort.json()
                nutzung = daten.get("usage") or {}
                self.statistik.buche(
                    art, int(nutzung.get("input_tokens") or 0),
                    int(nutzung.get("output_tokens") or 0), True,
                )
                return daten
            except httpx.HTTPStatusError as fehler:
                code = fehler.response.status_code
                # 4xx ausser 429 sind Programmierfehler (falsches Modell,
                # kaputter Koerper) -- eine Wiederholung wuerde denselben
                # Fehler noch dreimal bezahlen.
                if code != 429 and code < 500:
                    self.statistik.buche(art, 0, 0, False)
                    raise ClaudeFehler(
                        f"Simulationsmodell lehnte den Aufruf ab: HTTP {code}"
                    ) from fehler
                letzter = fehler
            except httpx.TransportError as fehler:
                letzter = fehler

            if versuch < len(self._wartezeiten):
                log.warning(
                    "Simulationsaufruf fehlgeschlagen (%s), Versuch %s/%s",
                    type(letzter).__name__, versuch + 1, gesamt,
                )
                time.sleep(self._wartezeiten[versuch] + random.uniform(0, 0.5))

        self.statistik.buche(art, 0, 0, False)
        raise ClaudeFehler(
            f"Simulationsmodell nach {gesamt} Versuchen nicht erreichbar "
            f"(zuletzt: {type(letzter).__name__})"
        )


def _inhalt_aus(koerper: dict) -> str:
    """Der Text aus ``content[0].text``.

    Robust gegen mehrere Bloecke: Claude kann eine Antwort in mehrere
    ``text``-Bloecke zerlegen (und bei aktivem Denken ``thinking``-Bloecke
    davorsetzen). Genommen wird deshalb alles vom Typ ``text``,
    aneinandergehaengt -- nicht blind ``content[0]``, das sonst irgendwann
    einen Denkblock liefert."""
    teile = [
        b.get("text") or "" for b in (koerper.get("content") or [])
        if isinstance(b, dict) and b.get("type") == "text"
    ]
    if not teile or not "".join(teile).strip():
        # 05.09. 04:25, --set birk Schritt Kernthema: Opus lieferte nur einen
        # thinking-Block und stop_reason max_tokens -- das Budget war im
        # Denken aufgebraucht, bevor ein Textblock kam.
        raise ClaudeFehler(
            "keine Textbloecke in der Antwort des Simulationsmodells "
            f"(stop_reason={koerper.get('stop_reason')}, "
            f"bloecke={[b.get('type') for b in koerper.get('content') or []]})"
        )
    return "\n".join(teile)

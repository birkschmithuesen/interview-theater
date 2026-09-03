"""Rauchtest: EIN Aufruf gegen die echten Dienste (Sprachmodell, optional Whisper).

**Kein Test, laeuft nie automatisch, kostet Geld.** Braucht echte
Zugangsdaten (TS_LLM_URL, TS_LLM_KEY, TS_LLM_MODELL, TS_STT_BASIS,
TS_STT_PRODUKT, siehe theatersoap.einstellungen) und Netzzugriff.

Zweck: die Schaetzung "Zeichen ÷ 3" aus global-constraints.md § 6 an einem
echten Aufruf pruefen. Das Skript schickt ein eingebautes Beispieltranskript
im Modus A (JSON-Schema, wie der kommende Verdichter aus Aufgabe 7 es tun
wird) an das Sprachmodell, liest die tatsaechlichen Prompt-Token aus der
Antwort und rechnet den Divisor aus, der Zeichen auf Token abbilden wuerde.

Aufruf:
    python -m scripts.rauchtest                 # nur das Sprachmodell
    python -m scripts.rauchtest ./beispiel.ogg   # zusaetzlich Whisper
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from theatersoap import db, einstellungen, llm, stt

#: Schema in der Form, die Aufgabe 7 (theatersoap.verdichter) verwenden wird
#: (SPEC-kontext-architektur.md § 5/§ 7): Zusammenfassung plus Kernthemen mit
#: je einem Belegzitat. Hier lokal nachgebaut, weil theatersoap.verdichter in
#: dieser Aufgabe noch nicht existiert -- nur zum Kalibrieren der
#: Token-Schaetzung, nicht zur produktiven Verwendung.
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["zusammenfassung", "kernthemen"],
    "properties": {
        "zusammenfassung": {"type": "string"},
        "kernthemen": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["thema", "beleg_zitat"],
                "properties": {
                    "thema": {"type": "string"},
                    "beleg_zitat": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = (
    "Du fasst ein Interview-Transkript aus einem Theaterworkshop zusammen. "
    "Schreibe 3-5 Saetze Zusammenfassung und nenne 2-4 Kernthemen. Zu jedem "
    "Thema gehoert ein woertliches, buchstabengetreues Zitat aus dem "
    "Transkript -- keine Auslassungen mit [...], nichts erfinden."
)

#: Eingebautes Beispieltranskript -- frei erfunden, keine echten
#: Teilnehmerinnen-Daten (das Repository ist oeffentlich).
BEISPIELTRANSKRIPT = """
Ich bin 1998 in diese Stadt gezogen, damals war ich zwanzig. Das Theater hier
war fuer mich der erste Ort, an dem ich mich zu Hause gefuehlt habe, obwohl
ich niemanden kannte. Die Proben liefen abends, und ich erinnere mich, wie
die Strassenbahn quietschend um die Ecke bog, waehrend wir drinnen Szenen
wiederholten, die nie fertig wurden. Meine Mutter hat nie verstanden, warum
ich so viel Zeit dort verbracht habe, aber fuer mich war es keine Frage. Ich
habe dort meine beste Freundin kennengelernt, wir stehen heute noch in
Kontakt, auch wenn sie inzwischen in einem anderen Land lebt. Was mir am
meisten geblieben ist, ist das Gefuehl, gehoert zu werden, wenn man auf der
Buehne steht und der Saal ganz still wird.
""".strip()


def teste_sprachmodell(einst, klient, conn) -> None:
    print("--- Sprachmodell (Modus A, Verdichter-Schema) ---")
    zeichen = len(SYSTEM_PROMPT) + len(BEISPIELTRANSKRIPT)
    geschaetzt = zeichen // 3

    start = time.monotonic()
    ergebnis = llm.LLM(einst, klient, conn).schema(
        None, SYSTEM_PROMPT, BEISPIELTRANSKRIPT, SCHEMA, "rauchtest"
    )
    dauer_s = time.monotonic() - start

    zeile = conn.execute(
        "SELECT tatsaechliche_token, antwort_token FROM aufruf "
        "WHERE art = 'rauchtest' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    tatsaechlich = zeile["tatsaechliche_token"] if zeile else None

    print(f"Ergebnis: {ergebnis}")
    print(f"Dauer: {dauer_s:.2f}s")
    print(f"Zeichen (system+nutzer): {zeichen}")
    print(f"Geschaetzte Token (Zeichen ÷ 3): {geschaetzt}")
    print(f"Tatsaechliche Prompt-Token (usage.prompt_tokens): {tatsaechlich}")
    if tatsaechlich:
        divisor = zeichen / tatsaechlich
        print(f"Tatsaechlicher Divisor (Zeichen / tatsaechliche Token): {divisor:.2f}")
    else:
        print("Kein Divisor berechenbar -- Antwort enthielt keine usage.prompt_tokens.")


def teste_whisper(einst, klient, audio_pfad: Path) -> None:
    print("--- Whisper (zweistufig) ---")
    start = time.monotonic()
    text = stt.transkribiere(einst, klient, audio_pfad, 90.0)
    dauer_s = time.monotonic() - start
    print(f"Transkript: {text!r}")
    print(f"Dauer: {dauer_s:.2f}s")


def main() -> None:
    einst = einstellungen.laden()
    conn = db.verbinde(einst.db_pfad)
    db.initialisiere(conn)

    with httpx.Client() as klient:
        teste_sprachmodell(einst, klient, conn)

        if len(sys.argv) > 1:
            print()
            teste_whisper(einst, klient, Path(sys.argv[1]))
        else:
            print()
            print("(kein Audiopfad angegeben -- Whisper wird uebersprungen)")

    conn.close()


if __name__ == "__main__":
    main()

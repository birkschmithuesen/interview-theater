"""Das zweite Geraet im Abnahmelauf P1-2 (04.10.2026): ein Handy, das nur
zuschaut. Es oeffnet dieselbe Gruppen-URL, wechselt einmal in den
CoThinker-Tab und wird nie neu geladen -- gemessen wird, ob das
Begriffsboard dort von selbst waechst (Karte t_4517d4ad). Kein Modell, keine
Persona.

Abweichung vom urspruenglichen Entwurf, mit Grund: ``framenavigated`` feuert
auch bei Hash-Navigation, und der Tabwechsel selbst setzt ``#buehne`` in der
URL. Ein Neuladen wird deshalb ueber eine Fenster-Marke
(``window.__beobachterMarke``) erkannt, die ein echtes Reload loescht."""

from __future__ import annotations

HANDY_PROFIL = {"viewport": {"width": 390, "height": 844},
                "is_mobile": True, "has_touch": True}
BOARD_SELEKTOR = "li[data-begriff]"
_TAB = '.tabs button[data-tab="buehne"]'


def _vor_goto(context) -> None:
    """Einhaengepunkt fuer Tests (``page.route``); im Lauf leer."""


class Beobachter:
    def __init__(self, context, page):
        self.context = context
        self.page = page
        self.verlauf: list[int] = []

    @classmethod
    def oeffne(cls, browser, url: str) -> "Beobachter":
        context = browser.new_context(**HANDY_PROFIL)
        _vor_goto(context)
        page = context.new_page()
        page.goto(url)
        page.wait_for_selector(".tabs")
        page.click(_TAB)
        page.wait_for_timeout(300)
        page.evaluate("window.__beobachterMarke = 1")
        return cls(context, page)

    def messe(self) -> int:
        anzahl = self.page.locator(BOARD_SELEKTOR).count()
        self.verlauf.append(anzahl)
        return anzahl

    def begriffe(self) -> tuple[str, ...]:
        """Die sichtbaren Board-Begriffe (derselbe Selektor wie ``messe``):
        der Wert von ``data-begriff``, sonst der sichtbare Text."""
        werte = self.page.locator(BOARD_SELEKTOR).evaluate_all(
            "els => els.map(e => (e.getAttribute('data-begriff') || '').trim() || e.innerText.trim())"
        )
        return tuple(w for w in werte if w)

    @property
    def neu_geladen(self) -> bool:
        return not self.page.evaluate("window.__beobachterMarke === 1")

    def ergebnis(self) -> dict:
        neu = self.neu_geladen
        return {"board_verlauf": list(self.verlauf),
                "beobachter_neu_geladen": neu,
                "board_bestanden": bool(self.verlauf) and max(self.verlauf) > 0 and not neu}

    def schliesse(self) -> None:
        self.context.close()

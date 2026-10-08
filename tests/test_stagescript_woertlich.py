"""Fix (Birk, Live-Fall G1 Szene 2, 08.10.2026): die Gruppe lieferte den
Szenentext woertlich im Chat, verlangte dreimal "esattamente, senza cambiare
niente / non dividere tra Giada e Emma" und bestaetigte mit "Yes, save" --
gespeichert wurde trotzdem eine vom Modell neu geschriebene Fassung mit
Rollenaufteilung (Giada/Emma) statt der woertlich bestaetigten Chat-Fassung.

``stagescript.schreibe`` hatte vor dem Speichern keinen Wortabgleich zwischen
der zuletzt bestaetigten Chat-Fassung (hier: ``notiz``, wenn die Gruppe ihren
gewuenschten Text selbst als Aenderungswunsch mitschickt) und der vom Modell
zurueckgegebenen Speicherfassung. Die Platzhaltertexte hier sind erfunden,
aber strukturell gleich dem Live-Fall (ein woertlicher Monolog, das Modell
schreibt beim Speichern Sprecherzeilen hinein).

Kein Netz, kein Modell: der Schreibweg bekommt eine Attrappe."""

from interview_theater import repo, stagescript

from test_stagescript import _karten
from test_szenenkarte import TG, padua  # noqa: F401

#: Die woertlich gelieferte, bereits im Chat bestaetigte Fassung -- EIN
#: Monolog, keine Rollenaufteilung (wie von der Gruppe verlangt).
CHAT_FASSUNG = (
    "Giada racconta che l'estate in cui la nonna le insegno' a leggere i tarocchi "
    "a lume di candela, mezzo per gioco mezzo sul serio, le carte non hanno mai "
    "mentito, nemmeno quando lei lo avrebbe voluto."
)

#: Was das Modell beim Speichern trotzdem zurueckgibt: fast wortgleich, aber
#: mit einer Rollenaufteilung Giada/Emma -- genau der Live-Befund.
MODELL_ROLLENAUFTEILUNG = (
    "GIADA: Giada racconta che l'estate in cui la nonna le insegno' a leggere i tarocchi "
    "a lume di candela, mezzo per gioco mezzo sul serio.\n"
    "EMMA: le carte non hanno mai mentito, nemmeno quando lei lo avrebbe voluto."
)

#: Eine echte Ueberarbeitung: das Modell schreibt eine inhaltlich ganz andere
#: Szene -- der Gegenfall, der weiterhin wie bisher gespeichert werden muss.
MODELL_ECHTE_UEBERARBEITUNG = (
    "GIADA: Non voglio parlare di quella stanza, non voglio ricordare il freddo sul pavimento.\n"
    "EMMA: Ma lo dici ogni volta, e ogni volta io resto a sentire senza capire davvero cosa provi."
)


#: Nahe an ``stagescript.AEHNLICHKEIT_WOERTLICH_SCHWELLE`` (0.95): die
#: Fixtures oben liegen bei ~0.96 bzw. ~0.27 Aehnlichkeit, weit von der
#: Grenze weg -- eine verstellte Schwelle (z. B. 0.5) faellt dort nicht auf.
#: Diese zwei Fassungen liegen bewusst knapp darueber (~0.95) bzw. knapp
#: darunter (~0.94).
_NAH_AN_SCHWELLE_DARUEBER = CHAT_FASSUNG.replace(
    "mezzo per gioco mezzo sul serio", "un po' per gioco un po' sul serio")
_NAH_AN_SCHWELLE_DARUNTER = CHAT_FASSUNG.replace(
    "mezzo per gioco mezzo sul serio", "un po' per gioco un po' sul serio davvero")


class _LLMFest:
    """Gibt bei jedem Aufruf dieselbe (feste) Fassung zurueck, unabhaengig
    von der Notiz -- simuliert ein Modell, das die Bitte "woertlich, nichts
    aendern" ignoriert."""

    def __init__(self, text):
        self._text = text
        self.aufrufe = []

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe.append({"art": art, "nutzer": nutzer})
        if art == stagescript.ART:
            return {"text": self._text, "kopf": ""}
        return {}


def test_woertlich_bestaetigte_chatfassung_wird_nicht_umgeschrieben(conn, padua):
    """Rot vor dem Fix: obwohl die Modellausgabe fast wortgleich mit der
    bestaetigten Chat-Fassung ist (nur eine Rollenaufteilung drin), wurde
    bisher die Modellausgabe gespeichert statt der woertlich verlangten
    Fassung. Die Notiz selbst (die Gruppe schreibt "esattamente, senza
    cambiare niente ...") ist dabei nur Begleittext -- die Chat-Fassung
    kommt separat und sauber (``chat_fassung``), wie die im Chat bereits
    gezeigte Fassung web_post 2655 im Live-Fall."""
    ids = _karten(conn)
    klm = _LLMFest(MODELL_ROLLENAUFTEILUNG)
    notiz = "esattamente, senza cambiare niente, non dividere tra Giada e Emma"

    assert stagescript.schreibe(
        conn, klm, None, 1, 2, notiz, chat_fassung=CHAT_FASSUNG) is True

    gespeichert = repo.hole_szene(conn, ids[1])["volltext"]
    assert gespeichert == CHAT_FASSUNG
    assert "GIADA:" not in gespeichert
    assert "EMMA:" not in gespeichert


def test_echte_ueberarbeitung_mit_klar_abweichender_chatfassung_bleibt_modellausgabe(
        conn, padua):
    """Gegenfall: die Modellausgabe weicht deutlich (< 0.95 Aehnlichkeit) von
    der zuletzt gezeigten Chat-Fassung ab -- eine echte Ueberarbeitung, kein
    woertlich bestaetigter Chattext. Die Modellausgabe wird weiterhin wie
    bisher gespeichert."""
    ids = _karten(conn)
    klm = _LLMFest(MODELL_ECHTE_UEBERARBEITUNG)

    assert stagescript.schreibe(
        conn, klm, None, 1, 2, "mach die Szene duesterer",
        chat_fassung=CHAT_FASSUNG) is True

    gespeichert = repo.hole_szene(conn, ids[1])["volltext"]
    assert gespeichert == MODELL_ECHTE_UEBERARBEITUNG


def test_woertlich_schwelle_knapp_darueber_wird_woertlich():
    """``_NAH_AN_SCHWELLE_DARUEBER`` liegt bei ~0.95 Aehnlichkeit zur
    Chat-Fassung -- knapp ueber der Schwelle, die Chat-Fassung muss die
    Modellausgabe ersetzen. Mit einer verstellten Schwelle (z. B. 0.5) wuerde
    das Ergebnis unveraendert bleiben, der Test also nicht auffallen --
    dieser Fall faellt dagegen bei JEDER Schwelle <= ~0.95 unveraendert aus."""
    assert stagescript._woertlich_statt_modell(
        CHAT_FASSUNG, _NAH_AN_SCHWELLE_DARUEBER) == CHAT_FASSUNG


def test_woertlich_schwelle_knapp_darunter_bleibt_modellausgabe():
    """``_NAH_AN_SCHWELLE_DARUNTER`` liegt bei ~0.94 Aehnlichkeit -- knapp
    UNTER der Schwelle, die Modellausgabe muss stehen bleiben. Mit einer
    verstellten Schwelle (z. B. 0.5) wuerde stattdessen die Chat-Fassung
    uebernommen -- dieser Test faellt bei einer solchen Verstellung rot."""
    assert stagescript._woertlich_statt_modell(
        CHAT_FASSUNG, _NAH_AN_SCHWELLE_DARUNTER) is None


def test_starte_ueber_den_produktionspfad_schuetzt_die_chatfassung(conn, einst, padua):
    """Derselbe Live-Fall, aber ueber den ECHTEN Produktionspfad
    (``stagescript.starte()``, der einzige Aufrufer von ``schreibe()`` in
    Produktion) statt den direkten ``schreibe()``-Aufruf oben: der Schutz
    greift nur, wenn ``starte()`` die zuletzt gespeicherte Fassung
    (``alt_en``, hier vorab wie im Live-Fall ueber ``repo.setze_stagescript``
    abgelegt) auch tatsaechlich als ``chat_fassung`` an ``schreibe()``
    durchreicht."""
    ids = _karten(conn)
    repo.setze_stagescript(conn, ids[1], CHAT_FASSUNG, None)
    tg = TG()
    klm = _LLMFest(MODELL_ROLLENAUFTEILUNG)
    notiz = "esattamente, senza cambiare niente, non dividere tra Giada e Emma"

    faden = stagescript.starte(conn, tg, klm, einst, 1, 2, notiz)
    assert faden is not None
    faden.join(5)

    gespeichert = repo.hole_szene(conn, ids[1])["volltext"]
    assert gespeichert == CHAT_FASSUNG
    assert "GIADA:" not in gespeichert
    assert "EMMA:" not in gespeichert

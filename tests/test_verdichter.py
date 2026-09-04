import pytest
from interview_theater import db, repo, verdichter


@pytest.fixture
def einst(tmp_path):
    from interview_theater import einstellungen
    return einstellungen.Einstellungen(
        bot_token="T", bot_name="gruppe1", db_pfad=str(tmp_path / "t.db"),
        audio_verz=str(tmp_path / "audio"),
        llm_url="https://llm.test/v1/chat/completions", llm_key="K", llm_modell="kimi",
        stt_basis="https://stt.test", stt_produkt="PRODUKT-ID",
    )


@pytest.fixture
def conn(tmp_path):
    c = db.verbinde(str(tmp_path / "t.db"))
    db.initialisiere(c)
    repo.sichere_gruppe(c, 1, "gruppe1", "Testgruppe")
    return c


TRANSKRIPT = (
    "Ich bin 1998 in diese Stadt gezogen, damals war ich zwanzig. Das Theater "
    "hier war fuer mich der erste Ort, an dem ich mich zu Hause gefuehlt habe. "
    "Meine Mutter hat nie verstanden, warum ich so viel Zeit dort verbracht habe."
)


class LLMAttrappe:
    """Ersetzt interview_theater.llm.LLM in Tests: liefert eine vorbereitete Antwort
    und zaehlt die Aufrufe, ohne irgendwelchen Netzzugriff."""

    def __init__(self, antwort):
        self._antwort = antwort
        self.aufrufe = 0

    def schema(self, chat_id, system, nutzer, schema, art):
        self.aufrufe += 1
        return self._antwort


@pytest.fixture
def aid(conn):
    aufnahme_id = repo.lege_aufnahme_an(conn, 1, 42, "lang", "sprache")
    repo.setze_transkript(conn, aufnahme_id, TRANSKRIPT)
    return aufnahme_id


def test_gueltiges_zitat_wird_gespeichert(conn, einst, aid):
    klm = LLMAttrappe({
        "zusammenfassung": "Eine Person erinnert sich an ihren Zuzug 1998.",
        "kernthemen": [
            {"thema": "Ankommen", "beleg_zitat": "Ich bin 1998 in diese Stadt gezogen"},
        ],
    })
    vid = verdichter.verdichte(klm, conn, einst, aid)

    thema = repo.themen_zu(conn, vid)[0]
    assert thema["zitat_geprueft"] == 1
    assert thema["beleg_zitat"] == "Ich bin 1998 in diese Stadt gezogen"


def test_ungueltiges_zitat_verwirft_das_ganze_thema(conn, einst, aid):
    """N2: kein Thema ohne woertliches Belegzitat. Frueher blieb der Vorschlag
    mit ``zitat_geprueft=0`` stehen -- im Probelauf entstand daraus ein
    komplett erfundenes Interview mit drei unbelegten Themen."""
    klm = LLMAttrappe({
        "zusammenfassung": "z",
        "kernthemen": [
            {"thema": "Abschied", "beleg_zitat": "Sie weinte bitterlich"},
        ],
    })
    vid = verdichter.verdichte(klm, conn, einst, aid)

    assert klm.aufrufe == 1, "kein Retry"
    assert repo.themen_zu(conn, vid) == []
    assert repo.hole_verdichtung(conn, vid)["zusammenfassung"] == "z", (
        "die Zusammenfassung bleibt, nur die Themen fallen weg"
    )
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art='zitat_ungeprueft'"
    ).fetchone()[0] == 1


def test_leeres_zitat_verwirft_das_thema_ebenso(conn, einst, aid):
    """Ein leerer String besteht die Pruefung sonst als Teilstring von allem
    -- der Fall muss ausdruecklich abgefangen sein."""
    klm = LLMAttrappe({
        "zusammenfassung": "z",
        "kernthemen": [{"thema": "Leere", "beleg_zitat": ""}],
    })
    vid = verdichter.verdichte(klm, conn, einst, aid)

    assert repo.themen_zu(conn, vid) == []


def test_gemischt_gueltige_und_ungueltige_zitate(conn, einst, aid):
    klm = LLMAttrappe({
        "zusammenfassung": "z",
        "kernthemen": [
            {"thema": "Ankommen", "beleg_zitat": "Ich bin 1998 in diese Stadt gezogen"},
            {"thema": "Abschied", "beleg_zitat": "Sie weinte bitterlich"},
        ],
    })
    vid = verdichter.verdichte(klm, conn, einst, aid)

    themen = repo.themen_zu(conn, vid)
    assert [t["thema"] for t in themen] == ["Ankommen"]
    assert themen[0]["zitat_geprueft"] == 1
    assert conn.execute(
        "SELECT count(*) FROM vorfall WHERE art='zitat_ungeprueft'"
    ).fetchone()[0] == 1


def test_verdichte_speichert_zusammenfassung_und_verknuepft_aufnahme(conn, einst, aid):
    klm = LLMAttrappe({"zusammenfassung": "Kurze Zusammenfassung.", "kernthemen": []})
    vid = verdichter.verdichte(klm, conn, einst, aid)

    zeile = repo.verdichtungen(conn, 1)[0]
    assert zeile["id"] == vid
    assert zeile["aufnahme_id"] == aid
    assert zeile["zusammenfassung"] == "Kurze Zusammenfassung."


def test_verdichte_ruft_schema_mit_transkript_als_nutzertext_auf(conn, einst, aid):
    gesehen = {}

    class Aufzeichnende(LLMAttrappe):
        def schema(self, chat_id, system, nutzer, schema, art):
            gesehen["chat_id"] = chat_id
            gesehen["nutzer"] = nutzer
            gesehen["schema"] = schema
            gesehen["art"] = art
            return super().schema(chat_id, system, nutzer, schema, art)

    klm = Aufzeichnende({"zusammenfassung": "z", "kernthemen": []})
    verdichter.verdichte(klm, conn, einst, aid)

    assert gesehen["chat_id"] == 1
    assert gesehen["nutzer"] == TRANSKRIPT
    assert gesehen["art"] == "verdichter"
    assert gesehen["schema"] == verdichter.SCHEMA


def test_schema_hat_additional_properties_false_und_vollstaendiges_required():
    def pruefe_objekt(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False, node
                eigenschaften = set(node.get("properties", {}).keys())
                assert set(node.get("required", [])) == eigenschaften, node
            for wert in node.values():
                pruefe_objekt(wert)
        elif isinstance(node, list):
            for element in node:
                pruefe_objekt(element)

    pruefe_objekt(verdichter.SCHEMA)

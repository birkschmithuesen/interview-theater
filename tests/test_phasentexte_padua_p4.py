"""Birk 05.10.2026 22:00: Phase 4 (Brainstorm) hat keinen eigenen
Gedankenbogen-Toggle mehr (t_cf87ee0a abgeloest) -- sie bedient sich mit
genau der Phase-1-Diskussionsbedienung ("Start listening" / "Discussion
done"). Die Padua-Einleitung von Phase 4 (``workshop/padua-2026/
phasentexte.toml``) darf deshalb nichts mehr vom alten "tap when the
thought is complete" erzaehlen -- siehe Task 4 des Plans und
``docs/agents/entscheidungen.md`` (t_cf87ee0a-Nachtrag)."""

from interview_theater import sprache, web_chat, workshop

VERBOTENE_PHRASEN = ("tap again", "thought is complete", "tap once")


def _padua_einleitung_phase_4(monkeypatch) -> str:
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        return workshop.phasentexte_einleitungen()[4]
    finally:
        workshop.vergiss()
        sprache.vergiss()


def test_padua_phase_4_wirbt_fuer_denselben_knopf_wie_phase_1(monkeypatch):
    # Padua laeuft englisch -- web_chat._TEXT_DISKUSSION_AN ist die
    # deutsche Konstante; ``T`` (sprache.Texte) liest die EN-Fassung, die
    # der Knopf im Browser unter diesem Profil wirklich zeigt.
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        text = workshop.phasentexte_einleitungen()[4]
        diskussion_an = web_chat.T._TEXT_DISKUSSION_AN
        diskussion_fertig = web_chat.T._TEXT_DISKUSSION_FERTIG_KNOPF
    finally:
        workshop.vergiss()
        sprache.vergiss()
    assert diskussion_an == "Start listening"
    assert diskussion_fertig == "Discussion done"
    assert diskussion_an in text
    assert diskussion_fertig in text


def test_padua_phase_4_erzaehlt_nichts_vom_alten_toggle(monkeypatch):
    text = _padua_einleitung_phase_4(monkeypatch).casefold()
    for phrase in VERBOTENE_PHRASEN:
        assert phrase not in text, phrase


def test_keine_en_phasentexte_erwaehnen_den_alten_toggle_wortlaut(monkeypatch):
    """Nicht nur Phase 4 selbst -- ueberhaupt kein Padua-Phasentext darf
    noch "tap when the thought" sagen (die wortgleiche Formulierung aus der
    alten Brainstorm-Laeuft-Zeile, ``_TEXT_BRAINSTORM_LAEUFT``)."""
    monkeypatch.setenv(workshop.VARIABLE, "padua-2026")
    workshop.vergiss()
    sprache.vergiss()
    try:
        einleitungen = workshop.phasentexte_einleitungen()
    finally:
        workshop.vergiss()
        sprache.vergiss()
    for nummer, text in einleitungen.items():
        assert "tap when the thought" not in text.casefold(), nummer

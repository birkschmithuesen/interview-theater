"""Der Profilschalter recherche.aktiv (Karte t_c5117c91): Vorgabe false,
Dortmund und das eingebaute Profil bleiben byte-gleich."""

from interview_theater import workshop


def _profil(werte: dict) -> workshop.Profil:
    return workshop.Profil(name="test", verzeichnis=None, werte=werte)


def test_ohne_eintrag_ist_recherche_aus():
    assert workshop.recherche_aktiv(_profil({})) is False


def test_mit_eintrag_ist_recherche_an():
    assert workshop.recherche_aktiv(_profil({"recherche": {"aktiv": True}})) is True


def test_das_eingebaute_vorgabeprofil_hat_recherche_aus():
    assert workshop.recherche_aktiv(_profil(workshop.VORGABE_WERTE)) is False

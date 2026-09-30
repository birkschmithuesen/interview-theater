import pytest

from interview_theater import zitat

IT_TRANSKRIPT = "Allora, l’ho detto a mia madre: qui non è casa mia, però ci provo."
UK_TRANSKRIPT = "Я приїхала сюди два роки тому, і ще досі вчу мову."
AR_TRANSKRIPT = "جئت إلى هنا قبل سنتين وما زلت أتعلم اللغة."


@pytest.mark.parametrize("zitat_, transkript, soll", [
    ("l'ho detto a mia madre", IT_TRANSKRIPT, True),          # typografischer Apostroph im Transkript
    ("qui non è casa mia", IT_TRANSKRIPT, True),
    ("I told my mother", IT_TRANSKRIPT, False),                # uebersetzt = kein Beleg
    ("here is not my home", IT_TRANSKRIPT, False),
    ("і ще досі вчу мову", UK_TRANSKRIPT, True),               # Kyrillisch
    ("وما زلت أتعلم اللغة", AR_TRANSKRIPT, True),               # Arabisch
    ("and I am still learning the language", AR_TRANSKRIPT, False),
])
def test_zitate_bleiben_im_original(zitat_, transkript, soll):
    assert zitat.pruefe(zitat_, transkript) is soll


def test_woertliches_zitat_besteht():
    transkript = "Ich bin 1998 in diese Stadt gezogen, damals war ich zwanzig."
    assert zitat.pruefe("Ich bin 1998 in diese Stadt gezogen", transkript)


def test_typografische_anfuehrungszeichen_stoeren_nicht():
    transkript = 'Sie sagte „Ich gehe jetzt" und ging, dann rief er »warte doch«.'
    assert zitat.pruefe('"Ich gehe jetzt"', transkript)
    assert zitat.pruefe("»warte doch«", transkript)


def test_mehrfache_leerzeichen_und_zeilenumbrueche_stoeren_nicht():
    transkript = "Die Proben liefen   abends,\nund die Strassenbahn\n\nquietschte."
    assert zitat.pruefe("Die Proben liefen abends, und die Strassenbahn quietschte.",
                          transkript)


def test_erfundenes_zitat_faellt_durch():
    transkript = "Ich bin 1998 in diese Stadt gezogen, damals war ich zwanzig."
    assert not zitat.pruefe("Sie weinte bitterlich", transkript)


def test_leeres_zitat_faellt_durch():
    transkript = "Ich bin 1998 in diese Stadt gezogen, damals war ich zwanzig."
    assert not zitat.pruefe("", transkript)
    assert not zitat.pruefe("   ", transkript)


def test_zitat_mit_auslassung_faellt_durch_ohne_sonderbehandlung():
    # "A [...] B" wird NICHT zerlegt: kommt der String so nicht vor, ist er ungueltig
    transkript = "Ich bin 1998 in diese Stadt gezogen. Damals war ich zwanzig."
    assert not zitat.pruefe("Ich bin 1998 in diese Stadt gezogen [...] war ich zwanzig",
                              transkript)

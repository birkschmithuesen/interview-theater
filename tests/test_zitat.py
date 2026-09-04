from interview_theater import zitat


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

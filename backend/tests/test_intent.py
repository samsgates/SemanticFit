from app.services.intent import deterministic_intent


def test_price_and_style_extraction():
    intent = deterministic_intent("I need a black formal dress under $120 for a summer wedding")
    assert intent.max_price == 120
    assert "formal" in intent.style
    assert "summer" in intent.season
    assert "wedding" in intent.occasion
    assert "black" in intent.colors


def test_exclusion():
    intent = deterministic_intent("casual summer clothes without denim")
    assert any("denim" in x for x in intent.exclude)

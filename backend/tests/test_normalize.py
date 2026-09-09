from ingestion.normalize import normalize_product


def test_normalize_realistic_product():
    raw = {
        "main_category": "AMAZON FASHION",
        "title": " Women's Linen Shirt ",
        "average_rating": 4.6,
        "rating_number": 125,
        "features": ["Lightweight", "Breathable"],
        "description": ["Casual summer shirt"],
        "price": "$39.99",
        "images": [{"thumb": "https://x/t.jpg", "large": "https://x/l.jpg", "variant": "MAIN", "hi_res": "https://x/h.jpg"}],
        "videos": [],
        "store": "Example Store",
        "categories": ["Women", "Clothing", "Tops"],
        "details": {"Fabric type": "Linen blend"},
        "parent_asin": "B000TEST01",
        "bought_together": None,
    }
    row, warnings = normalize_product(raw)
    assert row is not None
    assert row["parent_asin"] == "B000TEST01"
    assert row["price"] == 39.99
    assert row["primary_image"].endswith("h.jpg")
    assert "Linen blend" in row["search_document"]
    assert not warnings


def test_missing_price_is_warning_not_failure():
    row, warnings = normalize_product({"title": "Shirt", "parent_asin": "B1", "price": None})
    assert row is not None
    assert row["price"] is None
    assert "missing_price" in warnings


def test_missing_identity_is_hard_failure():
    row, warnings = normalize_product({"title": "Shirt"})
    assert row is None
    assert warnings == ["missing_parent_asin"]

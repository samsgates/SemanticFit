from app.services.ranking import bayesian_quality, popularity


def test_rating_confidence():
    weak = bayesian_quality(5.0, 1)
    strong = bayesian_quality(4.8, 10000)
    assert strong > weak


def test_popularity_is_logarithmic():
    assert popularity(1000) > popularity(100)
    assert popularity(100000) - popularity(10000) < 3

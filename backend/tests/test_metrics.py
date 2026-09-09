from evaluation.metrics import ndcg_at_k, precision_at_k, reciprocal_rank


def test_metrics():
    rel = [0, 1, 1, 0]
    assert precision_at_k(rel, 4) == 0.5
    assert reciprocal_rank(rel) == 0.5
    assert 0 < ndcg_at_k(rel, 4) <= 1

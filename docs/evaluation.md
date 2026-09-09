# Evaluation

SemanticFit separates weak intent tests from manually labeled retrieval tests.

Starter cases contain expected semantic terms/categories and produce proxy relevance measures, intent coverage, hard-constraint compliance, diversity, and latency.

For real retrieval metrics, reviewers should add `relevant_parent_asins`. Those cases produce Precision@K, Recall@K, MRR, and NDCG@K.

This distinction prevents weak heuristic labels from being presented as ground-truth retrieval quality.

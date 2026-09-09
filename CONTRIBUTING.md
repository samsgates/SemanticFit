# Contributing to SemanticFit

1. Open an issue for substantial behavior or architecture changes.
2. Keep retrieval, ranking, evaluation, and UI concerns modular.
3. Add tests for bug fixes and ranking logic.
4. Never report weak-label proxy metrics as gold-standard retrieval metrics.
5. Do not add paid API dependencies to the core search path.
6. Run `make lint` and `make test` before submitting a pull request.

When changing search behavior, include an evaluation run comparison whenever a populated SemanticFit index is available.

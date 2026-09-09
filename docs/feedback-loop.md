# Feedback Loop

Feedback storage is optional and does not alter online ranking automatically.

```mermaid
flowchart TD
    S[Search results] --> F[Explicit / implicit feedback]
    F --> DB[(PostgreSQL)]
    DB --> A[Admin review]
    A --> E[Evaluation cases]
    E --> T[Offline tuning]
    T --> R[Regression evaluation]
    R --> D[Deploy approved change]
```

Recommended uses include hard-negative mining, ranking-weight tuning, reranker fine-tuning, and creation of regression cases.

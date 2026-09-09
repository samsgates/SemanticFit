# SemanticFit Architecture

## Online recommendation path

```mermaid
sequenceDiagram
    participant U as React UI
    participant F as Flask API
    participant I as Intent Processor
    participant E as BGE-M3
    participant Q as Qdrant
    participant R as BGE Reranker
    participant P as PostgreSQL

    U->>F: POST /recommendations
    F->>I: parse query + constraints
    I-->>F: structured intent
    F->>E: encode semantic query
    E-->>F: dense + sparse vectors
    F->>Q: hybrid search + filters
    Q-->>F: top candidates
    F->>P: fetch canonical product docs
    P-->>F: product records
    F->>R: query/product pairs
    R-->>F: relevance scores
    F->>F: rank + diversify + explain
    F-->>U: recommendations + request ID + latency
```

## Storage responsibilities

### PostgreSQL

Canonical product metadata, ingestion jobs/checkpoints, search usage, audit history, feedback, and evaluation runs.

### Qdrant

Rebuildable search index containing named `dense` and `sparse` representations plus compact filter payloads.

### Redis

Optional response cache. Redis failure is non-fatal.

## Model lifecycle

Embedding and reranking models are lazy singletons in the Flask process. The default Gunicorn topology uses one worker process to avoid duplicating model memory. Threads handle concurrent request work around shared models and network/storage operations.

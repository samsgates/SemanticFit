# SemanticFit API Guide

SemanticFit exposes a JSON API for recommendations, catalog access, feedback, service health, and administration.

## Documentation endpoints

With the application running locally:

- Swagger UI: http://localhost:5000/api/docs
- OpenAPI JSON: http://localhost:5000/api/openapi.json
- API base URL: `http://localhost:5000/api/v1`

Swagger UI provides request schemas, response schemas, parameters, and an interactive **Try it out** action. Its assets load from a pinned `swagger-ui-dist` CDN package, so the browser needs network access to render the page.

## Public API

Check the application and its dependencies:

```bash
curl http://localhost:5000/api/v1/health
curl http://localhost:5000/api/v1/ready
```

Request recommendations with a natural-language query and optional hard filters:

```bash
curl -X POST 'http://localhost:5000/api/v1/recommendations?debug=true' \
	-H 'Content-Type: application/json' \
	-H 'X-Session-ID: example-session' \
	-d '{
		"query": "black formal dress for a summer wedding under $120",
		"limit": 8,
		"filters": {
			"min_price": 20,
			"max_price": 120,
			"min_rating": 4,
			"category": "Dresses"
		}
	}'
```

Supported explicit filters are `min_price`, `max_price`, `min_rating`, `category`, and `store`. The query must be 1-1000 characters. The server constrains `limit` to its configured maximum.

The response includes:

- `request_id`: use this when submitting feedback or investigating errors
- `intent`: structured intent extracted from the query
- `filters`: explicit and inferred filters used by search
- `results`: ranked products with match reasons and score breakdowns
- `meta`: retrieval counts, latency, cache status, and LLM usage
- `debug`: per-stage timings when `debug=true`

Browse catalog data and suggestions:

```bash
curl http://localhost:5000/api/v1/categories
curl 'http://localhost:5000/api/v1/search/suggestions?q=wedding'
curl http://localhost:5000/api/v1/products/B012345678
```

Submit product-level feedback using the `request_id` returned by recommendations:

```bash
curl -X POST http://localhost:5000/api/v1/feedback \
	-H 'Content-Type: application/json' \
	-H 'X-Session-ID: example-session' \
	-d '{
		"request_id": "req_example",
		"product_id": "B012345678",
		"feedback_type": "helpful",
		"feedback_reason": "Matches the requested occasion"
	}'
```

Valid feedback types are `helpful`, `not_relevant`, `search_helpful`, `search_partial`, `search_not_helpful`, `click`, and `detail_view`.

## Request headers

Every response includes `X-Request-ID`. Supply your own `X-Request-ID` header to correlate API calls with application logs, or let SemanticFit generate one.

`X-Session-ID` is optional and identifies an anonymous search session. Use a stable random UUID per browser or client installation; do not put personal data in it.

## Errors and rate limits

Errors use a consistent envelope:

```json
{
	"error": {
		"code": "INVALID_QUERY",
		"message": "Query cannot be empty",
		"request_id": "req_example"
	}
}
```

A `429` response includes `Retry-After` in seconds. Search failures may return `503` when a required model, database, or vector-store operation cannot complete.

## Admin API

Admin endpoints use a Flask session cookie. Save the cookie returned by login:

```bash
curl -c semanticfit.cookies \
	-X POST http://localhost:5000/api/v1/admin/login \
	-H 'Content-Type: application/json' \
	-d '{"username":"admin","password":"admin123"}'
```

The login response contains `csrf_token`. Read-only admin requests need the saved cookie:

```bash
curl -b semanticfit.cookies http://localhost:5000/api/v1/admin/dashboard
curl -b semanticfit.cookies 'http://localhost:5000/api/v1/admin/search-usage?limit=100'
curl -b semanticfit.cookies http://localhost:5000/api/v1/admin/ingestion/jobs
curl -b semanticfit.cookies 'http://localhost:5000/api/v1/admin/audit/export?format=json'
```

Protected write requests require both the cookie and `X-CSRF-Token`. For example:

```bash
curl -b semanticfit.cookies \
	-X POST http://localhost:5000/api/v1/admin/logout \
	-H 'X-CSRF-Token: TOKEN_FROM_LOGIN'
```

The `admin / admin123` account is for local development only and is rejected by the application in production. Never publish the cookie file or CSRF token.

## Endpoint index

| Method | Path | Authentication |
|---|---|---|
| `GET` | `/api/v1/health` | None |
| `GET` | `/api/v1/ready` | None |
| `POST` | `/api/v1/recommendations` | None |
| `GET` | `/api/v1/products/{parent_asin}` | None |
| `GET` | `/api/v1/categories` | None |
| `GET` | `/api/v1/search/suggestions` | None |
| `POST` | `/api/v1/feedback` | None |
| `POST` | `/api/v1/admin/login` | None |
| `POST` | `/api/v1/admin/logout` | Session + CSRF |
| `GET` | `/api/v1/admin/session` | None |
| `GET` | `/api/v1/admin/dashboard` | Admin session |
| `GET` | `/api/v1/admin/ingestion/jobs` | Admin session |
| `GET` | `/api/v1/admin/ingestion/jobs/{job_id}` | Admin session |
| `GET` | `/api/v1/admin/search-usage` | Admin session |
| `GET` | `/api/v1/admin/audit` | Admin session |
| `GET` | `/api/v1/admin/audit/export` | Admin session |
| `GET` | `/api/v1/admin/feedback` | Admin session |
| `GET` | `/api/v1/admin/evaluations` | Admin session |
| `GET` | `/api/v1/admin/evaluations/{run_id}` | Admin session |
| `GET` | `/api/v1/admin/system` | Admin session |
| `GET` | `/metrics` | None |

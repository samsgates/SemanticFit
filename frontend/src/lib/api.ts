export type SearchFilters = {
  min_price?: number | null
  max_price?: number | null
  min_rating?: number | null
  category?: string | null
  store?: string | null
}

export type ProductResult = {
  product_id: string
  parent_asin: string
  title: string
  main_category?: string | null
  price?: number | null
  rating?: number | null
  rating_count: number
  store?: string | null
  categories: string[]
  image?: string | null
  thumbnail?: string | null
  score: number
  match_percent: number
  reason: string
  score_breakdown?: Record<string, number>
}

export type SearchResponse = {
  request_id: string
  query: string
  intent: Record<string, unknown>
  filters: SearchFilters
  results: ProductResult[]
  meta: {
    retrieved: number
    reranked: number
    returned: number
    latency_ms: number
    cache_hit: boolean
    llm_used: boolean
  }
  debug?: Record<string, number>
}

const sessionKey = 'semanticfit_session_id'
export function sessionId() {
  let value = localStorage.getItem(sessionKey)
  if (!value) {
    value = crypto.randomUUID()
    localStorage.setItem(sessionKey, value)
  }
  return value
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const csrfToken = localStorage.getItem('semanticfit_csrf')
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': sessionId(),
      ...(csrfToken ? {'X-CSRF-Token': csrfToken} : {}),
      ...(init?.headers || {})
    }
  })
  const data = await response.json().catch(() => ({}))
  if (data?.csrf_token) localStorage.setItem('semanticfit_csrf', data.csrf_token)
  if (!response.ok) {
    throw new Error(data?.error?.message || `Request failed (${response.status})`)
  }
  return data
}

export const api = {
  search: (query: string, limit = 12, filters: SearchFilters = {}) =>
    request<SearchResponse>('/api/v1/recommendations', {
      method: 'POST',
      body: JSON.stringify({ query, limit, filters, session_id: sessionId() })
    }),
  product: (id: string) => request<any>(`/api/v1/products/${encodeURIComponent(id)}`),
  suggestions: (q = '') => request<{suggestions: string[]}>(`/api/v1/search/suggestions?q=${encodeURIComponent(q)}`),
  feedback: (payload: Record<string, unknown>) => request('/api/v1/feedback', { method: 'POST', body: JSON.stringify({ ...payload, session_id: sessionId() }) }),
  adminLogin: (username: string, password: string) => request<{ok: boolean; username: string; csrf_token: string}>('/api/v1/admin/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  adminLogout: () => request('/api/v1/admin/logout', { method: 'POST' }),
  adminSession: () => request<{authenticated: boolean; username?: string; csrf_token?: string}>('/api/v1/admin/session'),
  adminDashboard: () => request<any>('/api/v1/admin/dashboard'),
  adminUsage: () => request<any>('/api/v1/admin/search-usage?limit=250'),
  adminAudit: () => request<any>('/api/v1/admin/audit?limit=300'),
  adminFeedback: () => request<any>('/api/v1/admin/feedback?limit=300'),
  adminEvaluations: () => request<any>('/api/v1/admin/evaluations'),
  adminIngestion: () => request<any>('/api/v1/admin/ingestion/jobs'),
  adminSystem: () => request<any>('/api/v1/admin/system')
}

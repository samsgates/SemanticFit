import { Filter, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Header from '../components/Header'
import IntentBar from '../components/IntentBar'
import ProductCard from '../components/ProductCard'
import SearchBox from '../components/SearchBox'
import SkeletonGrid from '../components/SkeletonGrid'
import { api, SearchFilters } from '../lib/api'

export default function SearchPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const query = params.get('q') || ''
  const [filters, setFilters] = useState<SearchFilters>({})
  const [mobileFilters, setMobileFilters] = useState(false)
  useEffect(() => setMobileFilters(false), [query])
  const queryKey = useMemo(() => ['search', query, filters], [query, filters])
  const search = useQuery({
    queryKey,
    queryFn: () => api.search(query, 12, filters),
    enabled: Boolean(query)
  })
  const go = (value: string) => navigate(`/search?q=${encodeURIComponent(value)}`)
  return <div>
    <Header/>
    <main className="search-page container">
      <div className="search-top"><SearchBox initial={query} onSubmit={go} loading={search.isFetching}/></div>
      {query && <div className="results-title"><div><span className="section-kicker">Semantic results</span><h1>Fits for “{query}”</h1></div><button className="filter-mobile-button" onClick={()=>setMobileFilters(true)}><SlidersHorizontal size={17}/> Filters</button></div>}
      {search.data && <IntentBar intent={search.data.intent} latency={search.data.meta.latency_ms} llm={search.data.meta.llm_used}/>} 
      <div className="results-layout">
        <aside className={`filters-panel ${mobileFilters ? 'mobile-open' : ''}`}>
          <div className="filters-head"><strong><Filter size={17}/> Refine</strong><button className="mobile-close" onClick={()=>setMobileFilters(false)}><X/></button></div>
          <label>Max price <input type="number" min="0" value={filters.max_price ?? ''} placeholder="Any" onChange={e=>setFilters(f=>({...f,max_price:e.target.value ? Number(e.target.value):null}))}/></label>
          <label>Minimum rating
            <select value={filters.min_rating ?? ''} onChange={e=>setFilters(f=>({...f,min_rating:e.target.value ? Number(e.target.value):null}))}>
              <option value="">Any rating</option><option value="4">4.0+</option><option value="4.3">4.3+</option><option value="4.5">4.5+</option><option value="4.7">4.7+</option>
            </select>
          </label>
          <label>Category <input value={filters.category ?? ''} placeholder="e.g. Dresses" onChange={e=>setFilters(f=>({...f,category:e.target.value || null}))}/></label>
          <button className="clear-button" onClick={()=>setFilters({})}>Clear filters</button>
          <div className="filter-tip"><Sparkles size={16}/><p>Tip: describe style, occasion and material in your query. Use filters only for hard constraints.</p></div>
        </aside>
        <section className="results-content">
          {search.isLoading || search.isFetching ? <SkeletonGrid/> : search.isError ? <div className="error-state"><h3>Search unavailable</h3><p>{(search.error as Error).message}</p><button onClick={()=>search.refetch()}>Try again</button></div> : search.data?.results.length ? <div className="product-grid">{search.data.results.map(product=><ProductCard key={product.product_id} product={product} requestId={search.data!.request_id}/>)}</div> : query ? <EmptyState/> : null}
          {search.data && <div className="results-foot">Retrieved {search.data.meta.retrieved} candidates, reranked {search.data.meta.reranked}, returned {search.data.meta.returned} in {search.data.meta.latency_ms.toFixed(0)} ms.</div>}
        </section>
      </div>
    </main>
  </div>
}

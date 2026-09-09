import { ArrowRight, Search, Sparkles } from 'lucide-react'
import { FormEvent, useState } from 'react'

export default function SearchBox({
  initial = '',
  onSubmit,
  large = false,
  loading = false
}: {
  initial?: string
  onSubmit: (query: string) => void
  large?: boolean
  loading?: boolean
}) {
  const [value, setValue] = useState(initial)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const query = value.trim()
    if (query) onSubmit(query)
  }
  return (
    <form className={`search-box ${large ? 'search-box-large' : ''}`} onSubmit={submit}>
      <span className="search-icon"><Search size={large ? 22 : 18}/></span>
      <input
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Describe what you need, the occasion, style, weather or budget..."
        aria-label="Search products with natural language"
      />
      <button type="submit" className="search-submit" disabled={loading || !value.trim()}>
        {loading ? <span className="spinner"/> : large ? <><Sparkles size={17}/> Discover</> : <ArrowRight size={18}/>} 
      </button>
    </form>
  )
}

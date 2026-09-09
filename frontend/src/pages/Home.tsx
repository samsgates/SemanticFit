import { ArrowUpRight, BrainCircuit, Layers3, Search, ShieldCheck, Sparkles, Target } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import SearchBox from '../components/SearchBox'

const prompts = [
  'Something elegant for a summer wedding',
  'Comfortable clothes for a long flight',
  'Lightweight clothes for hot weather',
  'Smart casual outfit for a business dinner'
]

export default function Home() {
  const navigate = useNavigate()
  const go = (query: string) => navigate(`/search?q=${encodeURIComponent(query)}`)
  return <div>
    <Header/>
    <main>
      <section className="hero">
        <div className="ambient ambient-one"/><div className="ambient ambient-two"/>
        <div className="eyebrow"><Sparkles size={14}/> Meaning-first product discovery</div>
        <h1>Search for what you <em>mean</em>,<br/>not just what products are called.</h1>
        <p className="hero-copy">SemanticFit understands occasion, style, weather, material and budget to surface fashion that actually fits your intent.</p>
        <div className="hero-search"><SearchBox large onSubmit={go}/></div>
        <div className="prompt-row">{prompts.map(prompt => <button key={prompt} onClick={() => go(prompt)}>{prompt}<ArrowUpRight size={14}/></button>)}</div>
        <div className="trust-strip"><span><BrainCircuit size={16}/> BGE-M3 semantic retrieval</span><span><Layers3 size={16}/> Hybrid vector search</span><span><Target size={16}/> Cross-encoder reranking</span><span><ShieldCheck size={16}/> LLM optional</span></div>
      </section>

      <section className="section container">
        <div className="section-kicker">Designed for human intent</div>
        <div className="section-heading"><h2>From a thought to a ranked recommendation.</h2><p>SemanticFit separates understanding, retrieval and ranking so every layer can be measured, replaced and improved independently.</p></div>
        <div className="feature-grid">
          <article className="feature-card"><span>01</span><Search/><h3>Natural language</h3><p>Ask for an occasion, climate, mood or budget instead of guessing catalog keywords.</p></article>
          <article className="feature-card"><span>02</span><BrainCircuit/><h3>Hybrid retrieval</h3><p>Dense semantic vectors and sparse lexical signals are fused in Qdrant.</p></article>
          <article className="feature-card"><span>03</span><Target/><h3>Precision reranking</h3><p>A BGE cross-encoder reviews the strongest candidates before final scoring.</p></article>
        </div>
      </section>

      <section className="pipeline-section">
        <div className="container pipeline-inner">
          <div><div className="section-kicker">Transparent by design</div><h2>Search you can inspect.</h2><p>Every recommendation can expose its semantic, reranker, quality, popularity and intent-alignment signals for evaluation and debugging.</p></div>
          <div className="pipeline-card">
            {['Natural-language query','Intent processing','BGE-M3 dense + sparse','Qdrant RRF retrieval','BGE reranker','Quality + diversity ranking','Recommended products'].map((x,i)=><div className="pipeline-step" key={x}><span>{String(i+1).padStart(2,'0')}</span><strong>{x}</strong></div>)}
          </div>
        </div>
      </section>
    </main>
    <footer className="footer"><div className="brand"><span className="brand-mark">S</span><span>SemanticFit</span></div><p>Open-source semantic recommendation architecture.</p></footer>
  </div>
}

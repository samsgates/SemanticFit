import { BrainCircuit, Database, GitMerge, Layers3, Search, Target } from 'lucide-react'
import Header from '../components/Header'

const steps = [
  [Search,'1. Query','A user describes a need in ordinary language, including occasion, style, weather and budget when useful.'],
  [BrainCircuit,'2. Intent','Deterministic parsing extracts hard constraints. An optional LLM can improve complex intent understanding without becoming the search engine.'],
  [Layers3,'3. Embed','BGE-M3 produces dense semantic and sparse lexical representations from the query.'],
  [Database,'4. Retrieve','Qdrant runs hybrid retrieval and Reciprocal Rank Fusion with structured metadata filters.'],
  [Target,'5. Rerank','BGE reranker scores the strongest query-product pairs with a cross-encoder.'],
  [GitMerge,'6. Rank & diversify','Semantic relevance is combined with rating confidence, popularity and intent alignment, then category repetition is reduced.']
] as const

export default function HowItWorks(){return <div><Header/><main className="container how-page"><div className="how-hero"><span className="section-kicker">Architecture</span><h1>A recommendation pipeline you can reason about.</h1><p>SemanticFit deliberately separates retrieval from generation so relevance can be evaluated independently of an LLM.</p></div><div className="how-grid">{steps.map(([Icon,title,body])=><article key={title}><div className="how-icon"><Icon/></div><h2>{title}</h2><p>{body}</p></article>)}</div><section className="architecture-box"><h2>Core online path</h2><div className="architecture-flow">{['Query','Intent','BGE-M3','Qdrant','Reranker','Ranker','Results'].map((x,i)=><div key={x}><span>{x}</span>{i<6&&<b>→</b>}</div>)}</div></section></main></div>}

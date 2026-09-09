import { BrainCircuit, Gauge, Sparkles } from 'lucide-react'

export default function IntentBar({ intent, latency, llm }: { intent: Record<string, unknown>; latency: number; llm: boolean }) {
  const chips: string[] = []
  for (const key of ['occasion', 'season', 'weather', 'style', 'materials', 'colors']) {
    const values = intent[key]
    if (Array.isArray(values)) chips.push(...values.map(v => String(v)))
  }
  return (
    <div className="intent-bar">
      <div className="intent-title"><BrainCircuit size={18}/> Understood intent</div>
      <div className="intent-chips">
        {chips.length ? chips.slice(0, 10).map(x => <span key={x} className="chip">{x}</span>) : <span className="muted">Semantic meaning extracted directly from your query</span>}
      </div>
      <div className="intent-stats">
        <span><Gauge size={14}/>{latency.toFixed(0)} ms</span>
        <span><Sparkles size={14}/>{llm ? 'LLM assisted' : 'local retrieval'}</span>
      </div>
    </div>
  )
}

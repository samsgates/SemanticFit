import { SearchX } from 'lucide-react'

export default function EmptyState() {
  return <div className="empty-state">
    <div className="empty-icon"><SearchX size={26}/></div>
    <h3>No strong matches yet</h3>
    <p>Try removing a price constraint, using a broader style description, or naming the occasion instead of a specific product.</p>
  </div>
}

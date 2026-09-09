import { Heart, Star, ThumbsDown, ThumbsUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ProductResult } from '../lib/api'
import { api } from '../lib/api'

function price(value?: number | null) {
  return value == null ? 'Price unavailable' : `$${value.toFixed(2)}`
}

export default function ProductCard({ product, requestId }: { product: ProductResult; requestId: string }) {
  const feedback = async (kind: 'helpful' | 'not_relevant') => {
    try { await api.feedback({ request_id: requestId, product_id: product.product_id, feedback_type: kind }) } catch { /* optional */ }
  }
  return (
    <article className="product-card">
      <Link className="product-image-wrap" to={`/product/${product.product_id}`} onClick={() => api.feedback({request_id: requestId, product_id: product.product_id, feedback_type: 'click'}).catch(()=>{})}>
        {product.image ? <img src={product.image} alt={product.title} loading="lazy"/> : <div className="product-placeholder"><Heart size={36}/></div>}
        <span className="match-badge">{product.match_percent}% match</span>
      </Link>
      <div className="product-body">
        <div className="product-meta-row">
          <span className="product-category">{product.categories?.slice(-1)[0] || product.main_category || 'Fashion'}</span>
          {product.rating != null && <span className="rating"><Star size={14} fill="currentColor"/> {product.rating.toFixed(1)} <small>({product.rating_count?.toLocaleString()})</small></span>}
        </div>
        <Link to={`/product/${product.product_id}`} className="product-title">{product.title}</Link>
        <div className="product-price">{price(product.price)}</div>
        <div className="fit-reason"><span>Why it fits</span><p>{product.reason}</p></div>
        <div className="product-actions">
          <Link to={`/product/${product.product_id}`} className="secondary-button">Explore</Link>
          <button className="mini-button" title="Helpful" onClick={() => feedback('helpful')}><ThumbsUp size={15}/></button>
          <button className="mini-button" title="Not relevant" onClick={() => feedback('not_relevant')}><ThumbsDown size={15}/></button>
        </div>
      </div>
    </article>
  )
}

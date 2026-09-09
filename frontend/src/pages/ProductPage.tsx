import { ArrowLeft, CheckCircle2, Heart, Star } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import Header from '../components/Header'
import { api } from '../lib/api'

export default function ProductPage() {
  const { id = '' } = useParams()
  const product = useQuery({ queryKey:['product',id], queryFn:()=>api.product(id), enabled:Boolean(id) })
  const data = product.data
  return <div><Header/><main className="container product-page">
    <Link to="/search" className="back-link"><ArrowLeft size={16}/> Back to discovery</Link>
    {product.isLoading ? <div className="product-detail-skeleton skeleton"/> : product.isError ? <div className="error-state"><h3>Product unavailable</h3><p>{(product.error as Error).message}</p></div> : data && <div className="product-detail-grid">
      <div className="product-gallery">
        <div className="product-main-image">{data.primary_image ? <img src={data.primary_image} alt={data.title}/> : <Heart size={48}/>}</div>
        <div className="thumbnail-row">{(data.images||[]).slice(0,5).map((image:any,i:number)=><div className="thumbnail" key={i}>{image.thumb || image.large ? <img src={image.thumb || image.large} alt=""/>:null}</div>)}</div>
      </div>
      <div className="product-detail-copy">
        <span className="section-kicker">{data.categories?.join(' / ') || data.main_category}</span>
        <h1>{data.title}</h1>
        <div className="detail-rating">{data.average_rating != null && <><Star fill="currentColor" size={17}/><strong>{data.average_rating.toFixed(1)}</strong><span>{Number(data.rating_number||0).toLocaleString()} ratings</span></>}</div>
        <div className="detail-price">{data.price != null ? `$${Number(data.price).toFixed(2)}` : 'Price unavailable'}</div>
        {data.store && <div className="store-pill">Store: {data.store}</div>}
        {!!data.features?.length && <section className="detail-section"><h2>Highlights</h2><ul className="feature-list">{data.features.slice(0,10).map((x:string)=><li key={x}><CheckCircle2 size={17}/><span>{x}</span></li>)}</ul></section>}
        {!!data.description?.length && <section className="detail-section"><h2>Description</h2>{data.description.slice(0,6).map((x:string,i:number)=><p key={i}>{x}</p>)}</section>}
        {data.details && Object.keys(data.details).length > 0 && <section className="detail-section"><h2>Product details</h2><div className="details-table">{Object.entries(data.details).slice(0,24).map(([k,v])=><div key={k}><span>{k}</span><strong>{Array.isArray(v)?v.join(', '):String(v ?? '')}</strong></div>)}</div></section>}
      </div>
    </div>}
  </main></div>
}

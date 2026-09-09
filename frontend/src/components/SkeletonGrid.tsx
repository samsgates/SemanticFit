export default function SkeletonGrid() {
  return <div className="product-grid">{Array.from({length: 8}).map((_, i) => <div className="product-card skeleton-card" key={i}><div className="skeleton image-skeleton"/><div className="product-body"><div className="skeleton line short"/><div className="skeleton line"/><div className="skeleton line medium"/><div className="skeleton box"/></div></div>)}</div>
}

import { Activity, ClipboardCheck, Database, Gauge, LogOut, MessageSquareText, Search, Settings, ShieldCheck } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const items = [
  ['/admin', Gauge, 'Overview'],
  ['/admin/usage', Search, 'Search usage'],
  ['/admin/audit', ShieldCheck, 'Audit logs'],
  ['/admin/evaluations', ClipboardCheck, 'Evaluations'],
  ['/admin/feedback', MessageSquareText, 'Feedback'],
  ['/admin/ingestion', Database, 'Ingestion'],
  ['/admin/system', Activity, 'System health']
] as const

export default function AdminLayout() {
  const navigate = useNavigate()
  const logout = async () => { try { await api.adminLogout() } finally { navigate('/admin/login') } }
  return <div className="admin-shell">
    <aside className="admin-sidebar">
      <div className="admin-brand"><span className="brand-mark">S</span><div><strong>SemanticFit</strong><small>Control room</small></div></div>
      <nav>{items.map(([to, Icon, label]) => <NavLink end={to === '/admin'} to={to} key={to} className={({isActive}) => `admin-nav-link ${isActive ? 'active' : ''}`}><Icon size={18}/>{label}</NavLink>)}</nav>
      <div className="admin-sidebar-foot">
        <NavLink to="/" className="admin-nav-link"><Settings size={18}/> Public site</NavLink>
        <button onClick={logout} className="admin-nav-link"><LogOut size={18}/> Sign out</button>
      </div>
    </aside>
    <main className="admin-main"><Outlet/></main>
  </div>
}

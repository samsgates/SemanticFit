import { LockKeyhole, ShieldCheck } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

export default function AdminLogin(){
  const [username,setUsername]=useState('admin')
  const [password,setPassword]=useState('admin123')
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(false)
  const navigate=useNavigate()
  const submit=async(e:FormEvent)=>{e.preventDefault();setLoading(true);setError('');try{await api.adminLogin(username,password);navigate('/admin')}catch(err){setError((err as Error).message)}finally{setLoading(false)}}
  return <div className="login-page"><div className="login-ambient"/><form className="login-card" onSubmit={submit}><div className="login-logo"><span className="brand-mark">S</span><div><strong>SemanticFit</strong><small>Admin control room</small></div></div><div className="login-icon"><ShieldCheck/></div><h1>Welcome back</h1><p>Review search quality, ingestion, audit history and feedback signals.</p><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username"/></label><label>Password<div className="password-input"><LockKeyhole size={16}/><input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password"/></div></label>{error&&<div className="login-error">{error}</div>}<button className="primary-button full" disabled={loading}>{loading?'Signing in...':'Sign in'}</button><div className="demo-note"><strong>Development account</strong><span>admin / admin123</span><small>Change these credentials before production deployment.</small></div></form></div>
}

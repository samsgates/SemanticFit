import { Github, Moon, Search, Shield, Sun } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'

export default function Header() {
  const [dark, setDark] = useState(() => localStorage.getItem('semanticfit_theme') !== 'light')
  const location = useLocation()
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('semanticfit_theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <header className="site-header">
      <Link to="/" className="brand" aria-label="SemanticFit home">
        <span className="brand-mark">S</span>
        <span>SemanticFit</span>
      </Link>
      <nav className="top-nav" aria-label="Primary">
        {location.pathname !== '/' && <Link to="/search" className="nav-link"><Search size={16}/> Search</Link>}
        <Link to="/how-it-works" className="nav-link">How it works</Link>
        <Link to="/admin" className="nav-link"><Shield size={16}/> Admin</Link>
        <a className="icon-button" href="https://github.com/" target="_blank" rel="noreferrer" aria-label="GitHub"><Github size={18}/></a>
        <button className="icon-button" onClick={() => setDark(v => !v)} aria-label="Toggle theme">
          {dark ? <Sun size={18}/> : <Moon size={18}/>} 
        </button>
      </nav>
    </header>
  )
}

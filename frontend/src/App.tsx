import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AdminLayout from './components/AdminLayout'
import { api } from './lib/api'
import AdminLogin from './pages/AdminLogin'
import Home from './pages/Home'
import HowItWorks from './pages/HowItWorks'
import ProductPage from './pages/ProductPage'
import SearchPage from './pages/SearchPage'
import Audit from './pages/admin/Audit'
import Dashboard from './pages/admin/Dashboard'
import Evaluations from './pages/admin/Evaluations'
import FeedbackPage from './pages/admin/Feedback'
import Ingestion from './pages/admin/Ingestion'
import System from './pages/admin/System'
import Usage from './pages/admin/Usage'

function ProtectedAdmin(){const location=useLocation();const q=useQuery({queryKey:['admin-session'],queryFn:api.adminSession,retry:false});if(q.isLoading)return <div className="route-loader"><span className="spinner"/></div>;if(!q.data?.authenticated)return <Navigate to="/admin/login" replace state={{from:location}}/>;return <AdminLayout/>}

export default function App(){return <Routes><Route path="/" element={<Home/>}/><Route path="/search" element={<SearchPage/>}/><Route path="/product/:id" element={<ProductPage/>}/><Route path="/how-it-works" element={<HowItWorks/>}/><Route path="/admin/login" element={<AdminLogin/>}/><Route path="/admin" element={<ProtectedAdmin/>}><Route index element={<Dashboard/>}/><Route path="usage" element={<Usage/>}/><Route path="audit" element={<Audit/>}/><Route path="evaluations" element={<Evaluations/>}/><Route path="feedback" element={<FeedbackPage/>}/><Route path="ingestion" element={<Ingestion/>}/><Route path="system" element={<System/>}/></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}

import {lazy,Suspense,useEffect,useState} from 'react';
import {Navigate,Route,Routes} from 'react-router-dom';
import {api,clearSession} from './lib/api';
import type {User} from './types';
import Layout from './components/Layout';

const Landing=lazy(()=>import('./pages/Landing'));
const Auth=lazy(()=>import('./pages/Auth'));
const Report=lazy(()=>import('./pages/Report'));
const IssueMap=lazy(()=>import('./pages/IssueMap'));
const Detail=lazy(()=>import('./pages/Detail'));
const Dashboard=lazy(()=>import('./pages/Dashboard'));
const Analytics=lazy(()=>import('./pages/Analytics'));
const Profile=lazy(()=>import('./pages/Profile'));
const Moderation=lazy(()=>import('./pages/Moderation'));
const Legal=lazy(()=>import('./pages/Legal'));
const NotFound=lazy(()=>import('./pages/NotFound'));

const loading=<div className="grid min-h-[60vh] place-items-center text-civic" role="status">Loading CivicLens…</div>;

export default function App(){
  const [user,setUser]=useState<User|null>(null);
  const [ready,setReady]=useState(false);
  useEffect(()=>{if(localStorage.getItem('token'))api<User>('/api/auth/me').then(setUser).catch(()=>clearSession()).finally(()=>setReady(true));else setReady(true)},[]);
  if(!ready)return loading;
  const secure=(element:React.ReactNode,admin=false)=>!user?<Navigate to="/login"/>:admin&&user.role!=='admin'?<Navigate to="/unauthorized"/>:element;
  return <Layout user={user} setUser={setUser}><Suspense fallback={loading}><Routes>
    <Route path="/" element={<Landing/>}/><Route path="/login" element={<Auth mode="login" setUser={setUser}/>}/><Route path="/register" element={<Auth mode="register" setUser={setUser}/>}/>
    <Route path="/report" element={secure(<Report user={user!}/>)}/><Route path="/map" element={<IssueMap/>}/><Route path="/complaints/:id" element={<Detail user={user}/>}/>
    <Route path="/dashboard" element={secure(<Dashboard admin={false}/>)}/><Route path="/admin" element={secure(<Dashboard admin/>,true)}/><Route path="/admin/moderation" element={secure(<Moderation/>,true)}/>
    <Route path="/analytics" element={<Analytics/>}/><Route path="/profile" element={secure(<Profile user={user!} setUser={setUser}/>)}/>
    <Route path="/privacy" element={<Legal kind="privacy"/>}/><Route path="/terms" element={<Legal kind="terms"/>}/><Route path="/grievance" element={<Legal kind="grievance"/>}/>
    <Route path="/unauthorized" element={<NotFound unauthorized/>}/><Route path="*" element={<NotFound/>}/>
  </Routes></Suspense></Layout>;
}

import {useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Bell,CheckCheck} from 'lucide-react';
import {Link} from 'react-router-dom';
import {api} from '../lib/api';

type Notification={id:string;title:string;message:string;is_read:boolean;complaint_id?:string;created_at:string};
type Response={items:Notification[];total:number;unread:number};

export default function NotificationCenter(){
  const [open,setOpen]=useState(false);const qc=useQueryClient();
  const {data}=useQuery({queryKey:['notifications'],queryFn:()=>api<Response>('/api/notifications?page_size=10'),refetchInterval:60000});
  const read=useMutation({mutationFn:(id:string)=>api(`/api/notifications/${id}/read`,{method:'PATCH'}),onSuccess:()=>qc.invalidateQueries({queryKey:['notifications']})});
  const readAll=useMutation({mutationFn:()=>api('/api/notifications/read-all',{method:'POST'}),onSuccess:()=>qc.invalidateQueries({queryKey:['notifications']})});
  return <div className="relative"><button aria-label="Notifications" className="btn-secondary relative p-2.5" onClick={()=>setOpen(!open)}><Bell size={18}/>{!!data?.unread&&<span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{data.unread>99?'99+':data.unread}</span>}</button>{open&&<div className="absolute right-0 top-12 z-50 w-[min(380px,90vw)] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"><div className="flex items-center justify-between border-b p-4 dark:border-slate-700"><div><b>Notifications</b><p className="text-xs text-slate-400">{data?.unread||0} unread</p></div><button className="btn px-2 text-xs text-civic" disabled={!data?.unread} onClick={()=>readAll.mutate()}><CheckCheck size={15}/>Read all</button></div><div className="max-h-96 overflow-y-auto">{data?.items.map(item=><Link key={item.id} to={item.complaint_id?`/complaints/${item.complaint_id}`:'#'} onClick={()=>{if(!item.is_read)read.mutate(item.id);setOpen(false)}} className={`block border-b p-4 dark:border-slate-800 ${item.is_read?'':'bg-blue-50 dark:bg-blue-950/30'}`}><div className="flex justify-between gap-2"><b className="text-sm">{item.title}</b>{!item.is_read&&<span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-civic"/>}</div><p className="mt-1 text-sm text-slate-500">{item.message}</p><p className="mt-2 text-xs text-slate-400">{new Date(item.created_at).toLocaleString()}</p></Link>)}{!data?.items.length&&<p className="p-8 text-center text-sm text-slate-400">No notifications yet.</p>}</div></div>}</div>;
}

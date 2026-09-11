'use client';
import { useCallback,useEffect,useState } from 'react';
import { useParams,useRouter } from 'next/navigation';
import { ArrowLeft,CalendarDays,Gauge } from 'lucide-react';
import { api,ApiRequestError } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import type { ClientRead,ProfessionalRead,ProjectRead } from '@/types';
import { WorkBoardPrototype } from './WorkBoardPrototype';
import styles from '../assignments.module.css';

const date=(v:string|null)=>v?new Date(v).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'Not scheduled';
export default function ProjectDetail(){
 const id=useParams().id as string,router=useRouter();
 const[project,setProject]=useState<ProjectRead|null>(null),[client,setClient]=useState<ClientRead|null>(null),[people,setPeople]=useState<ProfessionalRead[]>([]),[capacity,setCapacity]=useState(0),[available,setAvailable]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null);
 const load=useCallback(async()=>{setLoading(true);setError(null);try{const[p,c,professionals]=await Promise.all([api.get<ProjectRead>(`/assignments/projects/${id}`),api.get<{total_capacity_allocated_pct:number;available_headcount:number}>('/assignments/capacity'),api.get<ProfessionalRead[]>('/people/?limit=100')]);setProject(p);setCapacity(c.total_capacity_allocated_pct);setAvailable(c.available_headcount);setPeople(professionals);if(p.client_id)setClient(await api.get<ClientRead>(`/clients/${p.client_id}`))}catch(e){setError(e instanceof ApiRequestError?e.userMessage:'Unable to load project.')}finally{setLoading(false)}},[id]);
 useEffect(()=>{load()},[load]);
 if(loading)return <Skeleton width="100%" height="320px"/>;
 if(error||!project)return <ErrorState type="error" message={error||'Project not found.'} onRetry={load}/>;
 return <div className="fade-in">
  <button className={styles.detailBack} onClick={()=>router.push('/assignments')}><ArrowLeft size={16}/>Back to boards</button>
  <div className={styles.detailHeader}><div><div className={styles.detailTitleGroup}><h2 className={styles.detailTitle}>{project.name}</h2><span className={styles.projectCode}>{project.code}</span><Badge projectStatus={project.status}/></div><p className={styles.pageSubtitle}>Project-backed delivery board</p></div></div>
  <div className={styles.detailGrid}>
   <Card><h3 className={styles.sectionTitle}>Board overview</h3><div className={styles.fieldRow}><span className={styles.fieldLabel}>Client</span><span className={styles.fieldValue}>{client?.name||'No client linked'}</span></div><div className={styles.fieldRow}><span className={styles.fieldLabel}>Contact</span><span className={styles.fieldValue}>{client?.contact_email||'Not provided'}</span></div></Card>
   <Card><h3 className={styles.sectionTitle}><CalendarDays size={16}/>Timeline</h3><div className={styles.fieldRow}><span className={styles.fieldLabel}>Start</span><span className={styles.fieldValue}>{date(project.start_date)}</span></div><div className={styles.fieldRow}><span className={styles.fieldLabel}>Target end</span><span className={styles.fieldValue}>{date(project.target_end_date)}</span></div></Card>
   <Card><h3 className={styles.sectionTitle}><Gauge size={16}/>Organization capacity</h3><div className={styles.capacitySummary}><div className={styles.capacityRing} style={{background:`conic-gradient(var(--color-brand-accent) ${Math.min(capacity,100)*3.6}deg,var(--color-surface-secondary) 0)`}}><span>{capacity}%</span></div><div><strong>{available}</strong><p>available professionals</p></div></div></Card>
  </div>
  <WorkBoardPrototype people={people}/>
 </div>
}

'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, CheckCircle2, ClipboardCheck, Columns3, FileCheck2, Filter, Gauge, LockKeyhole, Search, Users } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { api, ApiRequestError } from '@/lib/api';
import { Card } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import type { ProfessionalRead, ProjectRead } from '@/types';
import styles from './work.module.css';

const lanes = [
  ['Backlog','slate'], ['Todo','blue'], ['In progress','violet'],
  ['Blocked','red'], ['In review','amber'], ['Completed','green'],
] as const;

export default function WorkPage() {
  const { user } = useAuth();
  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [utilization, setUtilization] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [p, pr, capacity] = await Promise.all([
        api.get<ProfessionalRead[]>('/people/?limit=100'),
        api.get<ProjectRead[]>('/assignments/projects?limit=100'),
        api.get<{total_capacity_allocated_pct:number}>('/assignments/capacity'),
      ]);
      setPeople(p); setProjects(pr); setUtilization(capacity.total_capacity_allocated_pct);
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.userMessage : 'Unable to load work context.');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const active = useMemo(() => projects.filter(p =>
    p.status === 'active' && (!query || `${p.name} ${p.code}`.toLowerCase().includes(query.toLowerCase()))
  ), [projects, query]);
  if (error) return <ErrorState type="error" message={error} onRetry={load}/>;

  return <div className="fade-in">
    <header className={styles.hero}>
      <div><span className={styles.eyebrow}>Delivery command center</span><h2>Work Management</h2><p>Plan, govern and inspect delivery across one operational workspace.</p></div>
      <span className={styles.dependency}><LockKeyhole size={14}/>Ticket API pending</span>
    </header>
    <div className={styles.toolbar}>
      <label><Search size={16}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search project context…"/></label>
      <button><Filter size={15}/>Filters</button><span>{user?.role === 'ADMIN' ? 'Organization' : user?.role === 'MANAGER' ? 'My team' : 'My work'}</span>
    </div>
    {loading ? <div className={styles.metrics}>{[1,2,3,4].map(i => <Card key={i}><Skeleton height="62px" width="100%"/></Card>)}</div> :
      <div className={styles.metrics}>
        <Metric icon={<Columns3/>} value={active.length} label="Active projects"/>
        <Metric icon={<Users/>} value={people.length} label="Professionals"/>
        <Metric icon={<Gauge/>} value={`${Math.round(utilization)}%`} label="Capacity used"/>
        <Metric icon={<CheckCircle2/>} value={people.filter(p => p.status === 'ready').length} label="Ready to deploy"/>
      </div>}
    <div className={styles.notice}><AlertTriangle size={20}/><div><strong>Board actions are safely locked</strong><p>The seeded backend has no ticket, comment, checklist or transition endpoints. Live portfolio context is shown, but DWOP will not pretend drag-and-drop changes were saved.</p></div></div>
    <section className={styles.section}>
      <Heading icon={<Columns3 size={18}/>} title="Delivery board" subtitle="Six-stage workflow with review and blocker controls" aside={`${active.length} projects in scope`}/>
      <div className={styles.board}>{lanes.map(([name,tone], index) =>
        <div className={styles.column} key={name}>
          <div className={styles.columnHeader}><span className={`${styles.dot} ${styles[tone]}`}/><strong>{name}</strong><b>—</b></div>
          {index === 0 && active.length ? <div className={styles.contextCards}>{active.slice(0,3).map(p =>
            <div className={styles.contextCard} key={p.id}><span>{p.code}</span><strong>{p.name}</strong><small>Project context · tickets pending API</small></div>
          )}</div> : <div className={styles.emptyLane}><ClipboardCheck size={20}/><p>No persisted tickets</p><small>Cards appear when the ticket API is connected.</small></div>}
        </div>)}</div>
    </section>
    <div className={styles.lowerGrid}>
      <section><Heading icon={<BarChart3 size={18}/>} title="Portfolio pulse" subtitle="Live records from the seeded backend"/><Card padded={false}>{loading ? <Skeleton height="160px" width="100%"/> : projects.length === 0 ? <p className={styles.noData}>No projects are available.</p> : projects.slice(0,5).map(p => <div className={styles.projectRow} key={p.id}><span className={styles.projectMark}/><div><strong>{p.name}</strong><small>{p.code}</small></div><span>{p.status.replaceAll('_',' ')}</span></div>)}</Card></section>
      <aside><Heading icon={<FileCheck2 size={18}/>} title="Governance rail" subtitle="Approval and control gates"/><Card><ol><Step n="1" title="Proposal submitted" text="Scope and acceptance criteria captured"/><Step n="2" title="Admin review" text="Authority, priority and capacity checked"/><Step n="3" title="Approved ticket" text="Created only by an authorized human"/><Step n="4" title="Audited delivery" text="Transitions and evidence retained"/></ol></Card></aside>
    </div>
  </div>;
}

function Metric({icon,value,label}:{icon:React.ReactNode;value:string|number;label:string}) { return <Card><div className={styles.metric}><span>{icon}</span><div><strong>{value}</strong><small>{label}</small></div></div></Card>; }
function Heading({icon,title,subtitle,aside}:{icon:React.ReactNode;title:string;subtitle:string;aside?:string}) { return <div className={styles.heading}><div><h3>{icon}{title}</h3><p>{subtitle}</p></div>{aside&&<span>{aside}</span>}</div>; }
function Step({n,title,text}:{n:string;title:string;text:string}) { return <li><span>{n}</span><div><strong>{title}</strong><small>{text}</small></div></li>; }

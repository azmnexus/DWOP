'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BarChart3, FolderKanban, Plus, Search, Users } from 'lucide-react';
import { api, ApiRequestError } from '@/lib/api';
import { isAdmin } from '@/lib/auth';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import type { AssignmentRead, ClientRead, ProfessionalRead, ProjectCreate, ProjectRead, ProjectStatus } from '@/types';
import styles from './assignments.module.css';
import uiStyles from '@/components/ui/ui.module.css';

const formatDate = (value: string | null) => value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';

export default function AssignmentsPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [clients, setClients] = useState<ClientRead[]>([]);
  const [assignments, setAssignments] = useState<AssignmentRead[]>([]);
  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<ProjectStatus | ''>('');
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ProjectCreate>({ name: '', code: '', client_id: '', status: 'active', start_date: null, target_end_date: null });
  const [averageCapacity, setAverageCapacity] = useState(0);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [p, c, capacity, professionals] = await Promise.all([
        api.get<ProjectRead[]>('/assignments/projects?limit=100'), api.get<ClientRead[]>('/clients/?limit=100'),
        api.get<{total_capacity_allocated_pct:number}>('/assignments/capacity'), api.get<ProfessionalRead[]>('/people/?limit=100'),
      ]);
      setProjects(p); setClients(c); setAssignments([]); setPeople(professionals); setAverageCapacity(capacity.total_capacity_allocated_pct);
    } catch (e) { setError(e instanceof ApiRequestError ? e.userMessage : 'Unable to load assignments.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => projects.filter(p => (!status || p.status === status) && `${p.name} ${p.code}`.toLowerCase().includes(query.toLowerCase())), [projects, query, status]);
  const available = people.filter(p => p.availability_status === 'available').length;
  const clientName = (id: string | null) => id ? clients.find(c => c.id === id)?.name || 'Unknown client' : 'No client';

  async function createProject(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.code.trim() || !form.client_id) return showToast('warning', 'Name, code, and client are required.');
    setSaving(true);
    try { await api.post<ProjectRead>('/assignments/projects', { ...form, name: form.name.trim(), code: form.code.trim().toUpperCase() }); showToast('success', 'Project created.'); setOpen(false); await load(); }
    catch (e) { showToast('error', e instanceof ApiRequestError ? e.userMessage : 'Unable to create project.'); }
    finally { setSaving(false); }
  }

  if (error) return <ErrorState type="error" message={error} onRetry={load} />;
  return <div className="fade-in">
    <div className={styles.capacityRow}>
      <div className={styles.statCard}><BarChart3 size={22} /><div><div className={styles.statValue}>{averageCapacity}%</div><div className={styles.statLabel}>Average allocation</div><div className={styles.capacityBar}><div className={styles.capacityFill} style={{ width: `${Math.min(averageCapacity, 100)}%` }} /></div></div></div>
      <div className={styles.statCard}><Users size={22} /><div><div className={styles.statValue}>{available}</div><div className={styles.statLabel}>Available professionals</div></div></div>
      <div className={styles.statCard}><FolderKanban size={22} /><div><div className={styles.statValue}>{projects.filter(p => p.status === 'active').length}</div><div className={styles.statLabel}>Active projects</div></div></div>
    </div>
    <div className={styles.pageHeader}><div><h2 className={styles.pageTitle}>Projects <span className={styles.pageCount}>{filtered.length} projects</span></h2><p className={styles.pageSubtitle}>Assignments, capacity, dates, and project staffing in one operational workspace.</p></div>{isAdmin() && <Button size="sm" onClick={() => setOpen(true)}><Plus size={16}/>New project</Button>}</div>
    <div className={styles.filtersBar}><div className={styles.searchInput}><Input aria-label="Search projects" icon={<Search size={18}/>} placeholder="Search name or code" value={query} onChange={e => setQuery(e.target.value)} /></div><div className={styles.filterSelect}><select aria-label="Filter project status" className={uiStyles.selectField} value={status} onChange={e => setStatus(e.target.value as ProjectStatus | '')}><option value="">All statuses</option><option value="active">Active</option><option value="on_hold">On hold</option><option value="completed">Completed</option></select></div></div>
    {loading ? <SkeletonTable rows={5}/> : filtered.length === 0 ? <EmptyState icon={<FolderKanban/>} title="No projects found" description="Projects returned by the DWOP API will appear here." /> : <>
      <div className={styles.tableWrapper}><table className={styles.table}><thead><tr><th>Project</th><th>Client</th><th>Status</th><th>Roster</th><th>Timeline</th></tr></thead><tbody>{filtered.map(p => <tr key={p.id} tabIndex={0} role="link" onClick={() => router.push(`/assignments/${p.id}`)} onKeyDown={e => e.key === 'Enter' && router.push(`/assignments/${p.id}`)}><td><span className={styles.projectName}>{p.name}</span><br/><span className={styles.projectCode}>{p.code}</span></td><td>{clientName(p.client_id)}</td><td><Badge projectStatus={p.status}/></td><td>{assignments.filter(a => a.project_id === p.id && a.status === 'active').length}</td><td className={styles.dateCell}>{formatDate(p.start_date)} – {formatDate(p.target_end_date)}</td></tr>)}</tbody></table></div>
      <div className={styles.cardGrid}>{filtered.map(p => <button key={p.id} className={styles.projectCard} onClick={() => router.push(`/assignments/${p.id}`)}><div className={styles.projectCardHeader}><span className={styles.projectCardName}>{p.name}</span><Badge projectStatus={p.status}/></div><div className={styles.projectCardMeta}><span>{clientName(p.client_id)}</span><span>{assignments.filter(a => a.project_id === p.id && a.status === 'active').length} active assignments</span><span>{formatDate(p.start_date)}</span></div></button>)}</div>
    </>}
    <Modal isOpen={open} onClose={() => setOpen(false)} title="New project"><form onSubmit={createProject}><div className={uiStyles.formGrid}><Input label="Project name" required value={form.name} onChange={e => setForm({...form,name:e.target.value})}/><Input label="Project code" required value={form.code} onChange={e => setForm({...form,code:e.target.value.toUpperCase()})}/><div className={uiStyles.inputWrapper}><label className={uiStyles.inputLabel}>Client</label><select required className={uiStyles.selectField} value={form.client_id||''} onChange={e => setForm({...form,client_id:e.target.value||null})}><option value="">Select client</option>{clients.map(c => <option value={c.id} key={c.id}>{c.name}</option>)}</select></div><div className={uiStyles.inputWrapper}><label className={uiStyles.inputLabel}>Status</label><select className={uiStyles.selectField} value={form.status} onChange={e => setForm({...form,status:e.target.value as ProjectStatus})}><option value="active">Active</option><option value="on_hold">On hold</option><option value="completed">Completed</option></select></div><div className={uiStyles.formRow}><Input label="Start date" type="date" onChange={e => setForm({...form,start_date:e.target.value||null})}/><Input label="Target end date" type="date" onChange={e => setForm({...form,target_end_date:e.target.value||null})}/></div></div><div className={uiStyles.modalActions}><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" loading={saving}>Create project</Button></div></form></Modal>
  </div>;
}

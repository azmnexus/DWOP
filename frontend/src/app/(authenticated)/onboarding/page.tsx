'use client';
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, ClipboardList, Play, ShieldCheck } from 'lucide-react';
import { api, ApiRequestError } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Modal } from '@/components/ui/Modal';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import type { OnboardingRunRead, OnboardingTemplateRead, ProfessionalRead } from '@/types';
import styles from './onboarding.module.css';
import ui from '@/components/ui/ui.module.css';

export default function OnboardingPage(){
 const {user}=useAuth(),{showToast}=useToast();
 const [templates,setTemplates]=useState<OnboardingTemplateRead[]>([]),[people,setPeople]=useState<ProfessionalRead[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null),[open,setOpen]=useState(false),[saving,setSaving]=useState(false),[professionalId,setProfessionalId]=useState(''),[templateId,setTemplateId]=useState(''),[lastRun,setLastRun]=useState<OnboardingRunRead|null>(null);
 const load=useCallback(async()=>{setLoading(true);setError(null);try{const[t,p]=await Promise.all([api.get<OnboardingTemplateRead[]>('/onboarding/templates'),api.get<ProfessionalRead[]>('/people/?limit=100')]);setTemplates(t);setPeople(p)}catch(e){setError(e instanceof ApiRequestError?e.userMessage:'Unable to load onboarding.')}finally{setLoading(false)}},[]);
 useEffect(()=>{load()},[load]);
 const active=templates.filter(t=>t.is_active),canStart=user?.role==='ADMIN'||user?.role==='MANAGER';
 async function start(e:React.FormEvent){e.preventDefault();setSaving(true);try{const run=await api.post<OnboardingRunRead>('/onboarding/runs',{professional_id:professionalId,template_id:templateId});setLastRun(run);setOpen(false);showToast('success','Onboarding run started.');await load()}catch(e){showToast('error',e instanceof ApiRequestError?e.userMessage:'Unable to start onboarding.')}finally{setSaving(false)}}
 if(error)return <ErrorState type="error" message={error} onRetry={load}/>;
 return <div className="fade-in"><div className={styles.header}><div><span>WORKFORCE READINESS</span><h2>Onboarding operations</h2><p>Role templates, governed checklist creation, and readiness visibility.</p></div>{canStart&&<Button onClick={()=>setOpen(true)}><Play size={16}/>Start onboarding</Button>}</div>
 {loading?<SkeletonTable rows={4}/>:<><div className={styles.metrics}><Card><ClipboardList/><strong>{active.length}</strong><small>Active templates</small></Card><Card><CheckCircle2/><strong>{people.filter(p=>p.status==='ready').length}</strong><small>Ready</small></Card><Card><ShieldCheck/><strong>{people.filter(p=>p.status==='onboarding').length}</strong><small>Onboarding</small></Card></div>{lastRun&&<div className={styles.success}><CheckCircle2/><div><strong>Run created</strong><p>{lastRun.items.length} checklist items · {lastRun.progress_pct}% complete</p></div></div>}<section className={styles.section}><h3>Role templates</h3>{active.length===0?<EmptyState icon={<ClipboardList/>} title="No templates available" description="No active onboarding template exists in the seeded backend."/>:<div className={styles.grid}>{active.map(t=><Card key={t.id}><div className={styles.templateTop}><span>v{t.version}</span><span>{t.role_target}</span></div><h3>{t.title}</h3><p>{t.description||'No description provided.'}</p><div className={styles.checklist}>{t.items.map((item,i)=><div key={item.id}><span>{i+1}</span><div><strong>{item.title}</strong><small>{item.default_due_days} day target</small></div></div>)}</div></Card>)}</div>}</section></>}
 <Modal isOpen={open} onClose={()=>setOpen(false)} title="Start onboarding"><form onSubmit={start}><div className={ui.formGrid}><label className={ui.inputWrapper}><span className={ui.inputLabel}>Professional</span><select className={ui.selectField} required value={professionalId} onChange={e=>setProfessionalId(e.target.value)}><option value="">Select professional</option>{people.map(p=><option value={p.id} key={p.id}>{p.first_name} {p.last_name} · {p.status}</option>)}</select></label><label className={ui.inputWrapper}><span className={ui.inputLabel}>Template</span><select className={ui.selectField} required value={templateId} onChange={e=>setTemplateId(e.target.value)}><option value="">Select template</option>{active.map(t=><option value={t.id} key={t.id}>{t.title}</option>)}</select></label></div><div className={ui.modalActions}><Button type="button" variant="ghost" onClick={()=>setOpen(false)}>Cancel</Button><Button type="submit" loading={saving}>Start run</Button></div></form></Modal></div>
}

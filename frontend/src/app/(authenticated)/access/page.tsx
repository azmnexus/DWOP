"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, Plus, Search, ShieldCheck } from "lucide-react";
import { api, ApiRequestError } from "@/lib/api";
import { canWrite, isAdmin } from "@/lib/auth";
import { getAllPages } from "@/lib/data";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/contexts/AuthContext";
import type { AccessRequestRead, AccessType, IntegrationRead, ProfessionalRead } from "@/types";
import styles from "../workspace.module.css";
import ui from "@/components/ui/ui.module.css";

const labels: Record<string, string> = { repository: "Repository", channel: "Channel", board: "Board", drive: "Drive" };

export default function AccessPage() {
  const { showToast } = useToast();
  const { user } = useAuth();
  const isMember = user?.role === "MEMBER";
  const [requests, setRequests] = useState<AccessRequestRead[]>([]);
  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationRead[]>([]);
  const [loading, setLoading] = useState(true), [error, setError] = useState<string | null>(null), [query, setQuery] = useState(""), [status, setStatus] = useState("");
  const [open, setOpen] = useState(false), [saving, setSaving] = useState(false), [busyId, setBusyId] = useState<string | null>(null);
  const [form, setForm] = useState({ professional_id: "", integration_id: "", access_type: "repository" as AccessType, role_or_scope: "" });
  const peopleMap = useMemo(() => new Map(people.map((person) => [person.id, `${person.first_name} ${person.last_name}`])), [people]);
  const integrationMap = useMemo(() => new Map(integrations.map((item) => [item.id, item.provider.replace(/_/g, " ")])), [integrations]);
  const ownProfessional = useMemo(() => people.find((person) => person.user_id === user?.id), [people, user?.id]);
  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [requestData, peopleData, integrationData] = await Promise.all([api.get<AccessRequestRead[]>("/access/requests"), getAllPages<ProfessionalRead>("/people/"), api.get<IntegrationRead[]>("/integrations/providers")]);
      setRequests(requestData); setPeople(peopleData); setIntegrations(integrationData);
    } catch (err) { setError(err instanceof ApiRequestError ? err.userMessage : "Unable to load access requests."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (isMember) {
      setForm((current) => ({ ...current, professional_id: ownProfessional?.id || "" }));
    }
  }, [isMember, ownProfessional]);
  const filtered = useMemo(() => requests.filter((item) => (!status || item.status === status) && `${peopleMap.get(item.professional_id) || ""} ${integrationMap.get(item.integration_id) || ""} ${item.role_or_scope}`.toLowerCase().includes(query.toLowerCase())), [requests, status, query, peopleMap, integrationMap]);
  async function createRequest(e: React.FormEvent) { e.preventDefault(); setSaving(true); try { await api.post("/access/requests", form); showToast("success", "Access request submitted."); setOpen(false); setForm({ professional_id: isMember ? ownProfessional?.id || "" : "", integration_id: "", access_type: "repository", role_or_scope: "" }); await load(); } catch (err) { showToast("error", err instanceof ApiRequestError ? err.userMessage : "Unable to submit request."); } finally { setSaving(false); } }
  async function transition(id: string, action: "approve" | "provision" | "revoke") { setBusyId(id); try { await api.post(`/access/requests/${id}/${action}`, action === "approve" ? {} : undefined); showToast("success", `Access ${action === "approve" ? "approved" : action === "provision" ? "provisioned" : "revoked"}.`); await load(); } catch (err) { const message = action === "approve" && user?.role === "MANAGER" ? "Approval is restricted to professionals you directly manage." : err instanceof ApiRequestError ? err.userMessage : `Unable to ${action} access.`; showToast("error", message); } finally { setBusyId(null); } }
  if (error) return <ErrorState type="error" message={error} onRetry={load}/>;
  return <div className={`${styles.page} fade-in`}>
    <div className={styles.header}><div><h2>Access management</h2><p>Request, approve, provision, and revoke access through an auditable lifecycle.</p></div><div className={styles.actions}><Button size="sm" onClick={() => setOpen(true)} disabled={!integrations.length || (isMember && !ownProfessional)}><Plus size={16}/>New request</Button></div></div>
    {!loading && integrations.length === 0 && <div className={styles.notice}>Connect at least one provider in Settings before creating an access request.</div>}
    {!loading && isMember && !ownProfessional && <div className={styles.notice}>Your account is not linked to a workforce profile yet. Contact an administrator before submitting an access request.</div>}
    <div className={styles.summary}><div className={styles.metric}><div className={styles.metricTop}><span>Total requests</span><KeyRound size={18}/></div><strong>{requests.length}</strong><span>Across connected providers</span></div><div className={styles.metric}><div className={styles.metricTop}><span>Awaiting approval</span><ShieldCheck size={18}/></div><strong>{requests.filter((r) => r.status === "requested").length}</strong><span>Requires manager review</span></div><div className={styles.metric}><div className={styles.metricTop}><span>Provisioned</span><ShieldCheck size={18}/></div><strong>{requests.filter((r) => r.status === "provisioned").length}</strong><span>Active external access</span></div><div className={styles.metric}><div className={styles.metricTop}><span>Providers</span><KeyRound size={18}/></div><strong>{integrations.length}</strong><span>Available integrations</span></div></div>
    <div className={styles.filters}><Input aria-label="Search requests" icon={<Search size={18}/>} placeholder="Search person, provider, role or scope" value={query} onChange={(e) => setQuery(e.target.value)}/><select className={ui.selectField} aria-label="Filter status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{["requested", "approved", "provisioning", "provisioned", "failed", "revoked"].map((value) => <option key={value} value={value}>{value}</option>)}</select></div>
    <section className={styles.panel} aria-busy={loading}><div className={styles.panelHeader}><div><h3>Access requests</h3><p>{loading ? "Loading requests…" : `${filtered.length} matching requests`}</p></div></div>{!loading && filtered.length === 0 ? <EmptyState icon={<KeyRound/>} title="No access requests found" description="Submit a request to begin the approval and provisioning workflow."/> : <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Professional</th><th>Provider</th><th>Access</th><th>Status</th><th>Requested</th><th>Actions</th></tr></thead><tbody>{filtered.map((item) => <tr key={item.id}><td>{peopleMap.get(item.professional_id) || item.professional_id.slice(0, 8)}</td><td style={{ textTransform: "capitalize" }}>{integrationMap.get(item.integration_id) || item.integration_id.slice(0, 8)}</td><td>{labels[item.access_type]} · {item.role_or_scope}</td><td><span className={styles.status} data-status={item.status}>{item.status}</span></td><td>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(item.requested_at))}</td><td><div className={styles.rowActions}>{canWrite() && item.status === "requested" && <Button size="sm" variant="secondary" loading={busyId === item.id} onClick={() => transition(item.id, "approve")}>Approve</Button>}{canWrite() && item.status === "approved" && <Button size="sm" loading={busyId === item.id} onClick={() => transition(item.id, "provision")}>Provision</Button>}{isAdmin() && item.status === "provisioned" && <Button size="sm" variant="danger" loading={busyId === item.id} onClick={() => transition(item.id, "revoke")}>Revoke</Button>}</div></td></tr>)}</tbody></table></div>}</section>
    <Modal isOpen={open} onClose={() => setOpen(false)} title="New access request"><form onSubmit={createRequest}><div className={ui.formGrid}>{isMember ? <div className={styles.readOnlyField}><span>Requesting for</span><strong>{ownProfessional ? `${ownProfessional.first_name} ${ownProfessional.last_name}` : "Workforce profile not linked"}</strong></div> : <label className={ui.inputWrapper}><span className={ui.inputLabel}>Professional</span><select required className={ui.selectField} value={form.professional_id} onChange={(e) => setForm({ ...form, professional_id: e.target.value })}><option value="">Select professional</option>{people.map((person) => <option key={person.id} value={person.id}>{person.first_name} {person.last_name}</option>)}</select></label>}<label className={ui.inputWrapper}><span className={ui.inputLabel}>Provider</span><select required className={ui.selectField} value={form.integration_id} onChange={(e) => setForm({ ...form, integration_id: e.target.value })}><option value="">Select provider</option>{integrations.map((item) => <option key={item.id} value={item.id}>{item.provider.replace(/_/g, " ")}</option>)}</select></label><label className={ui.inputWrapper}><span className={ui.inputLabel}>Access type</span><select className={ui.selectField} value={form.access_type} onChange={(e) => setForm({ ...form, access_type: e.target.value as AccessType })}>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><Input label="Role or scope" required placeholder="e.g. Contributor, #delivery, read-only" value={form.role_or_scope} onChange={(e) => setForm({ ...form, role_or_scope: e.target.value })}/></div><div className={ui.modalActions}><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" loading={saving} disabled={isMember && !ownProfessional}>Submit request</Button></div></form></Modal>
  </div>;
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, Building2, Github, PlugZap, Slack } from "lucide-react";
import { api, ApiRequestError } from "@/lib/api";
import { isAdmin } from "@/lib/auth";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import type { IntegrationRead, TenantRead } from "@/types";
import styles from "../workspace.module.css";

const availableProviders = ["github", "slack", "trello", "google_workspace", "m365"];
const providerLabel = (value: string) => ({ github: "GitHub", slack: "Slack", trello: "Trello", google_workspace: "Google Workspace", m365: "Microsoft 365" }[value] || value);

export default function SettingsPage() {
  const { user } = useAuth(), { showToast } = useToast();
  const [tenant, setTenant] = useState<TenantRead | null>(null), [integrations, setIntegrations] = useState<IntegrationRead[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState<string | null>(null), [saving, setSaving] = useState(false), [connecting, setConnecting] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", domain: "" });
  const [preferences, setPreferences] = useState({ operations: true, approvals: true, weekly: false });
  const load = useCallback(async () => { if (!user) return; setLoading(true); setError(null); try { const integrationRequest = api.get<IntegrationRead[]>("/integrations/providers"); if (user.role === "ADMIN") { const [tenantData, integrationData] = await Promise.all([api.get<TenantRead>(`/tenants/${user.tenant_id}`), integrationRequest]); setTenant(tenantData); setForm({ name: tenantData.name, domain: tenantData.domain || "" }); setIntegrations(integrationData); } else { setIntegrations(await integrationRequest); setTenant(null); } } catch (err) { setError(err instanceof ApiRequestError ? err.userMessage : "Unable to load settings."); } finally { setLoading(false); } }, [user]);
  useEffect(() => { load(); const stored = localStorage.getItem("dwop_notification_preferences"); if (stored) { try { setPreferences(JSON.parse(stored)); } catch {} } }, [load]);
  async function saveOrganization(e: React.FormEvent) { e.preventDefault(); if (!tenant) return; setSaving(true); try { const updated = await api.put<TenantRead>(`/tenants/${tenant.id}`, { name: form.name.trim(), domain: form.domain.trim() || null }); setTenant(updated); showToast("success", "Organization settings saved."); } catch (err) { showToast("error", err instanceof ApiRequestError ? err.userMessage : "Unable to save settings."); } finally { setSaving(false); } }
  function togglePreference(key: keyof typeof preferences) { const next = { ...preferences, [key]: !preferences[key] }; setPreferences(next); localStorage.setItem("dwop_notification_preferences", JSON.stringify(next)); showToast("success", "Notification preference saved on this device."); }
  async function connect(provider: string) { setConnecting(provider); try { await api.post<IntegrationRead>(`/integrations/providers/${provider}/connect`, { auth_type: "oauth2", scopes: provider === "github" ? ["repo", "read:org"] : [] }); showToast("success", `${providerLabel(provider)} sandbox connected.`); await load(); } catch (err) { showToast("error", err instanceof ApiRequestError ? err.userMessage : "Unable to connect sandbox provider."); } finally { setConnecting(null); } }
  if (error) return <ErrorState type="error" message={error} onRetry={load}/>;
  return <div className={`${styles.page} fade-in`}>
    <div className={styles.header}><div><h2>Settings</h2><p>Manage your organization profile, integrations, and workspace preferences.</p></div></div>
    <div className={styles.settingsGrid}>
      <div className={styles.page}>
        <section className={styles.panel}><div className={styles.panelHeader}><div><h3>Organization</h3><p>Workspace identity and business domain</p></div><Building2 size={20}/></div>{isAdmin() ? <form className={styles.form} onSubmit={saveOrganization}><Input label="Organization name" required disabled={loading} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}/><Input label="Business domain" placeholder="example.com" disabled={loading} value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}/><div className={styles.notice}>Changes are saved to the tenant profile and apply across the workspace.</div><div className={styles.actions}><Button type="submit" loading={saving}>Save changes</Button></div></form> : <div className={styles.form}><div className={styles.notice}>Organization settings are available to administrators only.</div></div>}</section>
        <section className={styles.panel}><div className={styles.panelHeader}><div><h3>Notifications</h3><p>Personal preferences stored on this device</p></div><Bell size={20}/></div><div className={styles.form}>{([["operations", "Operational updates", "Changes to onboarding, assignments, and access."], ["approvals", "Approval reminders", "Requests that are waiting for your review."], ["weekly", "Weekly workspace digest", "A concise weekly operations summary."]] as const).map(([key, title, description]) => <div className={styles.toggleRow} key={key}><div><strong>{title}</strong><p>{description}</p></div><button className={styles.toggle} role="switch" aria-label={title} aria-checked={preferences[key]} onClick={() => togglePreference(key)} type="button"/></div>)}</div></section>
      </div>
      <section className={styles.panel}><div className={styles.panelHeader}><div><h3>Integrations</h3><p>Sandbox providers used for access provisioning</p></div><PlugZap size={20}/></div><div className={styles.integrations}>{availableProviders.map((provider) => { const current = integrations.find((item) => item.provider === provider); return <div className={styles.integration} key={provider}><span className={styles.integrationIcon}>{provider === "github" ? <Github size={19}/> : provider === "slack" ? <Slack size={19}/> : <PlugZap size={19}/>}</span><div className={styles.integrationBody}><strong>{providerLabel(provider)}</strong><p>{current ? `Sandbox adapter · Health: ${current.health_status || "not reported"}` : "Sandbox not connected"}</p></div>{current ? <span className={styles.status} data-status={current.connection_status}>Sandbox connected</span> : isAdmin() ? <Button size="sm" variant="secondary" loading={connecting === provider} onClick={() => connect(provider)}>Connect sandbox</Button> : <span className={styles.status}>Admin only</span>}</div>; })}</div></section>
    </div>
  </div>;
}

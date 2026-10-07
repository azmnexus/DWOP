"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Download, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api, ApiRequestError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import type { AuditEventRead, AuditExportRead } from "@/types";
import styles from "../workspace.module.css";
import ui from "@/components/ui/ui.module.css";

const humanize = (value: string) => value.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function ActivityPage() {
  const [events, setEvents] = useState<AuditEventRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("");
  const [target, setTarget] = useState("");
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setEvents(await api.get<AuditEventRead[]>("/audit/logs?limit=100")); }
    catch (err) { setError(err instanceof ApiRequestError ? err.userMessage : "Unable to load activity."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const actions = useMemo(() => Array.from(new Set(events.map((item) => item.action))).sort(), [events]);
  const targets = useMemo(() => Array.from(new Set(events.map((item) => item.target_type))).sort(), [events]);
  const filtered = useMemo(() => events.filter((item) => {
    const text = `${item.action} ${item.target_type} ${item.target_id} ${item.actor_user_id || "system"}`.toLowerCase();
    return (!query || text.includes(query.toLowerCase())) && (!action || item.action === action) && (!target || item.target_type === target);
  }), [events, query, action, target]);

  async function exportLog() {
    setExporting(true);
    try {
      const data = await api.get<AuditExportRead>("/audit/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = `dwop-audit-${new Date().toISOString().slice(0, 10)}.json`; link.click(); URL.revokeObjectURL(url);
    } finally { setExporting(false); }
  }

  if (error) return <ErrorState type="error" message={error} onRetry={load} />;
  return <div className={`${styles.page} fade-in`}>
    <div className={styles.header}><div><h2>Activity log</h2><p>A tenant-wide, immutable record of operational and security events.</p></div><div className={styles.actions}><Button variant="secondary" size="sm" onClick={load}><RefreshCw size={16}/>Refresh</Button><Button size="sm" loading={exporting} onClick={exportLog}><Download size={16}/>Export log</Button></div></div>
    <div className={styles.summary}>
      <div className={styles.metric}><div className={styles.metricTop}><span>Events loaded</span><Activity size={18}/></div><strong>{events.length}</strong><span>Most recent 100 events</span></div>
      <div className={styles.metric}><div className={styles.metricTop}><span>Actors</span><ShieldCheck size={18}/></div><strong>{new Set(events.map((e) => e.actor_user_id || "system")).size}</strong><span>Users and system actions</span></div>
      <div className={styles.metric}><div className={styles.metricTop}><span>Action types</span><Activity size={18}/></div><strong>{actions.length}</strong><span>Distinct operations</span></div>
      <div className={styles.metric}><div className={styles.metricTop}><span>Resources</span><ShieldCheck size={18}/></div><strong>{targets.length}</strong><span>Resource categories</span></div>
    </div>
    <div className={styles.filters}><Input aria-label="Search activity" icon={<Search size={18}/>} placeholder="Search action, resource, actor or ID" value={query} onChange={(e) => setQuery(e.target.value)}/><select className={ui.selectField} aria-label="Filter by action" value={action} onChange={(e) => setAction(e.target.value)}><option value="">All actions</option>{actions.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select><select className={ui.selectField} aria-label="Filter by resource" value={target} onChange={(e) => setTarget(e.target.value)}><option value="">All resources</option>{targets.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></div>
    <section className={styles.panel} aria-busy={loading}><div className={styles.panelHeader}><div><h3>Audit timeline</h3><p>{loading ? "Loading events…" : `${filtered.length} matching events`}</p></div></div>{!loading && filtered.length === 0 ? <EmptyState icon={<Activity/>} title="No activity found" description="Try changing the filters, or return after platform activity has been recorded."/> : <ol className={styles.timeline}>{filtered.map((event) => <li className={styles.event} key={event.id}><span className={styles.eventIcon}><Activity size={18}/></span><div><div className={styles.eventTitle}>{humanize(event.action)}</div><div className={styles.eventMeta}><span>{humanize(event.target_type)}</span><span>Target {event.target_id.slice(0, 8)}</span><span>{event.actor_user_id ? `Actor ${event.actor_user_id.slice(0, 8)}` : "System"}</span></div></div><time className={styles.eventTime} dateTime={event.timestamp}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(event.timestamp))}</time></li>)}</ol>}</section>
  </div>;
}

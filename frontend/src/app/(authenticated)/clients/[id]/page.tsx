"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Building2, CalendarDays, FolderKanban } from "lucide-react";
import { api, ApiRequestError } from "@/lib/api";
import { formatDate, getAllPages, normalizeProjects } from "@/lib/data";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ClientRead, ProjectRead } from "@/types";
import styles from "../clients.module.css";

export default function ClientDetail() {
  const id = useParams().id as string;
  const router = useRouter();
  const [client, setClient] = useState<ClientRead | null>(null);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [c, p] = await Promise.all([
        api.get<ClientRead>(`/clients/${id}`),
        getAllPages<ProjectRead>("/assignments/projects", { client_id: id }),
      ]);
      setClient(c);
      setProjects(normalizeProjects(p));
    } catch (e) {
      setError(
        e instanceof ApiRequestError ? e.userMessage : "Unable to load client.",
      );
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    load();
  }, [load]);
  if (loading) return <Skeleton width="100%" height="300px" />;
  if (error || !client)
    return (
      <ErrorState
        type="error"
        message={error || "Client not found."}
        onRetry={load}
      />
    );
  return (
    <div className="fade-in">
      <button className={styles.back} onClick={() => router.push("/clients")}>
        <ArrowLeft size={16} />
        Back to clients
      </button>
      <div className={styles.profile}>
        <span className={styles.heroIcon}>
          <Building2 size={28} />
        </span>
        <div>
          <h2>{client.name}</h2>
          <p>{client.contact_email || "No contact email provided"}</p>
        </div>
        <span className={styles.status}>{client.status}</span>
      </div>
      <div className={styles.metrics}>
        <Card>
          <strong>
            {projects.filter((p) => p.status === "active").length}
          </strong>
          <span>Active projects</span>
        </Card>
        <Card>
          <strong>{projects.length}</strong>
          <span>Total engagements</span>
        </Card>
        <Card>
          <strong>—</strong>
          <span>Assignment data pending</span>
        </Card>
      </div>
      <section className={styles.section}>
        <h3>
          <FolderKanban size={18} />
          Associated projects
        </h3>
        {projects.length === 0 ? (
          <EmptyState
            icon={<FolderKanban />}
            title="No associated projects"
            description="No project records currently reference this client."
          />
        ) : (
          <div className={styles.projectList}>
            {projects.map((p) => (
              <Card key={p.id}>
                <div className={styles.projectTop}>
                  <div>
                    <strong>{p.name}</strong>
                    <p>{p.code}</p>
                  </div>
                  <Badge kind="project-status" value={p.status} />
                </div>
                <div className={styles.timelineLabel}>
                  <CalendarDays size={15} />
                  {formatDate(p.start_date)} – {formatDate(p.target_end_date)}
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

import { api } from "@/lib/api";
import type { CapacityOverviewRead, ProjectRead, ProjectStatus } from "@/types";

const PAGE_SIZE = 100;
const PROJECT_STATUSES: ProjectStatus[] = ["active", "completed", "on_hold"];

export async function getAllPages<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
): Promise<T[]> {
  const records: T[] = [];

  for (let skip = 0; ; skip += PAGE_SIZE) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    query.set("skip", String(skip));
    query.set("limit", String(PAGE_SIZE));

    const page = await api.get<T[]>(`${path}?${query.toString()}`);
    records.push(...page);
    if (page.length < PAGE_SIZE) return records;
  }
}

export function normalizeProject(project: ProjectRead): ProjectRead {
  const normalizedStatus = String(
    project.status,
  ).toLowerCase() as ProjectStatus;
  return {
    ...project,
    status: PROJECT_STATUSES.includes(normalizedStatus)
      ? normalizedStatus
      : "on_hold",
  };
}

export function normalizeProjects(projects: ProjectRead[]): ProjectRead[] {
  return projects.map(normalizeProject);
}

export function getCapacityUtilization(capacity: CapacityOverviewRead): number {
  const value =
    capacity.average_utilization_pct ??
    capacity.total_capacity_allocated_pct ??
    0;
  return Number.isFinite(value) ? value : 0;
}

export function formatDate(
  value: string | null,
  fallback = "Not scheduled",
): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

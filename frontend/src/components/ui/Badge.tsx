import React from "react";
import styles from "./ui.module.css";
import type { ProfessionalStatus, ProjectStatus, UserRole } from "@/types";

type BadgeProps = {
  label?: string;
  className?: string;
} & (
  | { kind: "professional-status"; value: ProfessionalStatus }
  | { kind: "project-status"; value: ProjectStatus }
  | { kind: "role"; value: UserRole }
);

const statusClassMap: Record<ProfessionalStatus, string> = {
  intake: styles.badgeIntake,
  onboarding: styles.badgeOnboarding,
  ready: styles.badgeReady,
  assigned: styles.badgeAssigned,
  offboarding: styles.badgeOffboarding,
  inactive: styles.badgeInactive,
};

const roleClassMap: Record<UserRole, string> = {
  ADMIN: styles.badgeAdmin,
  MANAGER: styles.badgeManager,
  MEMBER: styles.badgeMember,
};

const projectStatusClassMap: Record<ProjectStatus, string> = {
  active: styles.badgeReady,
  completed: styles.badgeAssigned,
  on_hold: styles.badgeOnboarding,
};

const statusLabelMap: Record<ProfessionalStatus, string> = {
  intake: "Intake",
  onboarding: "Onboarding",
  ready: "Ready",
  assigned: "Assigned",
  offboarding: "Offboarding",
  inactive: "Inactive",
};

const projectStatusLabelMap: Record<ProjectStatus, string> = {
  active: "Active",
  completed: "Completed",
  on_hold: "On Hold",
};

export function Badge({ kind, value, label, className = "" }: BadgeProps) {
  const badgeClass =
    kind === "professional-status"
      ? statusClassMap[value]
      : kind === "project-status"
        ? projectStatusClassMap[value]
        : roleClassMap[value];
  const displayLabel =
    label ||
    (kind === "professional-status"
      ? statusLabelMap[value]
      : kind === "project-status"
        ? projectStatusLabelMap[value]
        : value);

  return (
    <span className={`${styles.badge} ${badgeClass} ${className}`}>
      {kind !== "role" && <span className={styles.badgeDot} />}
      {displayLabel}
    </span>
  );
}

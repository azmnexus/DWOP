import React from 'react';
import styles from './ui.module.css';
import type { ProfessionalStatus, UserRole, ProjectStatus } from '@/types';

interface BadgeProps {
  status?: ProfessionalStatus;
  projectStatus?: ProjectStatus;
  role?: UserRole;
  label?: string;
  className?: string;
}

const statusClassMap: Record<string, string> = {
  intake: styles.badgeIntake,
  onboarding: styles.badgeOnboarding,
  ready: styles.badgeReady,
  assigned: styles.badgeAssigned,
  offboarding: styles.badgeOffboarding,
  inactive: styles.badgeInactive,
};

const roleClassMap: Record<string, string> = {
  ADMIN: styles.badgeAdmin,
  MANAGER: styles.badgeManager,
  MEMBER: styles.badgeMember,
};

const projectStatusClassMap: Record<string, string> = {
  active: styles.badgeReady,
  completed: styles.badgeAssigned,
  on_hold: styles.badgeOnboarding,
};

const statusLabelMap: Record<string, string> = {
  intake: 'Intake',
  onboarding: 'Onboarding',
  ready: 'Ready',
  assigned: 'Assigned',
  offboarding: 'Offboarding',
  inactive: 'Inactive',
  available: 'Available',
  partially_booked: 'Partially Booked',
  fully_booked: 'Fully Booked',
};

const projectStatusLabelMap: Record<string, string> = {
  active: 'Active',
  completed: 'Completed',
  on_hold: 'On Hold',
};

export function Badge({ status, projectStatus, role, label, className = '' }: BadgeProps) {
  let badgeClass = '';
  let displayLabel = label || '';

  if (status) {
    badgeClass = statusClassMap[status] || styles.badgeInactive;
    displayLabel = label || statusLabelMap[status] || status;
  } else if (projectStatus) {
    badgeClass = projectStatusClassMap[projectStatus] || styles.badgeInactive;
    displayLabel = label || projectStatusLabelMap[projectStatus] || projectStatus;
  } else if (role) {
    badgeClass = roleClassMap[role] || styles.badgeMember;
    displayLabel = label || role;
  }

  return (
    <span className={`${styles.badge} ${badgeClass} ${className}`}>
      {(status || projectStatus) && <span className={styles.badgeDot} />}
      {displayLabel}
    </span>
  );
}

import React from 'react';
import styles from './ui.module.css';
import type { ProfessionalStatus, UserRole } from '@/types';

interface BadgeProps {
  status?: ProfessionalStatus;
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

export function Badge({ status, role, label, className = '' }: BadgeProps) {
  let badgeClass = '';
  let displayLabel = label || '';

  if (status) {
    badgeClass = statusClassMap[status] || styles.badgeInactive;
    displayLabel = label || statusLabelMap[status] || status;
  } else if (role) {
    badgeClass = roleClassMap[role] || styles.badgeMember;
    displayLabel = label || role;
  }

  return (
    <span className={`${styles.badge} ${badgeClass} ${className}`}>
      {status && <span className={styles.badgeDot} />}
      {displayLabel}
    </span>
  );
}

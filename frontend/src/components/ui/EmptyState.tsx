import React from 'react';
import { Users } from 'lucide-react';
import { Button } from './Button';
import styles from './ui.module.css';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className={styles.emptyState} role="status">
      <div className={styles.emptyStateIcon}>
        {icon || <Users size={28} />}
      </div>
      <h3 className={styles.emptyStateTitle}>{title}</h3>
      {description && (
        <p className={styles.emptyStateDescription}>{description}</p>
      )}
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

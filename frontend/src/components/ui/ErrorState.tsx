import React from 'react';
import { AlertTriangle, WifiOff, ShieldX } from 'lucide-react';
import { Button } from './Button';
import styles from './ui.module.css';

interface ErrorStateProps {
  type?: 'error' | 'network' | 'forbidden' | 'unauthorized';
  title?: string;
  message?: string;
  onRetry?: () => void;
}

const errorConfig = {
  error: {
    icon: <AlertTriangle size={28} />,
    title: 'Something went wrong',
    message: 'An unexpected error occurred. Please try again.',
  },
  network: {
    icon: <WifiOff size={28} />,
    title: 'Connection failed',
    message: 'Unable to reach the server. Please check your connection and try again.',
  },
  forbidden: {
    icon: <ShieldX size={28} />,
    title: 'Access denied',
    message: 'You do not have permission to view this resource.',
  },
  unauthorized: {
    icon: <ShieldX size={28} />,
    title: 'Session expired',
    message: 'Your session has expired. Please sign in again.',
  },
};

export function ErrorState({
  type = 'error',
  title,
  message,
  onRetry,
}: ErrorStateProps) {
  const config = errorConfig[type];

  return (
    <div className={styles.errorState} role="alert">
      <div className={styles.errorStateIcon}>
        {config.icon}
      </div>
      <h3 className={styles.errorStateTitle}>{title || config.title}</h3>
      <p className={styles.errorStateDescription}>{message || config.message}</p>
      {onRetry && type !== 'forbidden' && type !== 'unauthorized' && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

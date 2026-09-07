import React from 'react';
import styles from './ui.module.css';

interface SkeletonProps {
  width?: string;
  height?: string;
  circle?: boolean;
  className?: string;
}

export function Skeleton({ width = '100%', height = '14px', circle = false, className = '' }: SkeletonProps) {
  return (
    <div
      className={`${circle ? styles.skeletonCircle : styles.skeletonLine} ${className}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard() {
  return (
    <div className={`${styles.card} ${styles.skeletonCard}`} aria-hidden="true">
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <Skeleton circle width="40px" height="40px" />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <Skeleton width="60%" height="16px" />
          <Skeleton width="40%" height="12px" />
        </div>
      </div>
      <Skeleton width="100%" height="12px" />
      <Skeleton width="80%" height="12px" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div aria-hidden="true" aria-label="Loading data">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ display: 'flex', gap: '16px', padding: '16px', borderBottom: '1px solid var(--color-border)' }}>
          <Skeleton circle width="36px" height="36px" />
          <Skeleton width="25%" height="14px" />
          <Skeleton width="20%" height="14px" />
          <Skeleton width="15%" height="14px" />
          <Skeleton width="15%" height="14px" />
        </div>
      ))}
    </div>
  );
}

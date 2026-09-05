import React from 'react';
import styles from './ui.module.css';

interface CardProps {
  children: React.ReactNode;
  padded?: boolean;
  hoverable?: boolean;
  className?: string;
  onClick?: () => void;
}

export function Card({
  children,
  padded = true,
  hoverable = false,
  className = '',
  onClick,
}: CardProps) {
  return (
    <div
      className={`${styles.card} ${padded ? styles.cardPadded : ''} ${hoverable ? styles.cardHover : ''} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`${styles.cardHeader} ${className}`}>{children}</div>;
}

export function CardTitle({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <h3 className={`${styles.cardTitle} ${className}`}>{children}</h3>;
}

export function CardBody({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`${styles.cardBody} ${className}`}>{children}</div>;
}

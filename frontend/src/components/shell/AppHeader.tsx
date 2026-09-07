'use client';

import React from 'react';
import { Menu } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/Badge';
import styles from './shell.module.css';

interface AppHeaderProps {
  title: string;
  onMenuToggle: () => void;
}

export function AppHeader({ title, onMenuToggle }: AppHeaderProps) {
  const { user } = useAuth();

  const getInitials = (email: string) => email.substring(0, 2).toUpperCase();

  return (
    <header className={styles.header}>
      <div className={styles.headerLeft}>
        <button
          className={styles.menuButton}
          onClick={onMenuToggle}
          aria-label="Open navigation menu"
        >
          <Menu size={22} />
        </button>
        <h1 className={styles.pageTitle}>{title}</h1>
      </div>

      <div className={styles.headerRight}>
        {user && (
          <div className={styles.headerUserBtn}>
            <div className={styles.headerUserAvatar} aria-hidden="true">
              {getInitials(user.email)}
            </div>
            <span className={styles.headerUserName}>{user.email.split('@')[0]}</span>
            <Badge role={user.role} />
          </div>
        )}
      </div>
    </header>
  );
}

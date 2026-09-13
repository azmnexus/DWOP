'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  X,
  LayoutDashboard,
  Users,
  ClipboardList,
  FolderKanban,
  Building2,
  ListChecks,
  Shield,
  Activity,
  Settings,
  LogOut,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import styles from './shell.module.css';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  enabled: boolean;
}

const navItems: NavItem[] = [
  { label: 'Overview', href: '/', icon: <LayoutDashboard size={18} />, enabled: true },
  { label: 'Workforce', href: '/workforce', icon: <Users size={18} />, enabled: true },
  { label: 'Onboarding', href: '/onboarding', icon: <ClipboardList size={18} />, enabled: true },
  { label: 'Assignments', href: '/assignments', icon: <FolderKanban size={18} />, enabled: true },
  { label: 'Clients', href: '/clients', icon: <Building2 size={18} />, enabled: true },
  { label: 'Work Management', href: '/work', icon: <ListChecks size={18} />, enabled: true },
  { label: 'Access', href: '/access', icon: <Shield size={18} />, enabled: false },
  { label: 'Activity', href: '/activity', icon: <Activity size={18} />, enabled: false },
  { label: 'Settings', href: '/settings', icon: <Settings size={18} />, enabled: false },
];

export function MobileDrawer({ isOpen, onClose }: MobileDrawerProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  // Close drawer on route change
  useEffect(() => {
    onClose();
  // The parent callback identity may change after opening; only route changes
  // should trigger this effect.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Lock body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className={styles.drawerOverlay}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation menu"
      >
        <div className={styles.drawerHeader}>
          <div className={styles.brand}>
            <img src="/logo.png" alt="" className={styles.brandLogo} aria-hidden="true" />
            <div className={styles.brandText}>
              <span className={styles.brandName}>AZM Nexus</span>
              <span className={styles.brandSub}>Digital Workspace Ops</span>
            </div>
          </div>
          <button
            className={styles.drawerClose}
            onClick={onClose}
            aria-label="Close navigation menu"
          >
            <X size={20} />
          </button>
        </div>

        <nav className={styles.drawerNav}>
          <div className={styles.navSection}>
            <div className={styles.navSectionLabel}>Platform</div>
            {navItems.map((item) => {
              const isActive = item.href === '/'
                ? pathname === '/'
                : pathname.startsWith(item.href);

              if (!item.enabled) {
                return (
                  <div
                    key={item.href}
                    className={`${styles.navItem} ${styles.navItemDisabled}`}
                    title="Coming soon"
                  >
                    <span className={styles.navItemIcon}>{item.icon}</span>
                    {item.label}
                  </div>
                );
              }

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                  onClick={onClose}
                >
                  <span className={styles.navItemIcon}>{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* User section */}
        {user && (
          <div className={styles.userSection}>
            <div className={styles.userInfo}>
              <div className={styles.userAvatar} aria-hidden="true">
                {user.email.substring(0, 2).toUpperCase()}
              </div>
              <div className={styles.userDetails}>
                <div className={styles.userName}>{user.email}</div>
                <div className={styles.userRole}>{user.role}</div>
              </div>
            </div>
            <button className={styles.logoutBtn} onClick={logout} aria-label="Sign out">
              <LogOut size={16} />
              Sign Out
            </button>
          </div>
        )}
      </div>
    </>
  );
}

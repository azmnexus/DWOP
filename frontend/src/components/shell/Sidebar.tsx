'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  ClipboardList,
  FolderKanban,
  Shield,
  Activity,
  Settings,
  LogOut,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { Badge } from '@/components/ui/Badge';
import styles from './shell.module.css';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  enabled: boolean;
}

const navItems: NavItem[] = [
  { label: 'Overview', href: '/', icon: <LayoutDashboard size={18} />, enabled: true },
  { label: 'Workforce', href: '/workforce', icon: <Users size={18} />, enabled: true },
  { label: 'Onboarding', href: '/onboarding', icon: <ClipboardList size={18} />, enabled: false },
  { label: 'Assignments', href: '/assignments', icon: <FolderKanban size={18} />, enabled: false },
  { label: 'Access', href: '/access', icon: <Shield size={18} />, enabled: false },
  { label: 'Activity', href: '/activity', icon: <Activity size={18} />, enabled: false },
  { label: 'Settings', href: '/settings', icon: <Settings size={18} />, enabled: false },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const getInitials = (email: string) => {
    return email.substring(0, 2).toUpperCase();
  };

  return (
    <aside className={styles.sidebar} aria-label="Main navigation">
      {/* Brand */}
      <div className={styles.brand}>
        <img src="/logo.png" alt="" className={styles.brandLogo} aria-hidden="true" />
        <div className={styles.brandText}>
          <span className={styles.brandName}>AZM Nexus</span>
          <span className={styles.brandSub}>Digital Workspace Ops</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
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
              >
                <span className={styles.navItemIcon}>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* User Section */}
      {user && (
        <div className={styles.userSection}>
          <div className={styles.userInfo}>
            <div className={styles.userAvatar} aria-hidden="true">
              {getInitials(user.email)}
            </div>
            <div className={styles.userDetails}>
              <div className={styles.userName}>{user.email}</div>
              <div className={styles.userRole}>
                <Badge role={user.role} />
              </div>
            </div>
          </div>
          <button
            className={styles.logoutBtn}
            onClick={logout}
            aria-label="Sign out"
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}

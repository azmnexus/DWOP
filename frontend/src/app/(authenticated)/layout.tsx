'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { ToastProvider } from '@/components/ui/Toast';
import { Sidebar } from '@/components/shell/Sidebar';
import { AppHeader } from '@/components/shell/AppHeader';
import { MobileDrawer } from '@/components/shell/MobileDrawer';
import styles from '@/components/shell/shell.module.css';

const pageTitles: Record<string, string> = {
  '/': 'Overview',
  '/workforce': 'Workforce Directory',
  '/onboarding': 'Onboarding',
  '/assignments': 'Assignments',
  '/clients': 'Client View',
  '/work': 'Work Management',
  '/access': 'Access Management',
  '/activity': 'Activity Log',
  '/settings': 'Settings',
};

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isLoggedIn, isLoading } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isLoading && !isLoggedIn) {
      router.replace('/login');
    }
  }, [isLoggedIn, isLoading, router]);

  // Show nothing while checking auth state
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
      }}>
        <div className="spinner" aria-label="Loading" />
      </div>
    );
  }

  // Don't render app shell if not logged in
  if (!isLoggedIn) {
    return null;
  }

  // Determine page title from pathname
  const baseRoute = '/' + (pathname.split('/')[1] || '');
  const pageTitle = pathname.includes('/workforce/')
    ? 'Professional Profile'
    : pathname.includes('/clients/')
      ? 'Client Detail'
      : pathname.includes('/assignments/')
        ? 'Project Workspace'
    : pageTitles[baseRoute] || 'DWOP Platform';

  return (
    <ToastProvider>
      <div className={styles.appLayout}>
        <Sidebar />
        <MobileDrawer isOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />
        <main className={styles.mainContent}>
          <AppHeader
            title={pageTitle}
            onMenuToggle={() => setDrawerOpen(true)}
          />
          <div className={styles.contentArea}>
            {children}
          </div>
        </main>
      </div>
    </ToastProvider>
  );
}

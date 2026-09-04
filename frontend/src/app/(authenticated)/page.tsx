'use client';

import React, { useEffect, useState } from 'react';
import { Users, ClipboardList, TrendingUp, UserCheck } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import type { ProfessionalRead } from '@/types';

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtitle?: string;
}

function StatCard({ icon, label, value, subtitle }: StatCardProps) {
  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
        <div style={{
          width: 48,
          height: 48,
          borderRadius: 'var(--radius-md)',
          background: 'var(--color-surface-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-brand-primary)',
          flexShrink: 0,
        }}>
          {icon}
        </div>
        <div>
          <div style={{
            fontSize: 'var(--font-size-2xl)',
            fontWeight: 'var(--font-weight-bold)',
            color: 'var(--color-text-primary)',
            lineHeight: 1.2,
          }}>
            {value}
          </div>
          <div style={{
            fontSize: 'var(--font-size-sm)',
            color: 'var(--color-text-secondary)',
          }}>
            {label}
          </div>
          {subtitle && (
            <div style={{
              fontSize: 'var(--font-size-xs)',
              color: 'var(--color-text-muted)',
              marginTop: 2,
            }}>
              {subtitle}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const { user } = useAuth();
  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await api.get<ProfessionalRead[]>('/people/');
        setPeople(data);
      } catch {
        // Silently fail — dashboard is informational
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  const readyCount = people.filter(p => p.status === 'ready').length;
  const onboardingCount = people.filter(p => p.status === 'onboarding').length;
  const intakeCount = people.filter(p => p.status === 'intake').length;

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="fade-in">
      {/* Greeting */}
      <div style={{ marginBottom: 'var(--spacing-xl)' }}>
        <h2 style={{ fontSize: 'var(--font-size-2xl)', marginBottom: 'var(--spacing-xs)' }}>
          {greeting()}{user ? `, ${user.email.split('@')[0]}` : ''}
        </h2>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--font-size-sm)' }}>
          Here&apos;s an overview of your workforce operations.
          {user && <> You are signed in as <Badge role={user.role} /></>}
        </p>
      </div>

      {/* Stats Grid */}
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 'var(--spacing-md)' }}>
          {[1, 2, 3, 4].map(i => (
            <Card key={i}>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <Skeleton circle width="48px" height="48px" />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <Skeleton width="60px" height="24px" />
                  <Skeleton width="100px" height="14px" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 'var(--spacing-md)' }}>
          <StatCard
            icon={<Users size={22} />}
            label="Total Professionals"
            value={people.length}
            subtitle="Across all statuses"
          />
          <StatCard
            icon={<UserCheck size={22} />}
            label="Ready"
            value={readyCount}
            subtitle="Available for assignment"
          />
          <StatCard
            icon={<ClipboardList size={22} />}
            label="Onboarding"
            value={onboardingCount}
            subtitle="Currently onboarding"
          />
          <StatCard
            icon={<TrendingUp size={22} />}
            label="New Intake"
            value={intakeCount}
            subtitle="Pending processing"
          />
        </div>
      )}

      {/* Recent Professionals */}
      {!loading && people.length > 0 && (
        <div style={{ marginTop: 'var(--spacing-xl)' }}>
          <h3 style={{ fontSize: 'var(--font-size-lg)', marginBottom: 'var(--spacing-md)' }}>
            Recent Professionals
          </h3>
          <Card padded={false}>
            {people.slice(0, 5).map((person, idx) => (
              <div
                key={person.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: 'var(--spacing-md) var(--spacing-lg)',
                  borderBottom: idx < Math.min(people.length, 5) - 1 ? '1px solid var(--color-border)' : 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
                  <div style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--color-brand-primary), var(--color-brand-accent))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}>
                    {person.first_name[0]}{person.last_name[0]}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 'var(--font-size-sm)' }}>
                      {person.first_name} {person.last_name}
                    </div>
                    <div style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
                      {person.email}
                    </div>
                  </div>
                </div>
                <Badge status={person.status} />
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}

'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Mail,
  Phone,
  Calendar,
  CheckCircle,
  Clock,
  AlertTriangle,
} from 'lucide-react';
import { api, ApiRequestError } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { ProfessionalRead, OnboardingRunRead } from '@/types';
import styles from '../workforce.module.css';
import uiStyles from '@/components/ui/ui.module.css';

export default function ProfessionalProfilePage() {
  const params = useParams();
  const personId = params.id as string;

  const [person, setPerson] = useState<ProfessionalRead | null>(null);
  const [onboardingRuns, setOnboardingRuns] = useState<OnboardingRunRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ type: 'error' | 'network' | 'forbidden'; message?: string } | null>(null);

  useEffect(() => {
    const fetchProfile = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<ProfessionalRead>(`/people/${personId}`);
        setPerson(data);
      } catch (err) {
        if (err instanceof ApiRequestError) {
          if (err.status === 403) {
            setError({ type: 'forbidden', message: err.userMessage });
          } else if (err.status === 404) {
            setError({ type: 'error', message: 'Professional not found in the current tenant.' });
          } else if (err.status === 0) {
            setError({ type: 'network', message: err.userMessage });
          } else {
            setError({ type: 'error', message: err.userMessage });
          }
        } else {
          setError({ type: 'error' });
        }
      } finally {
        setLoading(false);
      }
    };

    if (personId) {
      fetchProfile();
    }
  }, [personId]);

  if (error) {
    return (
      <div className="fade-in">
        <Link href="/workforce" className={styles.profileBack}>
          <ArrowLeft size={16} />
          Back to Directory
        </Link>
        <ErrorState
          type={error.type}
          message={error.message}
          onRetry={error.type !== 'forbidden' ? () => window.location.reload() : undefined}
        />
      </div>
    );
  }

  if (loading || !person) {
    return (
      <div>
        <Link href="/workforce" className={styles.profileBack}>
          <ArrowLeft size={16} />
          Back to Directory
        </Link>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '24px' }}>
          <Skeleton circle width="80px" height="80px" />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="200px" height="24px" />
            <Skeleton width="300px" height="16px" />
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <Skeleton width="100%" height="200px" />
          <Skeleton width="100%" height="200px" />
        </div>
      </div>
    );
  }

  const engagement = person.engagements.length > 0 ? person.engagements[0] : null;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="fade-in">
      {/* Back link */}
      <Link href="/workforce" className={styles.profileBack}>
        <ArrowLeft size={16} />
        Back to Directory
      </Link>

      {/* Profile Header */}
      <div className={styles.profileHeader}>
        <div className={styles.profileAvatar}>
          {person.first_name[0]}{person.last_name[0]}
        </div>
        <div className={styles.profileInfo}>
          <h2 className={styles.profileName}>
            {person.first_name} {person.last_name}
          </h2>
          <div className={styles.profileMeta}>
            <Badge status={person.status} />
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Mail size={14} />
              {person.email}
            </span>
            {person.phone && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Phone size={14} />
                {person.phone}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Profile Sections */}
      <div className={styles.profileGrid}>
        {/* Identity & Contact */}
        <Card>
          <h4 className={styles.sectionTitle}>Identity & Contact</h4>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>First Name</span>
            <span className={styles.fieldValue}>{person.first_name}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Last Name</span>
            <span className={styles.fieldValue}>{person.last_name}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Email</span>
            <span className={styles.fieldValue}>{person.email}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Phone</span>
            <span className={styles.fieldValue}>{person.phone || '—'}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Joined</span>
            <span className={styles.fieldValue}>{formatDate(person.created_at)}</span>
          </div>
        </Card>

        {/* Lifecycle Status */}
        <Card>
          <h4 className={styles.sectionTitle}>Lifecycle & Availability</h4>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Status</span>
            <span className={styles.fieldValue}>
              <Badge status={person.status} />
            </span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Availability</span>
            <span className={styles.fieldValue}>
              <Badge
                label={
                  person.availability_status === 'partially_booked'
                    ? 'Partially Booked'
                    : person.availability_status === 'fully_booked'
                    ? 'Fully Booked'
                    : 'Available'
                }
                status={
                  person.availability_status === 'available'
                    ? 'ready'
                    : person.availability_status === 'fully_booked'
                    ? 'inactive'
                    : 'onboarding'
                }
              />
            </span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>User Account</span>
            <span className={styles.fieldValue}>
              {person.user_id ? 'Linked' : 'Not linked'}
            </span>
          </div>
        </Card>

        {/* Skills */}
        <Card>
          <h4 className={styles.sectionTitle}>Skills & Expertise</h4>
          {person.skills.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {person.skills.map((skill) => (
                <span key={skill} className={styles.skillTag} style={{ fontSize: '13px', padding: '4px 12px' }}>
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
              No skills recorded.
            </p>
          )}
        </Card>

        {/* Engagement */}
        <Card>
          <h4 className={styles.sectionTitle}>Engagement Details</h4>
          {engagement ? (
            <>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Type</span>
                <span className={styles.fieldValue} style={{ textTransform: 'capitalize' }}>
                  {engagement.engagement_type.replace('_', ' ')}
                </span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Contract Status</span>
                <span className={styles.fieldValue} style={{ textTransform: 'capitalize' }}>
                  {engagement.contract_status}
                </span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>Start Date</span>
                <span className={styles.fieldValue}>{formatDate(engagement.start_date)}</span>
              </div>
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>End Date</span>
                <span className={styles.fieldValue}>{formatDate(engagement.end_date)}</span>
              </div>
              {engagement.compensation_rate && (
                <div className={styles.fieldRow}>
                  <span className={styles.fieldLabel}>Compensation</span>
                  <span className={styles.fieldValue}>{engagement.compensation_rate}</span>
                </div>
              )}
            </>
          ) : (
            <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)' }}>
              No engagement details recorded.
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}

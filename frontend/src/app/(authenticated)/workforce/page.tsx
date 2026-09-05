'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Search, UserPlus } from 'lucide-react';
import { api, ApiRequestError } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { canWrite } from '@/lib/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton, SkeletonTable } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import type { ProfessionalRead, ProfessionalStatus, AvailabilityStatus } from '@/types';
import styles from './workforce.module.css';
import uiStyles from '@/components/ui/ui.module.css';

export default function WorkforcePage() {
  const router = useRouter();
  const { user } = useAuth();

  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ type: 'error' | 'network' | 'forbidden'; message?: string } | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProfessionalStatus | ''>('');
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityStatus | ''>('');

  const fetchPeople = async () => {
    setLoading(true);
    setError(null);
    try {
      let endpoint = '/people/?limit=100';
      if (statusFilter) endpoint += `&status_filter=${statusFilter}`;
      if (availabilityFilter) endpoint += `&availability_filter=${availabilityFilter}`;
      const data = await api.get<ProfessionalRead[]>(endpoint);
      setPeople(data);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 403) {
          setError({ type: 'forbidden', message: err.userMessage });
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

  useEffect(() => {
    fetchPeople();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, availabilityFilter]);

  // Client-side text search (backend doesn't support text search)
  const filteredPeople = useMemo(() => {
    if (!searchQuery.trim()) return people;
    const query = searchQuery.toLowerCase();
    return people.filter(
      (p) =>
        p.first_name.toLowerCase().includes(query) ||
        p.last_name.toLowerCase().includes(query) ||
        p.email.toLowerCase().includes(query) ||
        p.skills.some((s) => s.toLowerCase().includes(query))
    );
  }, [people, searchQuery]);

  const navigateToProfile = (id: string) => {
    router.push(`/workforce/${id}`);
  };

  const getInitials = (firstName: string, lastName: string) =>
    `${firstName[0] || ''}${lastName[0] || ''}`.toUpperCase();

  // Error state
  if (error) {
    return (
      <div className="fade-in">
        <ErrorState
          type={error.type}
          message={error.message}
          onRetry={error.type !== 'forbidden' ? fetchPeople : undefined}
        />
      </div>
    );
  }

  return (
    <div className="fade-in">
      {/* Header */}
      <div className={styles.directoryHeader}>
        <h2 className={styles.directoryTitle}>
          Workforce
          {!loading && (
            <span className={styles.directoryCount}>
              {filteredPeople.length} professional{filteredPeople.length !== 1 ? 's' : ''}
            </span>
          )}
        </h2>
        {canWrite() && (
          <Button variant="primary" size="sm">
            <UserPlus size={16} />
            Add Professional
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className={styles.filtersBar}>
        <div className={styles.searchInput}>
          <Input
            placeholder="Search by name, email, or skill..."
            icon={<Search size={18} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search professionals"
          />
        </div>
        <div className={styles.filterSelect}>
          <select
            className={uiStyles.selectField}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ProfessionalStatus | '')}
            aria-label="Filter by status"
          >
            <option value="">All Statuses</option>
            <option value="intake">Intake</option>
            <option value="onboarding">Onboarding</option>
            <option value="ready">Ready</option>
            <option value="assigned">Assigned</option>
            <option value="offboarding">Offboarding</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        <div className={styles.filterSelect}>
          <select
            className={uiStyles.selectField}
            value={availabilityFilter}
            onChange={(e) => setAvailabilityFilter(e.target.value as AvailabilityStatus | '')}
            aria-label="Filter by availability"
          >
            <option value="">All Availability</option>
            <option value="available">Available</option>
            <option value="partially_booked">Partially Booked</option>
            <option value="fully_booked">Fully Booked</option>
          </select>
        </div>
      </div>

      {/* Loading */}
      {loading && <SkeletonTable rows={5} />}

      {/* Empty */}
      {!loading && filteredPeople.length === 0 && (
        <EmptyState
          title="No professionals found"
          description={
            searchQuery || statusFilter || availabilityFilter
              ? 'Try adjusting your search or filter criteria.'
              : 'No professionals have been registered yet.'
          }
        />
      )}

      {/* Desktop Table */}
      {!loading && filteredPeople.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Professional</th>
                <th>Status</th>
                <th>Availability</th>
                <th>Skills</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {filteredPeople.map((person) => (
                <tr
                  key={person.id}
                  onClick={() => navigateToProfile(person.id)}
                  tabIndex={0}
                  role="link"
                  aria-label={`View profile of ${person.first_name} ${person.last_name}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') navigateToProfile(person.id);
                  }}
                >
                  <td>
                    <div className={styles.personCell}>
                      <div className={uiStyles.avatar + ' ' + uiStyles.avatarMd}>
                        {getInitials(person.first_name, person.last_name)}
                      </div>
                      <div>
                        <div className={styles.personName}>
                          {person.first_name} {person.last_name}
                        </div>
                        <div className={styles.personEmail}>{person.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <Badge status={person.status} />
                  </td>
                  <td>
                    <Badge
                      label={person.availability_status === 'partially_booked' ? 'Partial' : person.availability_status === 'fully_booked' ? 'Full' : 'Available'}
                      status={person.availability_status === 'available' ? 'ready' : person.availability_status === 'fully_booked' ? 'inactive' : 'onboarding'}
                    />
                  </td>
                  <td>
                    {person.skills.slice(0, 3).map((skill) => (
                      <span key={skill} className={styles.skillTag}>
                        {skill}
                      </span>
                    ))}
                    {person.skills.length > 3 && (
                      <span className={styles.moreSkills}>
                        +{person.skills.length - 3}
                      </span>
                    )}
                  </td>
                  <td>
                    {person.engagements.length > 0
                      ? person.engagements[0].engagement_type.replace('_', ' ')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Mobile Card Grid */}
      {!loading && filteredPeople.length > 0 && (
        <div className={styles.cardGrid}>
          {filteredPeople.map((person) => (
            <div
              key={person.id}
              className={styles.personCard}
              onClick={() => navigateToProfile(person.id)}
              tabIndex={0}
              role="link"
              aria-label={`View profile of ${person.first_name} ${person.last_name}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter') navigateToProfile(person.id);
              }}
            >
              <div className={uiStyles.avatar + ' ' + uiStyles.avatarMd}>
                {getInitials(person.first_name, person.last_name)}
              </div>
              <div className={styles.personCardInfo}>
                <div className={styles.personCardName}>
                  {person.first_name} {person.last_name}
                </div>
                <div className={styles.personCardEmail}>{person.email}</div>
                <div className={styles.personCardMeta}>
                  <Badge status={person.status} />
                  {person.skills.slice(0, 2).map((skill) => (
                    <span key={skill} className={styles.skillTag}>
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

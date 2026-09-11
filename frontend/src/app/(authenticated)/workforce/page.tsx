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
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import type { ProfessionalCreate, ProfessionalRead, ProfessionalStatus, AvailabilityStatus } from '@/types';
import styles from './workforce.module.css';
import uiStyles from '@/components/ui/ui.module.css';

export default function WorkforcePage() {
  const router = useRouter();
  const { user } = useAuth();
  const { showToast } = useToast();

  const [people, setPeople] = useState<ProfessionalRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ type: 'error' | 'network' | 'forbidden'; message?: string } | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ProfessionalCreate>({ first_name: '', last_name: '', email: '', phone: '', status: 'intake', availability_status: 'available', skills: [] });

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProfessionalStatus | ''>('');
  const [availabilityFilter, setAvailabilityFilter] = useState<AvailabilityStatus | ''>('');

  const fetchPeople = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<ProfessionalRead[]>('/people/?limit=100');
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
    const scoped = people.filter(p =>
      (!statusFilter || p.status === statusFilter) &&
      (!availabilityFilter || p.availability_status === availabilityFilter)
    );
    if (!searchQuery.trim()) return scoped;
    const query = searchQuery.toLowerCase();
    return scoped.filter(
      (p) =>
        p.first_name.toLowerCase().includes(query) ||
        p.last_name.toLowerCase().includes(query) ||
        p.email.toLowerCase().includes(query) ||
        p.skills.some((s) => s.toLowerCase().includes(query))
    );
  }, [people, searchQuery, statusFilter, availabilityFilter]);

  const navigateToProfile = (id: string) => {
    router.push(`/workforce/${id}`);
  };

  const getInitials = (firstName: string, lastName: string) =>
    `${firstName[0] || ''}${lastName[0] || ''}`.toUpperCase();

  const createProfessional = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true);
    try {
      await api.post<ProfessionalRead>('/people/', form);
      showToast('success', 'Professional added to workforce intake.');
      setAddOpen(false);
      setForm({ first_name: '', last_name: '', email: '', phone: '', status: 'intake', availability_status: 'available', skills: [] });
      await fetchPeople();
    } catch (err) {
      showToast('error', err instanceof ApiRequestError ? err.userMessage : 'Unable to add professional.');
    } finally { setSaving(false); }
  };

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
          <Button variant="primary" size="sm" onClick={() => setAddOpen(true)}>
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
      <Modal isOpen={addOpen} onClose={() => setAddOpen(false)} title="Add professional">
        <form onSubmit={createProfessional}>
          <div className={uiStyles.formGrid}>
            <div className={uiStyles.formRow}>
              <Input label="First name" required value={form.first_name} onChange={e => setForm({...form, first_name:e.target.value})}/>
              <Input label="Last name" required value={form.last_name} onChange={e => setForm({...form, last_name:e.target.value})}/>
            </div>
            <Input label="Work email" type="email" required value={form.email} onChange={e => setForm({...form, email:e.target.value})}/>
            <Input label="Phone" value={form.phone || ''} onChange={e => setForm({...form, phone:e.target.value})}/>
            <Input label="Skills" placeholder="FastAPI, React, Operations" value={form.skills?.join(', ') || ''} onChange={e => setForm({...form, skills:e.target.value.split(',').map(s=>s.trim()).filter(Boolean)})}/>
            <div className={uiStyles.formRow}>
              <label className={uiStyles.inputWrapper}><span className={uiStyles.inputLabel}>Status</span><select className={uiStyles.selectField} value={form.status} onChange={e=>setForm({...form,status:e.target.value as ProfessionalStatus})}><option value="intake">Intake</option><option value="onboarding">Onboarding</option><option value="ready">Ready</option></select></label>
              <label className={uiStyles.inputWrapper}><span className={uiStyles.inputLabel}>Availability</span><select className={uiStyles.selectField} value={form.availability_status} onChange={e=>setForm({...form,availability_status:e.target.value as AvailabilityStatus})}><option value="available">Available</option><option value="partially_booked">Partially booked</option><option value="fully_booked">Fully booked</option></select></label>
            </div>
          </div>
          <div className={uiStyles.modalActions}><Button type="button" variant="ghost" onClick={()=>setAddOpen(false)}>Cancel</Button><Button type="submit" loading={saving}>Add professional</Button></div>
        </form>
      </Modal>
    </div>
  );
}

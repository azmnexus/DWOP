export interface Tenant {
  id: string;
  name: string;
  slug: string;
  domain?: string;
}

export interface UserProfile {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  tenantId: string;
}

export interface OnboardingRun {
  id: string;
  templateId: string;
  userId: string;
  status: 'pending' | 'in_progress' | 'completed';
  progressPct: number;
}

export interface AccessRequest {
  id: string;
  userId: string;
  provider: 'github' | 'trello' | 'slack';
  roleRequested: string;
  status: 'pending_approval' | 'approved' | 'provisioned' | 'rejected';
}

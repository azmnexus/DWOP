/**
 * DWOP Frontend — TypeScript interfaces matching verified OpenAPI schemas.
 * Field names use snake_case to match backend JSON exactly.
 * Generated from live OpenAPI spec at /api/v1/openapi.json
 */

// ============================================================
// Auth
// ============================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  tenant_id: string;
  role: 'ADMIN' | 'MANAGER' | 'MEMBER';
  email: string;
}

export interface UserRead {
  id: string;
  tenant_id: string;
  email: string;
  role: 'ADMIN' | 'MANAGER' | 'MEMBER';
  is_active: boolean;
  created_at: string;
}

export type UserRole = 'ADMIN' | 'MANAGER' | 'MEMBER';

// ============================================================
// People / Talent
// ============================================================

export type ProfessionalStatus =
  | 'intake'
  | 'onboarding'
  | 'ready'
  | 'assigned'
  | 'offboarding'
  | 'inactive';

export type AvailabilityStatus =
  | 'available'
  | 'partially_booked'
  | 'fully_booked';

export type EngagementType =
  | 'employee'
  | 'contractor'
  | 'working_student';

export type ContractStatus =
  | 'active'
  | 'expired'
  | 'terminated';

export interface EngagementRead {
  id: string;
  tenant_id: string;
  professional_id: string;
  engagement_type: EngagementType;
  start_date: string | null;
  end_date: string | null;
  contract_status: ContractStatus;
  compensation_rate: string | null;
}

export interface EngagementCreate {
  engagement_type?: EngagementType;
  start_date?: string | null;
  end_date?: string | null;
  contract_status?: ContractStatus;
  compensation_rate?: string | null;
}

export interface ProfessionalRead {
  id: string;
  tenant_id: string;
  user_id: string | null;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  status: ProfessionalStatus;
  availability_status: AvailabilityStatus;
  skills: string[];
  created_at: string;
  engagements: EngagementRead[];
}

export interface ProfessionalCreate {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  status?: ProfessionalStatus;
  availability_status?: AvailabilityStatus;
  skills?: string[];
  user_id?: string | null;
  engagement?: EngagementCreate | null;
}

export interface ProfessionalUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  status?: ProfessionalStatus | null;
  availability_status?: AvailabilityStatus | null;
  skills?: string[] | null;
  user_id?: string | null;
}

// ============================================================
// Onboarding
// ============================================================

export interface ChecklistTemplateItemRead {
  id: string;
  template_id: string;
  title: string;
  description: string | null;
  order_index: number;
  required_evidence_type: string;
  default_due_days: number;
}

export interface OnboardingTemplateRead {
  id: string;
  tenant_id: string;
  role_target: string;
  title: string;
  description: string | null;
  version: number;
  is_active: boolean;
  items: ChecklistTemplateItemRead[];
}

export interface OnboardingRunCreate {
  professional_id: string;
  template_id: string;
  assigned_manager_id?: string | null;
}

export interface OnboardingItemRead {
  id: string;
  run_id: string;
  title: string;
  owner_user_id: string | null;
  status: 'pending' | 'blocked' | 'completed';
  due_date: string | null;
  blocker_reason: string | null;
  evidence_ref: string | null;
  completed_at: string | null;
}

export interface OnboardingItemUpdate {
  status?: string | null;
  blocker_reason?: string | null;
  evidence_ref?: string | null;
}

export interface OnboardingRunRead {
  id: string;
  tenant_id: string;
  professional_id: string;
  template_id: string;
  assigned_manager_id: string | null;
  status: string;
  progress_pct: number;
  started_at: string;
  completed_at: string | null;
  items: OnboardingItemRead[];
}

// ============================================================
// API Error
// ============================================================

export interface ApiError {
  status: number;
  message: string;
  detail?: string;
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface Role { id: number; name: string; data_scope: string }
export interface User {
  id: number; company_id: number; branch_id: number | null; role_id: number; username: string; full_name: string;
  email: string | null; mobile: string | null; status: "Active" | "Inactive" | "Suspended"; created_at: string; role: Role;
}
export interface Me extends User { company_name: string; permissions: string[] }
export interface Company { id: number; name: string; phone: string | null; email: string | null; address: string | null; is_active: boolean }
export interface Branch { id: number; company_id: number; name: string; city: string | null; address: string | null; is_active: boolean }
export interface Permission { id: number; code: string }
export interface RoleFull extends Role { permissions: Permission[] }
export interface Assignee { id: number; full_name: string; assigned_at?: string | null }
export interface Customer {
  id: number; name: string; mobile: string; business_type: string | null; product: string | null;
  contact_person: string | null; contact_person_mobile: string | null; address: string | null; city: string; country: string;
  email: string | null; location_url: string | null; business_photo_url: string | null; notes: string | null;
  created_by_user_id: number; status: "Active" | "Inactive"; created_at: string; updated_at: string;
  assigned_salesman: Assignee | null;
}
export interface Assignment {
  id: number; customer_id: number; salesman_id: number; salesman_name: string; assigned_by_user_id: number;
  assigned_by_name: string; assigned_at: string; ended_at: string | null; is_active: boolean;
}
export interface Visit {
  id: number; customer_id: number; customer_name: string | null; user_id: number; user_name: string | null;
  branch_id: number | null; branch_name: string | null; visit_time: string; latitude: number | null; longitude: number | null;
  purpose: string | null; notes: string | null; outcome: string | null; photo_url: string | null; follow_up_id: number | null;
}
export interface Outcome {
  id: number; follow_up_id: number; outcome_text: string; recorded_by_user_id: number; recorded_by_name: string | null; recorded_at: string;
}
export interface FollowUp {
  id: number; customer_id: number; user_id: number; created_by_name: string | null; visit_id: number | null; title: string;
  notes: string | null; due_date: string; status: "Pending" | "Completed" | "Cancelled"; completed_at: string | null;
  created_at: string; is_overdue: boolean;
  customer: { id: number; name: string; mobile: string; city: string; status: string } | null;
  assigned_salesman: Assignee | null;
}
export interface FollowUpDetail extends FollowUp { outcomes: Outcome[] }
export interface ActivityItem { type: string; at: string; user_id: number | null; user_name: string | null; summary: string; ref_id: number }
export interface Dashboard { kind: "admin" | "manager" | "salesman"; [key: string]: any }
export interface ReportResult { columns: { key: string; label: string }[]; rows: Record<string, any>[]; total: number }

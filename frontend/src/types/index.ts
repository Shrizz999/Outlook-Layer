export type BIRole = 'EMPLOYEE' | 'TEAM_LEADER' | 'DEPT_HEAD' | 'MANAGEMENT' | 'SYSADMIN';

export interface BusinessCase {
  id: string;
  case_number: string;
  title: string;
  case_type: 'ENQUIRY' | 'RFQ' | 'ORDER' | 'PROJECT' | 'ISSUE';
  status: 'NEW' | 'UNDER_REVIEW' | 'ACTIVE' | 'WAITING_CUSTOMER' | 'WAITING_SUPPLIER' | 'WAITING_INTERNAL' | 'AT_RISK' | 'COMPLETED';
  priority: 'CRITICAL' | 'HIGH' | 'NORMAL' | 'LOW';
  summary?: string;
  opened_at: string;
  primary_customer_id?: string;
  parties?: CaseParty[];
  links?: CaseLink[];
}

export interface CaseParty {
  id: string;
  party_type: 'CUSTOMER' | 'SUPPLIER' | 'INTERNAL' | 'OTHER';
  party_name?: string;
  relationship_role?: string;
}

export interface CaseLink {
  id: string;
  linked_object_type: string;
  linked_object_id: string;
  relationship_type: string;
  match_method?: string;
  match_confidence?: number;
}

export interface SourceMessage {
  id: string;
  source_mailbox_id: string;
  subject?: string;
  sender_address?: string;
  sender_display_name?: string;
  sent_at?: string;
  body_text?: string;
  body_preprocessed?: string;
  quoted_history_text?: string;
  signature_text?: string;
  processing_status: string;
  has_attachments: boolean;
  latest_analysis?: EmailAnalysis;
}

export interface EmailAnalysis {
  id: string;
  source_message_id: string;
  department?: string;
  domain?: string;
  intent?: string;
  priority: string;
  summary?: string;
  confidence?: number;
  requires_action?: boolean;
  follow_up_required?: boolean;
  raw_structured_output?: {
    references?: Array<{ type: string; value: string; confidence: number; evidence?: string }>;
    actions?: Array<{ action_text: string; action_type: string; suggested_department?: string; deadline?: string; priority?: string; evidence?: string }>;
    commitments?: Array<{ commitment_by: string; commitment_text: string; due_date?: string; evidence?: string }>;
  };
}

export interface TaskProposal {
  id: string;
  title: string;
  description?: string;
  task_type?: string;
  suggested_department?: string;
  priority: string;
  due_date?: string;
  action_evidence?: string;
  confidence?: number;
  proposal_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  approved_task_id?: string;
  business_case_id?: string;
}

export interface LegacyTask {
  task_id: string;
  date?: string;
  description?: string;
  assigned_to?: string;
  assigned_by?: string;
  department?: string;
  deadline?: string;
  priority?: string;
  status?: string;
  reason?: string;
  source?: string;
  business_case_id?: string;
  verification_status?: string;
  progress_percentage?: number;
  delay_reason?: string;
}

export interface TaskDependency {
  id: string;
  predecessor_task_id?: string;
  successor_task_id?: string;
  dependency_type: string;
  status: string;
  is_blocking: boolean;
  reason?: string;
}

export interface SalesOrder {
  id: string;
  so_number: string;
  source_customer_name?: string;
  order_date?: string;
  requested_delivery_date?: string;
  status: string;
  lines: SalesOrderLine[];
}

export interface SalesOrderLine {
  id: string;
  line_number: number;
  source_part_number?: string;
  description?: string;
  ordered_quantity: number;
  delivered_quantity: number;
  unit_of_measure?: string;
  delivery_date?: string;
}

export interface MonitoringAlert {
  id: string;
  alert_type: string;
  severity: string;
  description: string;
  suggested_action?: string;
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';
  created_at: string;
  evidence?: Record<string, any>;
}

export interface DashboardSummary {
  metrics: {
    open_cases_count: number;
    pending_emails_count: number;
    pending_proposals_count: number;
    active_tasks_count: number;
    overdue_tasks_count: number;
    blocked_tasks_count: number;
    open_alerts_count: number;
  };
  department_workload: Record<string, number>;
  recent_alerts: MonitoringAlert[];
  recent_cases: BusinessCase[];
}

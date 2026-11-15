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
  attachments_metadata?: any[];
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

export interface Employee {
  id: string;
  name: string;
  email: string;
  department: string;
  designation?: string;
  phone_number?: string;
  employee_number?: string;
  active: boolean;
  role: BIRole;
  created_at?: string;
  workload_stats?: {
    total_assigned: number;
    pending: number;
    in_progress: number;
    completed: number;
    overdue: number;
    blocked: number;
  };
}

export interface Department {
  id: string;
  code: string;
  name: string;
  parent_id?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface DepartmentHOD {
  id?: string;
  department: string;
  hod_employee_id?: string;
  hod_name?: string;
  hod_email?: string;
  effective_from?: string;
  assigned_by?: string;
  notes?: string;
}

export interface DepartmentStats {
  department: string;
  hod_name: string;
  hod_email?: string;
  total_employees: number;
  active_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  blocked_tasks: number;
  pending_proposals: number;
}

export interface HODDashboard {
  department: string;
  hod: {
    employee_id?: string;
    name?: string;
    email?: string;
    assigned_at?: string;
  };
  employees: Employee[];
  tasks: LegacyTask[];
  proposals: TaskProposal[];
  stats: {
    total_employees: number;
    total_tasks: number;
    pending_tasks: number;
    in_progress_tasks: number;
    completed_tasks: number;
    overdue_tasks: number;
    blocked_tasks: number;
    pending_proposals: number;
  };
}

export interface TaskHandover {
  id: string;
  task_id: string;
  from_employee_id: string;
  to_employee_id: string;
  from_employee_name?: string;
  to_employee_name?: string;
  from_department: string;
  to_department: string;
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'CANCELLED';
  checklist_items: Array<{ item: string; completed: boolean }>;
  notes?: string;
  created_at: string;
}

export interface PhysicalVerification {
  id: string;
  task_id: string;
  verification_type: string;
  verified_by_employee_id: string;
  verified_by_name?: string;
  verified_at: string;
  physical_location?: string;
  result: 'PASS' | 'FAIL' | 'CONDITIONAL';
  notes?: string;
}

export interface EmailDashboardSummary {
  total_ingested: number;
  successfully_processed: number;
  pending_processing: number;
  failed_processing: number;
  duplicate_detected: number;
  awaiting_review: number;
  linked_to_business_cases: number;
  unlinked_emails: number;
  last_ingestion_time?: string;
  sources_breakdown: Record<string, number>;
}

export interface GraphConnectorStatus {
  status: string;
  is_live: boolean;
  message: string;
  auth_mode: string;
  missing_configurations: string[];
  required_azure_permissions: string[];
}

export interface CriticalPathAnalysis {
  critical_path_tasks: string[];
  critical_path_duration_days: number;
  bottlenecks: Array<{
    task_id: string;
    title: string;
    department?: string;
    status: string;
    reason: string;
  }>;
  task_metrics: Record<string, {
    task_id: string;
    title: string;
    department?: string;
    status: string;
    duration_days: number;
    earliest_start: number;
    earliest_finish: number;
    latest_start: number;
    latest_finish: number;
    slack_days: number;
    is_critical: boolean;
  }>;
}

export interface DelayPropagationResult {
  source_task_id: string;
  source_task_title: string;
  delay_days: number;
  downstream_impacted_count: number;
  impacted_tasks: Array<{
    task_id: string;
    title: string;
    department?: string;
    status: string;
    original_deadline?: string;
    delay_days: number;
    impact_severity: string;
  }>;
}

export interface ThreeWayDiscrepancy {
  field: string;
  quote_value?: any;
  po_value?: any;
  so_value?: any;
  discrepancy_type: string;
  severity: string;
  description: string;
}

export interface ThreeWayReconciliationResult {
  status: string;
  is_reconciled: boolean;
  summary: string;
  discrepancies: ThreeWayDiscrepancy[];
  matched_fields: string[];
  recommended_action?: string;
}

export interface UserAccount {
  id: string;
  employee_id?: string;
  email: string;
  full_name: string;
  department: string;
  requested_position: string;
  approved_position: BIRole;
  account_status: 'active' | 'pending_approval' | 'rejected' | 'suspended';
  rejection_reason?: string;
  last_login_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface SessionResponse {
  session_token: string;
  user: UserAccount;
  expires_at: string;
}

export interface RoleRequest {
  id: string;
  user_id: string;
  user_email?: string;
  user_name?: string;
  requested_position: string;
  requested_department: string;
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewed_by?: string;
  review_reason?: string;
  created_at: string;
  reviewed_at?: string;
}

export interface UserAuditLog {
  id: string;
  user_id?: string;
  action: string;
  old_value?: any;
  new_value?: any;
  performed_by: string;
  created_at: string;
}

export interface MicrosoftConnection {
  id: string;
  employee_id: string;
  microsoft_user_id: string;
  tenant_id?: string;
  email_address: string;
  display_name?: string;
  account_type: 'organizational' | 'personal';
  granted_scopes: string[];
  connection_status: 'active' | 'expired' | 'error' | 'disconnected' | 'reauth_required';
  connected_at: string;
  last_synced_at?: string;
  last_error?: string;
  disconnected_at?: string;
  created_at: string;
}

export interface MicrosoftConnectionStatus {
  is_connected: boolean;
  connection?: MicrosoftConnection;
  requires_reauth: boolean;
  folder_count: number;
  message_count: number;
  last_synced_at?: string;
  sync_status: 'idle' | 'syncing' | 'completed' | 'error';
  last_error?: string;
}

export interface EmailFolder {
  id: string;
  connection_id: string;
  graph_folder_id: string;
  parent_folder_id?: string;
  display_name: string;
  well_known_name?: string;
  is_hidden: boolean;
  is_system_folder: boolean;
  sync_enabled: boolean;
  total_item_count: number;
  unread_item_count: number;
  created_at: string;
}

export interface EmailMessage {
  id: string;
  connection_id: string;
  employee_id: string;
  folder_id?: string;
  folder_name?: string;
  graph_message_id: string;
  internet_message_id?: string;
  conversation_id?: string;
  subject?: string;
  sender_name?: string;
  sender_email?: string;
  recipients: Array<{ name?: string; email: string }>;
  cc_recipients: Array<{ name?: string; email: string }>;
  bcc_recipients?: Array<{ name?: string; email: string }>;
  received_at?: string;
  sent_at?: string;
  body_preview?: string;
  body_content?: string;
  body_type?: 'html' | 'text';
  has_attachments: boolean;
  importance: 'low' | 'normal' | 'high';
  is_read: boolean;
  is_draft: boolean;
  is_deleted: boolean;
  is_flagged?: boolean;
  flag_status?: 'flagged' | 'notFlagged' | 'complete';
  categories?: string[];
  send_status?: 'draft' | 'pending_send' | 'sending' | 'sent' | 'failed' | 'synced';
  send_error?: string;
  in_reply_to_id?: string;
  idempotency_key?: string;
  web_link?: string;
  source: string;
  created_at: string;
  latest_analysis?: any;
}

export interface EmailDraft {
  id: string;
  connection_id: string;
  employee_id: string;
  graph_draft_id?: string;
  reply_to_message_id?: string;
  reply_mode: 'new' | 'reply' | 'reply_all' | 'forward';
  subject: string;
  to_recipients: Array<{ name?: string; email: string }>;
  cc_recipients: Array<{ name?: string; email: string }>;
  bcc_recipients: Array<{ name?: string; email: string }>;
  body_content: string;
  body_type: 'html' | 'text';
  importance: 'low' | 'normal' | 'high';
  status: string;
  last_saved_at: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationThread {
  conversation_id: string;
  message_count: number;
  messages: EmailMessage[];
}

export interface TodoTaskMapping {
  id: string;
  task_id: string;
  connection_id: string;
  provider: string;
  external_list_id: string;
  external_task_id: string;
  title: string;
  due_date?: string;
  status: string;
  external_url?: string;
  synced_at: string;
}

export interface EmailComposeSendPayload {
  subject: string;
  body_content: string;
  body_type?: 'html' | 'text';
  to_recipients: Array<{ name?: string; email: string }>;
  cc_recipients?: Array<{ name?: string; email: string }>;
  bcc_recipients?: Array<{ name?: string; email: string }>;
  importance?: 'low' | 'normal' | 'high';
  draft_id?: string;
  idempotency_key?: string;
}

export interface SyncRun {
  id: string;
  connection_id: string;
  sync_type: string;
  status: 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'FAILED';
  started_at: string;
  completed_at?: string;
  messages_discovered: number;
  messages_inserted: number;
  messages_updated: number;
  messages_deleted: number;
  errors_count: number;
  error_summary?: string;
}

export interface OutlookAdminOverview {
  total_employees: number;
  connected_employees_count: number;
  active_connections_count: number;
  expired_connections_count: number;
  failed_connections_count: number;
  total_synchronized_messages: number;
  total_discovered_folders: number;
  last_sync_completed_at?: string;
  active_sync_jobs: number;
  recent_sync_runs: SyncRun[];
}

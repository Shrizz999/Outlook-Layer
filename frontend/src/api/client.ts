import {
  BusinessCase,
  CriticalPathAnalysis,
  DashboardSummary,
  DelayPropagationResult,
  Department,
  DepartmentHOD,
  DepartmentStats,
  EmailAnalysis,
  EmailDashboardSummary,
  Employee,
  GraphConnectorStatus,
  HODDashboard,
  LegacyTask,
  MonitoringAlert,
  PhysicalVerification,
  SalesOrder,
  SourceMessage,
  TaskDependency,
  TaskHandover,
  TaskProposal,
  ThreeWayReconciliationResult,
  UserAccount,
  SessionResponse,
  RoleRequest,
  UserAuditLog,
  MicrosoftConnection,
  MicrosoftConnectionStatus,
  EmailFolder,
  EmailMessage,
  EmailDraft,
  ConversationThread,
  TodoTaskMapping,
  EmailComposeSendPayload,
  SyncRun,
  OutlookAdminOverview,
} from '../types';

const API_BASE = 'http://localhost:8000/api/v1';

let authToken: string | null = typeof window !== 'undefined' ? sessionStorage.getItem('bi_session_token') : null;

export const authStorage = {
  getToken: () => authToken,
  setToken: (token: string) => {
    authToken = token;
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('bi_session_token', token);
    }
  },
  clearToken: () => {
    authToken = null;
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('bi_session_token');
    }
  },
};

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const opts: RequestInit = { ...(options || {}) };
  opts.credentials = 'include';
  const headers = new Headers(opts.headers || {});
  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }
  opts.headers = headers;

  const res = await fetch(url, opts);
  if (!res.ok) {
    let errorDetail = `API error ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      const errorText = await res.text();
      if (errorText) errorDetail = errorText;
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // Dashboard & Admin
  getDashboardSummary: () => fetchJson<DashboardSummary>(`${API_BASE}/admin/dashboard-summary`),
  getAiUsage: () => fetchJson<any>(`${API_BASE}/admin/ai-usage`),
  getSystemStatus: () => fetchJson<any>(`${API_BASE}/admin/system-status`),
  resetOperationalData: () =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/admin/reset-data`, { method: 'POST' }),

  // Business Cases
  listCases: () => fetchJson<BusinessCase[]>(`${API_BASE}/business-cases`),
  getCase: (id: string) => fetchJson<BusinessCase>(`${API_BASE}/business-cases/${id}`),
  reconcileThreeWay: (payload: { quote?: any; purchase_order?: any; sales_order?: any }) =>
    fetchJson<ThreeWayReconciliationResult>(`${API_BASE}/business-cases/reconcile-3way`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Emails & Offline Ingestion
  listEmails: () => fetchJson<SourceMessage[]>(`${API_BASE}/emails`),
  getEmail: (id: string) => fetchJson<SourceMessage>(`${API_BASE}/emails/${id}`),
  getEmailAnalysis: (id: string) => fetchJson<EmailAnalysis>(`${API_BASE}/emails/${id}/analysis`),
  getEmailDashboardSummary: () => fetchJson<EmailDashboardSummary>(`${API_BASE}/emails/dashboard-summary`),
  triggerAnalysis: (id: string) =>
    fetchJson<EmailAnalysis>(`${API_BASE}/emails/${id}/analyse`, { method: 'POST' }),
  reprocessEmail: (id: string) =>
    fetchJson<SourceMessage>(`${API_BASE}/emails/${id}/reprocess`, { method: 'POST' }),
  manualIngestEmail: (payload: {
    sender_email: string;
    sender_name?: string;
    to_recipients?: Array<{ address: string; display_name?: string }>;
    subject: string;
    body: string;
    received_at?: string;
    has_attachments?: boolean;
  }) =>
    fetchJson<SourceMessage>(`${API_BASE}/emails/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  ingestEmail: (payload: { subject: string; sender_name: string; sender_email: string; body: string }) =>
    fetchJson<SourceMessage>(`${API_BASE}/emails/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  uploadEml: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/emails/upload-eml`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Upload failed: ${errorText}`);
    }
    return res.json() as Promise<SourceMessage>;
  },
  uploadBatchEml: async (files: File[]) => {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    const res = await fetch(`${API_BASE}/emails/upload-batch`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Batch upload failed: ${errorText}`);
    }
    return res.json() as Promise<{ total_uploaded: number; ingested: any[]; failed: any[] }>;
  },
  uploadZipEml: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/emails/upload-zip`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`ZIP upload failed: ${errorText}`);
    }
    return res.json() as Promise<{ total_extracted: number; ingested: any[]; failed: any[] }>;
  },
  importFixtures: () =>
    fetchJson<{ total_files_found: number; successfully_ingested: number; skipped_duplicates: number }>(
      `${API_BASE}/emails/import-fixtures`,
      { method: 'POST' }
    ),
  importTrainData: (batch: string = 'all', limit?: number) => {
    const params = new URLSearchParams({ batch });
    if (limit) params.set('limit', limit.toString());
    return fetchJson<{
      batch_name: string;
      total_imported: number;
      total_duplicates: number;
      total_tasks_created: number;
      total_dependencies_created: number;
      active_bottlenecks: any[];
      batches_processed: any[];
    }>(`${API_BASE}/emails/import-train-data?${params.toString()}`, { method: 'POST' });
  },
  listAllAttachments: () => fetchJson<any[]>(`${API_BASE}/emails/attachments/all`),
  getMessageAttachments: (messageId: string) => fetchJson<any[]>(`${API_BASE}/emails/${messageId}/attachments`),
  getGraphStatus: () => fetchJson<GraphConnectorStatus>(`${API_BASE}/emails/connectors/graph/status`),

  // Employee Management
  listEmployees: (department?: string) => {
    const url = department
      ? `${API_BASE}/employees?department=${encodeURIComponent(department)}`
      : `${API_BASE}/employees`;
    return fetchJson<Employee[]>(url);
  },
  createEmployee: (payload: {
    name: string;
    email: string;
    department: string;
    designation?: string;
    phone_number?: string;
    employee_number?: string;
    role?: string;
    active?: boolean;
  }) =>
    fetchJson<Employee>(`${API_BASE}/employees`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getEmployee: (id: string) => fetchJson<Employee>(`${API_BASE}/employees/${id}`),
  updateEmployee: (id: string, payload: Partial<Employee>) =>
    fetchJson<Employee>(`${API_BASE}/employees/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getEmployeeWorkload: (id: string) => fetchJson<any>(`${API_BASE}/employees/${id}/workload`),

  // Department & HOD Management
  listDepartments: () => fetchJson<Department[]>(`${API_BASE}/departments`),
  listDepartmentStats: () => fetchJson<DepartmentStats[]>(`${API_BASE}/departments/stats`),
  getDepartmentHOD: (department: string) =>
    fetchJson<DepartmentHOD>(`${API_BASE}/departments/${encodeURIComponent(department)}/hod`),
  assignDepartmentHOD: (payload: { department: string; employee_id: string; notes?: string }) =>
    fetchJson<DepartmentHOD>(`${API_BASE}/departments/hod`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  removeDepartmentHOD: (department: string) =>
    fetchJson<{ status: string; department: string }>(
      `${API_BASE}/departments/${encodeURIComponent(department)}/hod`,
      { method: 'DELETE' }
    ),
  getHODDashboard: (department: string) =>
    fetchJson<HODDashboard>(`${API_BASE}/departments/${encodeURIComponent(department)}/dashboard`),
  listHandovers: (department?: string) => {
    const url = department
      ? `${API_BASE}/departments/handovers/list?department=${encodeURIComponent(department)}`
      : `${API_BASE}/departments/handovers/list`;
    return fetchJson<TaskHandover[]>(url);
  },
  createHandover: (payload: {
    task_id: string;
    from_employee_id: string;
    to_employee_id: string;
    from_department: string;
    to_department: string;
    checklist_items?: Array<{ item: string; completed: boolean }>;
    notes?: string;
  }) =>
    fetchJson<TaskHandover>(`${API_BASE}/departments/handovers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  actionHandover: (id: string, action: 'ACCEPT' | 'REJECT', notes?: string) =>
    fetchJson<TaskHandover>(`${API_BASE}/departments/handovers/${id}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, notes }),
    }),
  createPhysicalVerification: (payload: {
    task_id: string;
    verification_type: string;
    verified_by_employee_id: string;
    physical_location?: string;
    result: 'PASS' | 'FAIL' | 'CONDITIONAL';
    notes?: string;
  }) =>
    fetchJson<PhysicalVerification>(`${API_BASE}/departments/physical-verifications`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Tasks
  listTasks: (department?: string) => {
    const url = department
      ? `${API_BASE}/tasks?department=${encodeURIComponent(department)}`
      : `${API_BASE}/tasks`;
    return fetchJson<LegacyTask[]>(url);
  },
  listProposals: () => fetchJson<TaskProposal[]>(`${API_BASE}/tasks/proposals/list`),
  approveProposal: (proposalId: string, payload: { assigned_to_name?: string; deadline?: string; priority?: string }) =>
    fetchJson<LegacyTask>(`${API_BASE}/tasks/proposals/${proposalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getCriticalPath: (caseId?: string) => {
    const url = caseId
      ? `${API_BASE}/tasks/analytics/critical-path?case_id=${encodeURIComponent(caseId)}`
      : `${API_BASE}/tasks/analytics/critical-path`;
    return fetchJson<CriticalPathAnalysis>(url);
  },
  propagateDelay: (taskId: string, delayDays: number) =>
    fetchJson<DelayPropagationResult>(`${API_BASE}/tasks/${taskId}/propagate-delay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delay_days: delayDays }),
    }),
  getCaseTraceability: (caseId: string) =>
    fetchJson<{
      business_case_id: string;
      total_tasks: number;
      completed_tasks: number;
      progress_percentage: number;
      active_bottleneck: any;
      timeline: Array<{
        task_id: string;
        description: string;
        assigned_to: string;
        assigned_by: string;
        department: string;
        status: string;
        deadline?: string;
        is_completed: boolean;
        predecessor_task_id?: string;
      }>;
    }>(`${API_BASE}/tasks/traceability/${caseId}`),
  getBottlenecks: () =>
    fetchJson<Array<{
      case_id: string;
      case_number: string;
      title: string;
      progress_percentage: number;
      task_id: string;
      bottleneck_employee: string;
      department: string;
      status: string;
      deadline?: string;
      reason: string;
    }>>(`${API_BASE}/tasks/analytics/bottlenecks`),

  // Dependencies
  listDependencies: () => fetchJson<TaskDependency[]>(`${API_BASE}/tasks/dependencies/list`),
  createDependency: (payload: { predecessor_task_id: string; successor_task_id: string; reason?: string }) =>
    fetchJson<TaskDependency>(`${API_BASE}/tasks/dependencies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, predecessor_type: 'TASK', successor_type: 'TASK', is_blocking: true }),
    }),

  // Orders
  listOrders: () => fetchJson<SalesOrder[]>(`${API_BASE}/orders`),
  getOrder: (soNumber: string) => fetchJson<SalesOrder>(`${API_BASE}/orders/${soNumber}`),

  // Alerts
  listAlerts: () => fetchJson<MonitoringAlert[]>(`${API_BASE}/alerts`),
  acknowledgeAlert: (id: string) =>
    fetchJson<any>(`${API_BASE}/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolveAlert: (id: string, notes?: string) =>
    fetchJson<any>(`${API_BASE}/alerts/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    }),

  // Authentication & Session
  register: (payload: {
    full_name: string;
    email: string;
    password: string;
    confirm_password: string;
    department: string;
    position: string;
  }) =>
    fetchJson<UserAccount>(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  login: async (payload: { email: string; password: string }) => {
    const res = await fetchJson<SessionResponse>(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res && res.session_token) {
      authStorage.setToken(res.session_token);
    }
    return res;
  },

  logout: async () => {
    try {
      await fetchJson<{ status: string; message: string }>(`${API_BASE}/auth/logout`, {
        method: 'POST',
      });
    } finally {
      authStorage.clearToken();
    }
  },

  getMe: () => fetchJson<UserAccount>(`${API_BASE}/auth/me`),

  // Admin User & Role Management
  listAdminUsers: (params?: { department?: string; position?: string; account_status?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.department) query.set('department', params.department);
    if (params?.position) query.set('position', params.position);
    if (params?.account_status) query.set('account_status', params.account_status);
    if (params?.search) query.set('search', params.search);
    const qs = query.toString();
    return fetchJson<UserAccount[]>(`${API_BASE}/auth/admin/users${qs ? `?${qs}` : ''}`);
  },

  updateAdminUser: (
    userId: string,
    payload: {
      approved_position?: string;
      department?: string;
      account_status?: string;
      employee_id?: string;
      rejection_reason?: string;
    }
  ) =>
    fetchJson<UserAccount>(`${API_BASE}/auth/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  adminResetPassword: (userId: string, newPassword: string) =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/auth/admin/users/${userId}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_password: newPassword }),
    }),

  listRoleRequests: (status?: string) => {
    const qs = status ? `?approval_status=${encodeURIComponent(status)}` : '';
    return fetchJson<RoleRequest[]>(`${API_BASE}/auth/admin/role-requests${qs}`);
  },

  reviewRoleRequest: (requestId: string, payload: { approval_status: 'APPROVED' | 'REJECTED'; reason?: string }) =>
    fetchJson<RoleRequest>(`${API_BASE}/auth/admin/role-requests/${requestId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  listAuditLogs: (userId?: string) => {
    const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
    return fetchJson<UserAuditLog[]>(`${API_BASE}/auth/admin/audit-logs${qs}`);
  },

  // Department Dashboard (HOD View)
  getDepartmentDashboard: (deptCodeOrId: string) =>
    fetchJson<HODDashboard>(`${API_BASE}/departments/${deptCodeOrId}/dashboard`),

  // Multi-User Microsoft Outlook Integration
  getOutlookConnectUrl: () =>
    fetchJson<{ authorization_url: string; state: string }>(`${API_BASE}/outlook/connect`),

  mockConnectOutlook: (accountType: 'organizational' | 'personal' = 'organizational', email?: string) => {
    const qs = new URLSearchParams({ account_type: accountType });
    if (email) qs.set('email', email);
    return fetchJson<MicrosoftConnection>(`${API_BASE}/outlook/mock-connect?${qs.toString()}`, {
      method: 'POST',
    });
  },

  getOutlookStatus: () =>
    fetchJson<MicrosoftConnectionStatus>(`${API_BASE}/outlook/connection`),

  disconnectOutlook: () =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/outlook/disconnect`, {
      method: 'POST',
    }),

  triggerOutlookSync: () =>
    fetchJson<{ status: string; message: string; sync_run_id: string }>(`${API_BASE}/outlook/sync`, {
      method: 'POST',
    }),

  listOutlookFolders: () =>
    fetchJson<EmailFolder[]>(`${API_BASE}/outlook/folders`),

  listOutlookSyncRuns: (limit = 10) =>
    fetchJson<SyncRun[]>(`${API_BASE}/outlook/sync/runs?limit=${limit}`),

  listOutlookEmails: (params?: { folderId?: string; search?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.folderId) query.set('folder_id', params.folderId);
    if (params?.search) query.set('search', params.search);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return fetchJson<EmailMessage[]>(`${API_BASE}/outlook/emails${qs ? `?${qs}` : ''}`);
  },

  getOutlookEmailDetail: (messageId: string) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}`),

  getOutlookEmailAnalysis: (messageId: string) =>
    fetchJson<any>(`${API_BASE}/outlook/emails/${messageId}/analysis`),

  markOutlookEmailRead: (messageId: string, isRead: boolean) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}/read`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_read: isRead }),
    }),

  updateOutlookEmailFlag: (messageId: string, isFlagged: boolean) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}/flag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        is_flagged: isFlagged,
        flag_status: isFlagged ? 'flagged' : 'notFlagged',
      }),
    }),

  moveOutlookEmail: (messageId: string, destinationFolderId: string) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}/move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination_folder_id: destinationFolderId }),
    }),

  deleteOutlookEmail: (messageId: string, permanent = false) =>
    fetchJson<{ status: string; message: string }>(
      `${API_BASE}/outlook/emails/${messageId}?permanent=${permanent}`,
      { method: 'DELETE' }
    ),

  getConversationThread: (conversationId: string) =>
    fetchJson<ConversationThread>(`${API_BASE}/outlook/conversations/${encodeURIComponent(conversationId)}`),

  sendOutlookEmail: (payload: EmailComposeSendPayload) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  replyOutlookEmail: (messageId: string, comment: string, replyAll = false) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comment, reply_all: replyAll }),
    }),

  forwardOutlookEmail: (
    messageId: string,
    toRecipients: Array<{ name?: string; email: string }>,
    comment = ''
  ) =>
    fetchJson<EmailMessage>(`${API_BASE}/outlook/emails/${messageId}/forward`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ to_recipients: toRecipients, comment }),
    }),

  listOutlookDrafts: () =>
    fetchJson<EmailDraft[]>(`${API_BASE}/outlook/drafts`),

  saveOutlookDraft: (draft: Partial<EmailDraft>) =>
    fetchJson<EmailDraft>(`${API_BASE}/outlook/drafts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draft),
    }),

  deleteOutlookDraft: (draftId: string) =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/outlook/drafts/${draftId}`, {
      method: 'DELETE',
    }),

  createTodoFromEmail: (
    messageId: string,
    payload: { title: string; notes?: string; importance?: string; due_date?: string; task_id?: string }
  ) =>
    fetchJson<TodoTaskMapping>(`${API_BASE}/outlook/emails/${messageId}/create-todo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  listTodoMappings: () =>
    fetchJson<TodoTaskMapping[]>(`${API_BASE}/outlook/todo/mappings`),

  getOutlookAdminOverview: () =>
    fetchJson<OutlookAdminOverview>(`${API_BASE}/outlook/admin/overview`),
};

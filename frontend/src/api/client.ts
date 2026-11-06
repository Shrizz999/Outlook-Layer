import {
  BusinessCase,
  DashboardSummary,
  EmailAnalysis,
  LegacyTask,
  MonitoringAlert,
  SalesOrder,
  SourceMessage,
  TaskDependency,
  TaskProposal,
} from '../types';

const API_BASE = 'http://localhost:8000/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error ${res.status}: ${errorText}`);
  }
  return res.json();
}

export const api = {
  // Dashboard & Admin
  getDashboardSummary: () => fetchJson<DashboardSummary>(`${API_BASE}/admin/dashboard-summary`),
  getAiUsage: () => fetchJson<any>(`${API_BASE}/admin/ai-usage`),
  getSystemStatus: () => fetchJson<any>(`${API_BASE}/admin/system-status`),

  // Business Cases
  listCases: () => fetchJson<BusinessCase[]>(`${API_BASE}/business-cases`),
  getCase: (id: string) => fetchJson<BusinessCase>(`${API_BASE}/business-cases/${id}`),

  // Emails
  listEmails: () => fetchJson<SourceMessage[]>(`${API_BASE}/emails`),
  getEmail: (id: string) => fetchJson<SourceMessage>(`${API_BASE}/emails/${id}`),
  getEmailAnalysis: (id: string) => fetchJson<EmailAnalysis>(`${API_BASE}/emails/${id}/analysis`),
  triggerAnalysis: (id: string) =>
    fetchJson<EmailAnalysis>(`${API_BASE}/emails/${id}/analyse`, { method: 'POST' }),
  ingestEmail: (payload: { subject: string; sender_name: string; sender_email: string; body: string }) =>
    fetchJson<SourceMessage>(`${API_BASE}/emails/ingest`, {
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

  // Tasks
  listTasks: () => fetchJson<LegacyTask[]>(`${API_BASE}/tasks`),
  listProposals: () => fetchJson<TaskProposal[]>(`${API_BASE}/tasks/proposals/list`),
  approveProposal: (proposalId: string, payload: { assigned_to_name?: string; deadline?: string }) =>
    fetchJson<LegacyTask>(`${API_BASE}/tasks/proposals/${proposalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

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
};

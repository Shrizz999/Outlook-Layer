import React, { useEffect, useState } from 'react';
import {
  Users,
  ShieldCheck,
  Check,
  X,
  Search,
  Filter,
  KeyRound,
  Ban,
  UserCheck,
  History,
  RefreshCw,
  AlertTriangle,
  Building,
  CheckCircle2,
} from 'lucide-react';
import { api } from '../api/client';
import { Department, RoleRequest, UserAccount, UserAuditLog } from '../types';

export const AdminUserManagementView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'requests' | 'audit'>('users');

  // Users state
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [search, setSearch] = useState('');
  const [filterDept, setFilterDept] = useState('');
  const [filterPos, setFilterPos] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Role requests state
  const [requests, setRequests] = useState<RoleRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [rejectModalReq, setRejectModalReq] = useState<RoleRequest | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // Password reset modal state
  const [resetModalUser, setResetModalUser] = useState<UserAccount | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  // Position change modal state
  const [editRoleUser, setEditRoleUser] = useState<UserAccount | null>(null);
  const [targetPosition, setTargetPosition] = useState('');
  const [targetDepartment, setTargetDepartment] = useState('');

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<UserAuditLog[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Notification banners
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const data = await api.listAdminUsers({
        department: filterDept || undefined,
        position: filterPos || undefined,
        account_status: filterStatus || undefined,
        search: search || undefined,
      });
      setUsers(data);
    } catch (err: any) {
      console.error('Failed to load users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadRequests = async () => {
    setLoadingRequests(true);
    try {
      const data = await api.listRoleRequests();
      setRequests(data);
    } catch (err: any) {
      console.error('Failed to load role requests:', err);
    } finally {
      setLoadingRequests(false);
    }
  };

  const loadAuditLogs = async () => {
    setLoadingAudit(true);
    try {
      const data = await api.listAuditLogs();
      setAuditLogs(data);
    } catch (err: any) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoadingAudit(false);
    }
  };

  const loadDepartments = async () => {
    try {
      const depts = await api.listDepartments();
      setDepartments(depts);
    } catch (err) {
      console.error('Failed to load departments:', err);
    }
  };

  useEffect(() => {
    loadDepartments();
  }, []);

  useEffect(() => {
    if (activeTab === 'users') {
      loadUsers();
    } else if (activeTab === 'requests') {
      loadRequests();
    } else if (activeTab === 'audit') {
      loadAuditLogs();
    }
  }, [activeTab, filterDept, filterPos, filterStatus, search]);

  const showNotification = (type: 'success' | 'error', text: string) => {
    setStatusMsg({ type, text });
    setTimeout(() => setStatusMsg(null), 5000);
  };

  // --- Actions ---

  const handleApproveRequest = async (req: RoleRequest) => {
    try {
      await api.reviewRoleRequest(req.id, {
        approval_status: 'APPROVED',
        reason: 'Approved by Administrator',
      });
      showNotification('success', `Role request for ${req.user_name || req.user_email} approved successfully.`);
      loadRequests();
      loadUsers();
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to approve request.');
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectModalReq) return;
    try {
      await api.reviewRoleRequest(rejectModalReq.id, {
        approval_status: 'REJECTED',
        reason: rejectReason || 'Declined by Administrator',
      });
      showNotification('success', `Role request rejected.`);
      setRejectModalReq(null);
      setRejectReason('');
      loadRequests();
      loadUsers();
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to reject request.');
    }
  };

  const handleToggleSuspend = async (u: UserAccount) => {
    const newStatus = u.account_status === 'suspended' ? 'active' : 'suspended';
    try {
      await api.updateAdminUser(u.id, {
        account_status: newStatus,
        rejection_reason: newStatus === 'suspended' ? 'Account suspended by administrator' : undefined,
      });
      showNotification('success', `Account for ${u.full_name} is now ${newStatus}.`);
      loadUsers();
    } catch (err: any) {
      showNotification('error', err.message || 'Status change failed.');
    }
  };

  const handleConfirmRoleUpdate = async () => {
    if (!editRoleUser) return;
    try {
      await api.updateAdminUser(editRoleUser.id, {
        approved_position: targetPosition || editRoleUser.approved_position,
        department: targetDepartment || editRoleUser.department,
      });
      showNotification('success', `Position/department updated for ${editRoleUser.full_name}.`);
      setEditRoleUser(null);
      loadUsers();
    } catch (err: any) {
      showNotification('error', err.message || 'Update failed.');
    }
  };

  const handleConfirmResetPassword = async () => {
    if (!resetModalUser || !newPassword) return;
    try {
      await api.adminResetPassword(resetModalUser.id, newPassword);
      setResetMsg('Password successfully reset. Active sessions invalidated.');
      setTimeout(() => {
        setResetModalUser(null);
        setNewPassword('');
        setResetMsg(null);
      }, 2000);
    } catch (err: any) {
      setResetMsg(err.message || 'Password reset failed.');
    }
  };

  const pendingRequestsCount = requests.filter((r) => r.approval_status === 'PENDING').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">User & RBAC Management</h2>
          <p className="text-xs text-slate-500">
            Internal credentials, departmental HOD approvals, account status, and audit trails
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('users')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition ${
              activeTab === 'users' ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>User Accounts</span>
            <span className="text-[10px] bg-slate-200 text-slate-700 px-1.5 py-0.2 rounded-full ml-1">
              {users.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('requests')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition relative ${
              activeTab === 'requests' ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Role Approvals</span>
            {pendingRequestsCount > 0 && (
              <span className="text-[10px] bg-amber-500 text-white font-bold px-1.5 py-0.2 rounded-full ml-1">
                {pendingRequestsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition ${
              activeTab === 'audit' ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Audit Trail</span>
          </button>
        </div>
      </div>

      {statusMsg && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex items-center space-x-2 ${
            statusMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          )}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* --- TAB 1: USERS --- */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-wrap gap-3 items-center justify-between text-xs">
            <div className="flex items-center space-x-2 flex-1 min-w-[240px]">
              <Search className="w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search by name, email, department..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center space-x-2 flex-wrap gap-2">
              <select
                value={filterDept}
                onChange={(e) => setFilterDept(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All Departments</option>
                {departments.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.code} - {d.name}
                  </option>
                ))}
              </select>

              <select
                value={filterPos}
                onChange={(e) => setFilterPos(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All Positions</option>
                <option value="EMPLOYEE">Employee</option>
                <option value="DEPT_HEAD">HOD (Department Head)</option>
                <option value="MANAGEMENT">Manager</option>
                <option value="SYSADMIN">Administrator</option>
              </select>

              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All Statuses</option>
                <option value="active">Active</option>
                <option value="pending_approval">Pending Approval</option>
                <option value="suspended">Suspended</option>
                <option value="rejected">Rejected</option>
              </select>

              <button
                onClick={loadUsers}
                className="p-1.5 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition"
                title="Refresh user list"
              >
                <RefreshCw className={`w-4 h-4 ${loadingUsers ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Users Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 font-semibold text-slate-600">
                  <tr>
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Department</th>
                    <th className="py-3 px-4">Approved Role</th>
                    <th className="py-3 px-4">Requested Role</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Last Login</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {users.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        {loadingUsers ? 'Loading registered accounts...' : 'No user accounts match current filters.'}
                      </td>
                    </tr>
                  ) : (
                    users.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{u.full_name}</div>
                          <div className="text-[11px] text-slate-400">{u.email}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium text-slate-800">{u.department}</span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`font-semibold px-2 py-0.5 rounded-full text-[11px] border ${
                              u.approved_position === 'SYSADMIN'
                                ? 'bg-purple-50 text-purple-700 border-purple-200'
                                : u.approved_position === 'MANAGEMENT'
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : u.approved_position === 'DEPT_HEAD'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-slate-100 text-slate-700 border-slate-200'
                            }`}
                          >
                            {u.approved_position}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600 font-medium">
                          {u.requested_position}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              u.account_status === 'active'
                                ? 'bg-emerald-100 text-emerald-800'
                                : u.account_status === 'pending_approval'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-rose-100 text-rose-800'
                            }`}
                          >
                            {u.account_status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-[11px] text-slate-500">
                          {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                        </td>
                        <td className="py-3 px-4 text-right space-x-2">
                          <button
                            onClick={() => {
                              setEditRoleUser(u);
                              setTargetPosition(u.approved_position);
                              setTargetDepartment(u.department);
                            }}
                            className="text-blue-600 hover:text-blue-800 font-medium underline underline-offset-2"
                          >
                            Edit Role
                          </button>

                          <button
                            onClick={() => {
                              setResetModalUser(u);
                              setNewPassword('');
                              setResetMsg(null);
                            }}
                            className="text-slate-600 hover:text-slate-900 font-medium"
                            title="Reset Password"
                          >
                            Reset Pwd
                          </button>

                          <button
                            onClick={() => handleToggleSuspend(u)}
                            className={`font-semibold ${
                              u.account_status === 'suspended'
                                ? 'text-emerald-600 hover:text-emerald-800'
                                : 'text-rose-600 hover:text-rose-800'
                            }`}
                          >
                            {u.account_status === 'suspended' ? 'Reactivate' : 'Suspend'}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 2: ROLE APPROVALS --- */}
      {activeTab === 'requests' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Position Elevation Requests</h3>
                <p className="text-xs text-slate-500">
                  Review and approve employee requests for HOD, Manager, and Administrator status
                </p>
              </div>
              <button
                onClick={loadRequests}
                className="text-xs text-slate-500 hover:text-slate-800 flex items-center space-x-1"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingRequests ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 font-semibold text-slate-600">
                  <tr>
                    <th className="py-3 px-4">Applicant</th>
                    <th className="py-3 px-4">Requested Role</th>
                    <th className="py-3 px-4">Target Department</th>
                    <th className="py-3 px-4">Request Date</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {requests.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400">
                        {loadingRequests ? 'Loading role requests...' : 'No role approval requests pending.'}
                      </td>
                    </tr>
                  ) : (
                    requests.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{r.user_name || 'Anonymous User'}</div>
                          <div className="text-[11px] text-slate-400">{r.user_email}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full text-[11px]">
                            {r.requested_position}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-800">
                          {r.requested_department}
                        </td>
                        <td className="py-3 px-4 text-[11px] text-slate-500">
                          {new Date(r.created_at).toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              r.approval_status === 'APPROVED'
                                ? 'bg-emerald-100 text-emerald-800'
                                : r.approval_status === 'REJECTED'
                                ? 'bg-rose-100 text-rose-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {r.approval_status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right space-x-2">
                          {r.approval_status === 'PENDING' ? (
                            <>
                              <button
                                onClick={() => handleApproveRequest(r)}
                                className="inline-flex items-center px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded text-xs transition space-x-1 shadow-xs"
                              >
                                <Check className="w-3.5 h-3.5" />
                                <span>Approve</span>
                              </button>
                              <button
                                onClick={() => {
                                  setRejectModalReq(r);
                                  setRejectReason('');
                                }}
                                className="inline-flex items-center px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded text-xs transition space-x-1 shadow-xs"
                              >
                                <X className="w-3.5 h-3.5" />
                                <span>Reject</span>
                              </button>
                            </>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">
                              Reviewed by {r.reviewed_by || 'Admin'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* --- TAB 3: AUDIT TRAIL --- */}
      {activeTab === 'audit' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Administrative Security Audit Trail</h3>
              <p className="text-xs text-slate-500">
                Immutable records of role approvals, department reassignments, suspensions, and resets
              </p>
            </div>
            <button
              onClick={loadAuditLogs}
              className="text-xs text-slate-500 hover:text-slate-800 flex items-center space-x-1"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingAudit ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 font-semibold text-slate-600">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Performed By</th>
                  <th className="py-3 px-4">Details / Values</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-400">
                      {loadingAudit ? 'Loading audit records...' : 'No audit entries recorded yet.'}
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3 px-4 text-[11px] text-slate-500 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-900">
                        <span className="bg-slate-100 text-slate-800 px-2 py-0.5 rounded font-mono text-[11px]">
                          {log.action}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-700 font-medium">
                        {log.performed_by}
                      </td>
                      <td className="py-3 px-4 text-[11px] font-mono text-slate-600 max-w-md truncate">
                        {log.new_value ? JSON.stringify(log.new_value) : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* --- Reject Modal --- */}
      {rejectModalReq && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-600" />
              <span>Reject Role Request</span>
            </h3>
            <p className="text-xs text-slate-500">
              Provide a reason for rejecting the request of{' '}
              <strong className="text-slate-800">{rejectModalReq.user_name || rejectModalReq.user_email}</strong> for{' '}
              <strong className="text-slate-800">{rejectModalReq.requested_position}</strong> status:
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Applicant does not meet criteria for Department Head..."
              rows={3}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-rose-500"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setRejectModalReq(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 rounded font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="px-3 py-1.5 text-xs bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded shadow-xs"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- Edit Role & Department Modal --- */}
      {editRoleUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              <span>Modify Position & Department</span>
            </h3>
            <p className="text-xs text-slate-500">
              Target User: <strong className="text-slate-800">{editRoleUser.full_name}</strong> ({editRoleUser.email})
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 font-medium mb-1">Approved Position</label>
                <select
                  value={targetPosition}
                  onChange={(e) => setTargetPosition(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-800"
                >
                  <option value="EMPLOYEE">Employee</option>
                  <option value="DEPT_HEAD">HOD (Department Head)</option>
                  <option value="MANAGEMENT">Manager</option>
                  <option value="SYSADMIN">Administrator</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">Assigned Department</label>
                <select
                  value={targetDepartment}
                  onChange={(e) => setTargetDepartment(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-800"
                >
                  {departments.map((d) => (
                    <option key={d.code} value={d.code}>
                      {d.code} - {d.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setEditRoleUser(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 rounded font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRoleUpdate}
                className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded shadow-xs"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- Password Reset Modal --- */}
      {resetModalUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center space-x-2">
              <KeyRound className="w-4 h-4 text-amber-600" />
              <span>Admin Password Reset</span>
            </h3>
            <p className="text-xs text-slate-500">
              Set a temporary or new password for <strong className="text-slate-800">{resetModalUser.email}</strong>.
              All current active sessions will be terminated.
            </p>

            {resetMsg && (
              <div className="p-2.5 rounded bg-slate-100 text-xs text-slate-800 border border-slate-300">
                {resetMsg}
              </div>
            )}

            <div>
              <label className="block text-xs text-slate-600 font-medium mb-1">New Password (min 8 chars)</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setResetModalUser(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-900 rounded font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmResetPassword}
                disabled={newPassword.length < 8}
                className="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded disabled:opacity-50 shadow-xs"
              >
                Reset Password
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

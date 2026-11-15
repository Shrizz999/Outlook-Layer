import React, { useEffect, useState } from 'react';
import {
  Building2,
  UserCheck,
  AlertCircle,
  Clock,
  Shield,
  ArrowRight,
  UserX,
  History,
  CheckCircle2,
  XCircle,
  FileCheck,
  ArrowLeftRight,
  Plus,
  RefreshCw,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { DepartmentStats, Employee, HODDashboard, TaskHandover } from '../types';

export const DepartmentsView: React.FC = () => {
  const [stats, setStats] = useState<DepartmentStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDept, setSelectedDept] = useState<string | null>(null);
  const [hodDashboard, setHodDashboard] = useState<HODDashboard | null>(null);
  const [handovers, setHandovers] = useState<TaskHandover[]>([]);
  const [deptEmployees, setDeptEmployees] = useState<Employee[]>([]);

  // Assign HOD Modal
  const [assignModalDept, setAssignModalDept] = useState<string | null>(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>('');
  const [assignNotes, setAssignNotes] = useState<string>('');
  const [submittingHOD, setSubmittingHOD] = useState(false);

  // New Handover Modal
  const [showHandoverModal, setShowHandoverModal] = useState(false);
  const [handoverData, setHandoverData] = useState({
    task_id: '',
    from_employee_id: '',
    to_employee_id: '',
    from_department: '',
    to_department: 'Production',
    notes: '',
  });

  // Physical Verification Modal
  const [showVerificationModal, setShowVerificationModal] = useState(false);
  const [verificationData, setVerificationData] = useState({
    task_id: '',
    verification_type: 'QUALITY_INSPECTION',
    verified_by_employee_id: '',
    physical_location: 'Plant Floor Line 1',
    result: 'PASS' as 'PASS' | 'FAIL' | 'CONDITIONAL',
    notes: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await api.listDepartmentStats();
      setStats(data);
    } catch (err: any) {
      console.error('Failed to load department stats:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openHODDashboard = async (department: string) => {
    setSelectedDept(department);
    try {
      const [dash, ho, emps] = await Promise.all([
        api.getHODDashboard(department),
        api.listHandovers(department),
        api.listEmployees(department),
      ]);
      setHodDashboard(dash);
      setHandovers(ho);
      setDeptEmployees(emps);
    } catch (err: any) {
      alert(`Failed to load HOD dashboard: ${err.message}`);
    }
  };

  const handleAssignHOD = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignModalDept || !selectedEmployeeId) return;
    setSubmittingHOD(true);
    try {
      await api.assignDepartmentHOD({
        department: assignModalDept,
        employee_id: selectedEmployeeId,
        notes: assignNotes,
      });
      setAssignModalDept(null);
      setSelectedEmployeeId('');
      setAssignNotes('');
      await loadData();
      if (selectedDept) {
        await openHODDashboard(selectedDept);
      }
    } catch (err: any) {
      alert(`HOD Assignment Error: ${err.message}`);
    } finally {
      setSubmittingHOD(false);
    }
  };

  const handleRemoveHOD = async (department: string) => {
    if (!confirm(`Are you sure you want to remove the HOD for ${department}?`)) return;
    try {
      await api.removeDepartmentHOD(department);
      await loadData();
      if (selectedDept === department) {
        await openHODDashboard(department);
      }
    } catch (err: any) {
      alert(`Failed to remove HOD: ${err.message}`);
    }
  };

  const handleHandoverAction = async (id: string, action: 'ACCEPT' | 'REJECT') => {
    try {
      await api.actionHandover(id, action);
      if (selectedDept) {
        const ho = await api.listHandovers(selectedDept);
        setHandovers(ho);
      }
    } catch (err: any) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const handleCreateHandover = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createHandover({
        ...handoverData,
        checklist_items: [
          { item: 'Engineering drawing & BOM verified', completed: true },
          { item: 'Material allocation confirmed', completed: true },
        ],
      });
      setShowHandoverModal(false);
      if (selectedDept) {
        const ho = await api.listHandovers(selectedDept);
        setHandovers(ho);
      }
    } catch (err: any) {
      alert(`Failed to create handover: ${err.message}`);
    }
  };

  const handleCreateVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createPhysicalVerification(verificationData);
      setShowVerificationModal(false);
      alert('Physical operational verification logged successfully.');
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
            <Building2 className="w-6 h-6 text-blue-600" />
            <span>Departments & HOD Management</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Configure department leadership, enforce single active HOD policies, and coordinate inter-department handovers.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {selectedDept && (
            <button
              onClick={() => setSelectedDept(null)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
            >
              ← Back to All Departments
            </button>
          )}
          <button
            onClick={loadData}
            className="p-2 border border-slate-200 rounded-lg bg-white text-slate-600 hover:text-slate-900 shadow-xs"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* DEPARTMENT CARDS GRID (When not inside a specific HOD view) */}
      {!selectedDept ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((dept) => {
            const hasHod = dept.hod_name && dept.hod_name !== 'HOD NOT ASSIGNED';
            return (
              <div
                key={dept.department}
                className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col justify-between hover:border-slate-300 transition"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{dept.department}</h3>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {dept.total_employees} staff members
                      </div>
                    </div>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${
                        hasHod
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {hasHod ? 'HOD Assigned' : 'HOD NOT ASSIGNED'}
                    </span>
                  </div>

                  {/* Current HOD Info */}
                  <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <div className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                      Department Head (HOD)
                    </div>
                    {hasHod ? (
                      <div className="mt-1 flex items-center justify-between">
                        <div>
                          <div className="text-xs font-bold text-slate-800">{dept.hod_name}</div>
                          {dept.hod_email && (
                            <div className="text-[11px] text-slate-500">{dept.hod_email}</div>
                          )}
                        </div>
                        <button
                          onClick={() => handleRemoveHOD(dept.department)}
                          className="text-[10px] text-rose-600 hover:text-rose-800 font-semibold"
                        >
                          Remove
                        </button>
                      </div>
                    ) : (
                      <div className="mt-1 text-xs font-semibold text-amber-600 flex items-center space-x-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        <span>HOD NOT ASSIGNED</span>
                      </div>
                    )}
                  </div>

                  {/* Operational Metrics */}
                  <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                    <div className="p-2 bg-slate-50 rounded-lg">
                      <div className="text-[10px] font-semibold text-slate-400">Active Tasks</div>
                      <div className="text-sm font-bold text-slate-800 mt-0.5">
                        {dept.active_tasks}
                      </div>
                    </div>
                    <div className="p-2 bg-slate-50 rounded-lg">
                      <div className="text-[10px] font-semibold text-slate-400">Overdue</div>
                      <div
                        className={`text-sm font-bold mt-0.5 ${
                          dept.overdue_tasks > 0 ? 'text-rose-600' : 'text-slate-800'
                        }`}
                      >
                        {dept.overdue_tasks}
                      </div>
                    </div>
                    <div className="p-2 bg-slate-50 rounded-lg">
                      <div className="text-[10px] font-semibold text-slate-400">Proposals</div>
                      <div className="text-sm font-bold text-blue-600 mt-0.5">
                        {dept.pending_proposals}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between gap-2">
                  <button
                    onClick={async () => {
                      setAssignModalDept(dept.department);
                      const emps = await api.listEmployees(dept.department);
                      setDeptEmployees(emps);
                    }}
                    className="flex-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
                  >
                    {hasHod ? 'Change HOD' : 'Assign HOD'}
                  </button>
                  <button
                    onClick={() => openHODDashboard(dept.department)}
                    className="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition flex items-center justify-center space-x-1"
                  >
                    <span>HOD View</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* HOD DEDICATED VIEW */
        <div className="space-y-6">
          {/* HOD Header Banner */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 uppercase tracking-wider">
                  HOD Operations Dashboard
                </span>
                <span className="text-xs text-slate-400">/</span>
                <span className="text-xs font-bold text-slate-800">{selectedDept}</span>
              </div>
              <h2 className="text-lg font-bold text-slate-900 mt-1">
                {hodDashboard?.hod.name || 'HOD NOT ASSIGNED'}
              </h2>
              <div className="text-xs text-slate-500">
                {hodDashboard?.hod.email || 'No designated HOD profile found'}
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => {
                  setHandoverData({
                    task_id: '',
                    from_employee_id: hodDashboard?.employees[0]?.id || '',
                    to_employee_id: '',
                    from_department: selectedDept,
                    to_department: 'Production',
                    notes: '',
                  });
                  setShowHandoverModal(true);
                }}
                className="flex items-center space-x-1.5 px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs"
              >
                <ArrowLeftRight className="w-4 h-4" />
                <span>Initiate Handover</span>
              </button>

              <button
                onClick={() => {
                  setVerificationData({
                    task_id: '',
                    verification_type: selectedDept === 'Quality' ? 'QA_INSPECTION' : 'DISPATCH_VERIFICATION',
                    verified_by_employee_id: hodDashboard?.hod.employee_id || '',
                    physical_location: 'Shop Floor Station A',
                    result: 'PASS',
                    notes: '',
                  });
                  setShowVerificationModal(true);
                }}
                className="flex items-center space-x-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs"
              >
                <FileCheck className="w-4 h-4" />
                <span>Log Physical Verification</span>
              </button>
            </div>
          </div>

          {/* Department Staff & Department Tasks */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Department Staff Table */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
              <h3 className="text-xs font-bold uppercase text-slate-500 tracking-wider mb-3">
                Department Roster ({hodDashboard?.employees.length || 0})
              </h3>
              <div className="divide-y divide-slate-100 max-h-[300px] overflow-y-auto">
                {hodDashboard?.employees.map((emp) => (
                  <div key={emp.id} className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-slate-900">{emp.name}</div>
                      <div className="text-[11px] text-slate-500">{emp.designation || emp.role}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold text-slate-800">
                        {emp.workload_stats?.total_assigned || 0} tasks
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {emp.workload_stats?.overdue || 0} overdue
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Inter-Department Handoffs */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
              <h3 className="text-xs font-bold uppercase text-slate-500 tracking-wider mb-3">
                Inter-Department Handovers ({handovers.length})
              </h3>
              {handovers.length === 0 ? (
                <div className="text-xs text-slate-400 text-center py-8">
                  No active handovers for this department.
                </div>
              ) : (
                <div className="divide-y divide-slate-100 max-h-[300px] overflow-y-auto">
                  {handovers.map((h) => (
                    <div key={h.id} className="py-2.5 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-800">Task {h.task_id}</span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            h.status === 'ACCEPTED'
                              ? 'bg-emerald-50 text-emerald-700'
                              : h.status === 'REJECTED'
                              ? 'bg-rose-50 text-rose-700'
                              : 'bg-amber-50 text-amber-700'
                          }`}
                        >
                          {h.status}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {h.from_department} → {h.to_department}
                      </div>
                      {h.notes && <div className="text-[11px] text-slate-600 italic">"{h.notes}"</div>}
                      {h.status === 'PENDING' && (
                        <div className="flex items-center space-x-2 pt-1">
                          <button
                            onClick={() => handleHandoverAction(h.id, 'ACCEPT')}
                            className="px-2 py-0.5 bg-emerald-600 text-white text-[10px] font-semibold rounded"
                          >
                            Accept Handover
                          </button>
                          <button
                            onClick={() => handleHandoverAction(h.id, 'REJECT')}
                            className="px-2 py-0.5 bg-rose-600 text-white text-[10px] font-semibold rounded"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ASSIGN HOD MODAL */}
      {assignModalDept && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-800">
                Assign Head of Department: {assignModalDept}
              </h2>
              <button
                onClick={() => setAssignModalDept(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAssignHOD} className="mt-4 space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Select Employee from {assignModalDept} *
                </label>
                <select
                  required
                  value={selectedEmployeeId}
                  onChange={(e) => setSelectedEmployeeId(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                >
                  <option value="">-- Choose active employee --</option>
                  {deptEmployees
                    .filter((e) => e.active)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name} ({e.designation || e.role})
                      </option>
                    ))}
                </select>
                <p className="text-[10px] text-slate-400 mt-1">
                  Enforces rule: HOD must belong to {assignModalDept} and be active.
                </p>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Assignment Notes / Reason
                </label>
                <textarea
                  rows={2}
                  value={assignNotes}
                  onChange={(e) => setAssignNotes(e.target.value)}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                  placeholder="e.g. Appointed as Department Head for Q4"
                />
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setAssignModalDept(null)}
                  className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg text-slate-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingHOD}
                  className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-xs"
                >
                  {submittingHOD ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE HANDOVER MODAL */}
      {showHandoverModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-800">Initiate Department Handover</h2>
              <button
                onClick={() => setShowHandoverModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateHandover} className="mt-4 space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Operational Task ID *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. TASK-00101"
                  value={handoverData.task_id}
                  onChange={(e) => setHandoverData({ ...handoverData, task_id: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    From Department
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={handoverData.from_department}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-slate-50 text-slate-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    To Department *
                  </label>
                  <select
                    value={handoverData.to_department}
                    onChange={(e) => setHandoverData({ ...handoverData, to_department: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  >
                    <option value="Production">Production</option>
                    <option value="Quality">Quality</option>
                    <option value="Stores">Stores</option>
                    <option value="Dispatch">Dispatch</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Notes</label>
                <textarea
                  rows={2}
                  value={handoverData.notes}
                  onChange={(e) => setHandoverData({ ...handoverData, notes: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                  placeholder="Drawing approved and ready for shop floor machining"
                />
              </div>
              <div className="pt-2 flex items-center justify-end space-x-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowHandoverModal(false)}
                  className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 text-xs bg-indigo-600 text-white font-semibold rounded-lg"
                >
                  Submit Handover
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* PHYSICAL VERIFICATION MODAL */}
      {showVerificationModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-800">
                Log Physical Operational Verification
              </h2>
              <button
                onClick={() => setShowVerificationModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateVerification} className="mt-4 space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Task ID *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. TASK-00105"
                  value={verificationData.task_id}
                  onChange={(e) =>
                    setVerificationData({ ...verificationData, task_id: e.target.value })
                  }
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Inspection Result *
                  </label>
                  <select
                    value={verificationData.result}
                    onChange={(e) =>
                      setVerificationData({
                        ...verificationData,
                        result: e.target.value as any,
                      })
                    }
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  >
                    <option value="PASS">PASS (Verified)</option>
                    <option value="FAIL">FAIL (Defect Detected)</option>
                    <option value="CONDITIONAL">CONDITIONAL (Rework Required)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Physical Location
                  </label>
                  <input
                    type="text"
                    value={verificationData.physical_location}
                    onChange={(e) =>
                      setVerificationData({
                        ...verificationData,
                        physical_location: e.target.value,
                      })
                    }
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">Notes</label>
                <textarea
                  rows={2}
                  value={verificationData.notes}
                  onChange={(e) =>
                    setVerificationData({ ...verificationData, notes: e.target.value })
                  }
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                  placeholder="Inspected batch dimensions with digital vernier caliper: within 0.02mm tolerance."
                />
              </div>
              <div className="pt-2 flex items-center justify-end space-x-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowVerificationModal(false)}
                  className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 text-xs bg-emerald-600 text-white font-semibold rounded-lg"
                >
                  Confirm Physical Verification
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

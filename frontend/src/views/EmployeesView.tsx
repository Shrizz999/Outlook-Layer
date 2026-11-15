import React, { useEffect, useState } from 'react';
import {
  Users,
  UserPlus,
  Search,
  Filter,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Briefcase,
  Mail,
  Phone,
  Shield,
  Edit2,
  RefreshCw,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { BIRole, Employee } from '../types';

export const EmployeesView: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    department: 'Engineering',
    designation: '',
    phone_number: '',
    employee_number: '',
    role: 'EMPLOYEE' as BIRole,
    active: true,
  });
  const [submitting, setSubmitting] = useState(false);

  const loadEmployees = async () => {
    setLoading(true);
    try {
      const data = await api.listEmployees(selectedDept === 'ALL' ? undefined : selectedDept);
      setEmployees(data);
    } catch (err: any) {
      console.error('Failed to load employees:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEmployees();
  }, [selectedDept]);

  const filteredEmployees = employees.filter((emp) => {
    const q = searchQuery.toLowerCase();
    const matchQuery =
      emp.name.toLowerCase().includes(q) ||
      emp.email.toLowerCase().includes(q) ||
      (emp.designation && emp.designation.toLowerCase().includes(q)) ||
      (emp.employee_number && emp.employee_number.toLowerCase().includes(q));
    return matchQuery;
  });

  const handleSaveEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (editingEmployee) {
        await api.updateEmployee(editingEmployee.id, formData);
      } else {
        await api.createEmployee(formData);
      }
      setShowAddModal(false);
      setEditingEmployee(null);
      resetForm();
      loadEmployees();
    } catch (err: any) {
      alert(`Operation failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      email: '',
      department: 'Engineering',
      designation: '',
      phone_number: '',
      employee_number: '',
      role: 'EMPLOYEE',
      active: true,
    });
  };

  const handleToggleActive = async (emp: Employee) => {
    try {
      await api.updateEmployee(emp.id, { active: !emp.active });
      loadEmployees();
    } catch (err: any) {
      alert(`Failed to update status: ${err.message}`);
    }
  };

  const openEditModal = (emp: Employee) => {
    setEditingEmployee(emp);
    setFormData({
      name: emp.name,
      email: emp.email,
      department: emp.department,
      designation: emp.designation || '',
      phone_number: emp.phone_number || '',
      employee_number: emp.employee_number || '',
      role: emp.role,
      active: emp.active,
    });
    setShowAddModal(true);
  };

  const departmentsList = [
    'ALL',
    'Engineering',
    'Purchase',
    'Stores',
    'Production',
    'Quality',
    'Dispatch',
    'Sales',
  ];

  // Overall statistics
  const totalEmployees = employees.length;
  const activeEmployees = employees.filter((e) => e.active).length;
  const totalAssignedTasks = employees.reduce(
    (acc, e) => acc + (e.workload_stats?.total_assigned || 0),
    0
  );
  const overdueTasks = employees.reduce(
    (acc, e) => acc + (e.workload_stats?.overdue || 0),
    0
  );

  return (
    <div className="space-y-6">
      {/* Top Banner & KPI Cards */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center space-x-2">
            <Users className="w-6 h-6 text-blue-600" />
            <span>Employee Management & Workload</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage organizational roster, departmental assignments, and monitor real-time task allocations.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              resetForm();
              setEditingEmployee(null);
              setShowAddModal(true);
            }}
            className="flex items-center space-x-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
          >
            <UserPlus className="w-4 h-4" />
            <span>Add Employee</span>
          </button>
          <button
            onClick={loadEmployees}
            className="p-2 border border-slate-200 rounded-lg bg-white text-slate-600 hover:text-slate-900 shadow-xs transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Total Staff
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{totalEmployees}</div>
          <div className="text-[11px] text-emerald-600 mt-1 font-medium">
            {activeEmployees} active / {totalEmployees - activeEmployees} inactive
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Active Allocations
          </div>
          <div className="text-2xl font-bold text-blue-600 mt-1">{totalAssignedTasks}</div>
          <div className="text-[11px] text-slate-500 mt-1">Operational tasks tracked</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Overdue Tasks
          </div>
          <div className="text-2xl font-bold text-rose-600 mt-1">{overdueTasks}</div>
          <div className="text-[11px] text-rose-500 mt-1">Requires supervisor follow-up</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Departments Covered
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {new Set(employees.map((e) => e.department)).size}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Across operational functions</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-700">Department:</span>
          <div className="flex flex-wrap gap-1.5">
            {departmentsList.map((dept) => (
              <button
                key={dept}
                onClick={() => setSelectedDept(dept)}
                className={`px-2.5 py-1 text-xs rounded-md font-medium transition ${
                  selectedDept === dept
                    ? 'bg-blue-600 text-white font-semibold'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {dept}
              </button>
            ))}
          </div>
        </div>

        <div className="relative min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search employee, email, role..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-500">Loading employees...</div>
        ) : filteredEmployees.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">No employees match your search.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="px-4 py-3">Employee</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Designation / Role</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Workload (Tasks)</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredEmployees.map((emp) => {
                  const ws = emp.workload_stats;
                  return (
                    <tr
                      key={emp.id}
                      className="hover:bg-slate-50/80 transition cursor-pointer"
                      onClick={() => setSelectedEmployee(emp)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{emp.name}</div>
                        <div className="text-[11px] text-slate-400">
                          {emp.employee_number || emp.id.substring(0, 8)}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                          {emp.department}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">{emp.designation || 'Staff'}</div>
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">{emp.role}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center space-x-1 text-[11px] text-slate-600">
                          <Mail className="w-3 h-3 text-slate-400" />
                          <span>{emp.email}</span>
                        </div>
                        {emp.phone_number && (
                          <div className="flex items-center space-x-1 text-[11px] text-slate-400 mt-0.5">
                            <Phone className="w-3 h-3 text-slate-400" />
                            <span>{emp.phone_number}</span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            emp.active
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {emp.active ? (
                            <>
                              <CheckCircle className="w-3 h-3" />
                              <span>Active</span>
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3" />
                              <span>Inactive</span>
                            </>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {ws ? (
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-slate-800">{ws.total_assigned}</span>
                            <span className="text-[10px] text-slate-400">
                              ({ws.in_progress} active,{' '}
                              <span className={ws.overdue > 0 ? 'text-rose-600 font-bold' : ''}>
                                {ws.overdue} overdue
                              </span>
                              )
                            </span>
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-400">0 tasks</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div
                          className="flex items-center justify-end space-x-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            onClick={() => openEditModal(emp)}
                            className="p-1 hover:bg-slate-200 rounded text-slate-600 transition"
                            title="Edit Employee"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleToggleActive(emp)}
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold transition ${
                              emp.active
                                ? 'text-rose-600 hover:bg-rose-50'
                                : 'text-emerald-600 hover:bg-emerald-50'
                            }`}
                          >
                            {emp.active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add / Edit Employee Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-sm font-bold text-slate-800">
                {editingEmployee ? 'Edit Employee Details' : 'Create New Employee'}
              </h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveEmployee} className="mt-4 space-y-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  placeholder="e.g. Ramesh Verma"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Work Email *
                  </label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    placeholder="ramesh@balbird.invalid"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Employee Number
                  </label>
                  <input
                    type="text"
                    value={formData.employee_number}
                    onChange={(e) => setFormData({ ...formData, employee_number: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    placeholder="EMP-1024"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Department *
                  </label>
                  <select
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  >
                    {departmentsList
                      .filter((d) => d !== 'ALL')
                      .map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Designation
                  </label>
                  <input
                    type="text"
                    value={formData.designation}
                    onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                    placeholder="Senior QA Engineer"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">Role</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as BIRole })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg bg-white"
                  >
                    <option value="EMPLOYEE">Employee</option>
                    <option value="TEAM_LEADER">Team Leader</option>
                    <option value="DEPT_HEAD">Dept Head</option>
                    <option value="MANAGEMENT">Management</option>
                    <option value="SYSADMIN">Sysadmin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    value={formData.phone_number}
                    onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg"
                    placeholder="+91-98765-43210"
                  />
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between border-t border-slate-100">
                <label className="flex items-center space-x-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.active}
                    onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                    className="rounded border-slate-300 text-blue-600"
                  />
                  <span>Account Active</span>
                </label>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowAddModal(false)}
                    className="px-3 py-1.5 text-xs border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow-xs"
                  >
                    {submitting ? 'Saving...' : editingEmployee ? 'Update' : 'Create'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState } from 'react';
import { CheckSquare, Sparkles, UserPlus, Clock, ArrowRight, ShieldCheck, Check, Filter } from 'lucide-react';
import { LegacyTask, TaskProposal } from '../types';
import { api } from '../api/client';

interface TasksViewProps {
  tasks: LegacyTask[];
  proposals: TaskProposal[];
  onRefresh: () => void;
  currentRole?: string;
}

export const TasksView: React.FC<TasksViewProps> = ({ tasks, proposals, onRefresh, currentRole = 'MANAGEMENT' }) => {
  const [activeTab, setActiveTab] = useState<'proposals' | 'operational'>('proposals');
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [assignedName, setAssignedName] = useState('John Sales');

  const canApprove = ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'].includes(currentRole);

  const handleApprove = async (propId: string) => {
    setApprovingId(propId);
    try {
      await api.approveProposal(propId, {
        assigned_to_name: assignedName,
        deadline: '2026-11-20',
      });
      onRefresh();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setApprovingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Tab Controls */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Task Intelligence & Coordination</h2>
          <p className="text-xs text-slate-500">
            AI-extracted task proposals require human approval before insertion into operational Task Orch records.
          </p>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => setActiveTab('proposals')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition flex items-center space-x-1.5 ${
              activeTab === 'proposals'
                ? 'bg-white text-blue-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Proposals ({proposals.filter((p) => p.proposal_status === 'PENDING').length})</span>
          </button>
          <button
            onClick={() => setActiveTab('operational')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition flex items-center space-x-1.5 ${
              activeTab === 'operational'
                ? 'bg-white text-blue-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>Operational Tasks ({tasks.length})</span>
          </button>
        </div>
      </div>

      {/* Tab 1: Proposals Awaiting Human Review */}
      {activeTab === 'proposals' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Review candidate actions extracted from correspondence before operational activation.</span>
            <div className="flex items-center space-x-2">
              <span className="font-medium text-slate-700">Assign Approved Tasks To:</span>
              <select
                value={assignedName}
                onChange={(e) => setAssignedName(e.target.value)}
                className="bg-white border border-slate-300 rounded px-2 py-1 text-slate-800 font-semibold"
              >
                <option value="John Sales">John Sales (Sales)</option>
                <option value="Alice Purchase">Alice Purchase (Procurement)</option>
                <option value="Bob PPC">Bob PPC (Planning)</option>
                <option value="Carol Production">Carol Production (Mfg)</option>
                <option value="David Quality">David Quality (QC)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {proposals.length === 0 ? (
              <div className="col-span-2 p-12 text-center text-xs text-slate-400 bg-white border border-slate-200 rounded-xl">
                No pending task proposals. Run AI analysis on incoming messages to generate proposals.
              </div>
            ) : (
              proposals.map((prop) => {
                const isPending = prop.proposal_status === 'PENDING';
                return (
                  <div
                    key={prop.id}
                    className={`bg-white border rounded-xl p-5 space-y-3.5 shadow-xs transition ${
                      isPending ? 'border-blue-200 hover:border-blue-300' : 'border-slate-200 opacity-75'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">
                            {prop.task_type || 'TASK'}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              prop.priority === 'HIGH' || prop.priority === 'CRITICAL'
                                ? 'bg-rose-50 text-rose-700'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {prop.priority}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">{prop.title}</h4>
                      </div>

                      {prop.proposal_status === 'APPROVED' ? (
                        <span className="flex items-center text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
                          <Check className="w-3 h-3 mr-1" />
                          Approved ({prop.approved_task_id})
                        </span>
                      ) : canApprove ? (
                        <button
                          onClick={() => handleApprove(prop.id)}
                          disabled={approvingId === prop.id}
                          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center space-x-1 transition shadow-xs"
                        >
                          <UserPlus className="w-3.5 h-3.5" />
                          <span>{approvingId === prop.id ? 'Approving...' : 'Approve & Assign'}</span>
                        </button>
                      ) : (
                        <span className="text-[10px] font-semibold text-slate-400 bg-slate-100 px-2 py-1 rounded-md border border-slate-200">
                          Awaiting Manager Approval
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">{prop.description}</p>

                    {/* Metadata pill row */}
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 pt-2 border-t border-slate-100">
                      <span>
                        Dept: <strong>{prop.suggested_department || 'Unassigned'}</strong>
                      </span>
                      {prop.due_date && (
                        <span>
                          Due: <strong>{prop.due_date}</strong>
                        </span>
                      )}
                      <span>
                        Confidence: <strong>{Math.round((prop.confidence || 0) * 100)}%</strong>
                      </span>
                    </div>

                    {prop.action_evidence && (
                      <div className="text-[10px] bg-slate-50 p-2 rounded text-slate-500 font-mono italic">
                        Evidence: "{prop.action_evidence}"
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Operational Tasks Table (Legacy tasks table) */}
      {activeTab === 'operational' && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
          <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Operational Task Queue (Supabase `tasks` Table)
              </h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">Primary Key: task_id (TEXT)</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold text-[10px] bg-slate-50/50">
                  <th className="py-2.5 px-3">Task ID</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">Assignee</th>
                  <th className="py-2.5 px-3">Department</th>
                  <th className="py-2.5 px-3">Deadline</th>
                  <th className="py-2.5 px-3">Priority</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {tasks.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      No operational tasks in database.
                    </td>
                  </tr>
                ) : (
                  tasks.map((t) => (
                    <tr key={t.task_id} className="hover:bg-slate-50 transition">
                      <td className="py-3 px-3 font-mono font-bold text-blue-600">{t.task_id}</td>
                      <td className="py-3 px-3 font-medium text-slate-800 max-w-xs truncate">{t.description}</td>
                      <td className="py-3 px-3 text-slate-700 font-semibold">{t.assigned_to || 'Unassigned'}</td>
                      <td className="py-3 px-3 text-slate-500">{t.department || 'General'}</td>
                      <td className="py-3 px-3 text-slate-500 font-mono">{t.deadline || '—'}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            t.priority === 'HIGH' || t.priority === 'CRITICAL'
                              ? 'bg-rose-50 text-rose-700'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {t.priority || 'NORMAL'}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            t.status === 'blocked'
                              ? 'bg-purple-50 text-purple-700'
                              : t.status === 'in_progress'
                              ? 'bg-blue-50 text-blue-700'
                              : t.status === 'completed'
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {t.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

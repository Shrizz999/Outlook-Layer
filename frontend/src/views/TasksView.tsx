import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  Sparkles,
  UserPlus,
  Clock,
  ArrowRight,
  ShieldCheck,
  Check,
  Filter,
  AlertTriangle,
  Lock,
  PlayCircle,
  ChevronRight,
  RefreshCw,
  GitFork,
  Layers,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { LegacyTask, TaskProposal } from '../types';
import { api } from '../api/client';

interface TasksViewProps {
  tasks: LegacyTask[];
  proposals: TaskProposal[];
  onRefresh: () => void;
  currentRole?: string;
}

export const TasksView: React.FC<TasksViewProps> = ({ tasks, proposals, onRefresh, currentRole = 'MANAGEMENT' }) => {
  const [activeTab, setActiveTab] = useState<'traceability' | 'operational' | 'proposals'>('traceability');
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [assignedName, setAssignedName] = useState('Swapnali');

  // Traceability & Bottleneck state
  const [bottlenecks, setBottlenecks] = useState<any[]>([]);
  const [cases, setCases] = useState<any[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [traceability, setTraceability] = useState<any | null>(null);
  const [loadingTrace, setLoadingTrace] = useState(false);

  const canApprove = ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'].includes(currentRole);

  const loadBottlenecksAndCases = async () => {
    try {
      const [bList, cList] = await Promise.all([
        api.getBottlenecks(),
        api.listCases(),
      ]);
      setBottlenecks(bList);
      setCases(cList);
      if (cList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(cList[0].id);
      }
    } catch (e) {
      console.error('Failed to load bottlenecks/cases', e);
    }
  };

  useEffect(() => {
    loadBottlenecksAndCases();
  }, [tasks]);

  useEffect(() => {
    if (!selectedCaseId) return;
    setLoadingTrace(true);
    api.getCaseTraceability(selectedCaseId)
      .then((res) => setTraceability(res))
      .catch((e) => console.error('Failed to load traceability', e))
      .finally(() => setLoadingTrace(false));
  }, [selectedCaseId]);

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
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-200 pb-4 gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
            <span>Task Intelligence & Manufacturing Coordination</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
              13-Stage Workflow
            </span>
          </h2>
          <p className="text-xs text-slate-500">
            Autonomous multi-department dependency orchestration, active bottleneck detection, and line-item traceability.
          </p>
        </div>

        <div className="flex bg-slate-100 p-1 rounded-lg self-start md:self-auto">
          <button
            onClick={() => setActiveTab('traceability')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition flex items-center space-x-1.5 ${
              activeTab === 'traceability'
                ? 'bg-white text-blue-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <GitFork className="w-3.5 h-3.5" />
            <span>Workflow & Bottlenecks ({bottlenecks.length})</span>
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
        </div>
      </div>

      {/* Tab 1: Workflow Traceability & Bottlenecks */}
      {activeTab === 'traceability' && (
        <div className="space-y-6">
          {/* Active Operational Bottlenecks Banner */}
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between pb-2 border-b border-amber-200/60 mb-3">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <h3 className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                  Active Departmental Bottlenecks ({bottlenecks.length})
                </h3>
              </div>
              <span className="text-[11px] text-amber-700 font-medium">
                Downstream manufacturing stages are currently blocked
              </span>
            </div>

            {bottlenecks.length === 0 ? (
              <div className="text-xs text-slate-500 py-3 text-center">
                No active bottlenecks. All workflows are progressing smoothly.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {bottlenecks.map((b, idx) => (
                  <div
                    key={idx}
                    className="bg-white border border-amber-200 rounded-lg p-3 space-y-2 shadow-2xs hover:border-amber-300 transition"
                  >
                    <div className="flex items-start justify-between">
                      <span className="text-[10px] font-mono font-bold text-amber-800 bg-amber-100 px-1.5 py-0.5 rounded">
                        {b.case_number || 'CASE'}
                      </span>
                      <span className="text-[10px] font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200 flex items-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse mr-1"></span>
                        HOLDING UP
                      </span>
                    </div>

                    <div>
                      <div className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                        <span className="text-blue-700 font-extrabold">{b.bottleneck_employee}</span>
                        <span className="text-slate-400 font-normal">({b.department})</span>
                      </div>
                      <p className="text-[11px] text-slate-600 line-clamp-2 mt-0.5">{b.title}</p>
                    </div>

                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
                      <span>Deadline: <strong className="font-mono text-slate-700">{b.deadline || '—'}</strong></span>
                      <span>Progress: <strong className="text-blue-600">{b.progress_percentage}%</strong></span>
                    </div>

                    <button
                      onClick={() => setSelectedCaseId(b.case_id)}
                      className="w-full mt-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 bg-blue-50/50 hover:bg-blue-50 py-1 rounded transition text-center"
                    >
                      View 13-Stage Traceability →
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Business Case Selector & Detailed Traceability */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <div className="p-4 border-b border-slate-200 bg-slate-50/70 flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                <Layers className="w-4 h-4 text-blue-600" />
                <div>
                  <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Manufacturing Order Traceability Timeline
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Track sequential handoffs from Customer Enquiry through Quality & Dispatch
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-xs font-medium text-slate-600">Select Order / Case:</span>
                <select
                  value={selectedCaseId}
                  onChange={(e) => setSelectedCaseId(e.target.value)}
                  className="bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-xs text-slate-800 font-semibold focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                >
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.case_number} — {c.title.slice(0, 35)}...
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {loadingTrace ? (
              <div className="p-12 text-center text-xs text-slate-400">Loading workflow traceability timeline...</div>
            ) : !traceability || traceability.timeline.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-400">
                No workflow tasks found for this case. Import test emails or trigger enquiry ingestion to auto-orchestrate.
              </div>
            ) : (
              <div className="p-6 space-y-6">
                {/* Progress Metric Bar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-700">Overall Order Progress</span>
                    <span className="font-bold font-mono text-blue-600">
                      {traceability.completed_tasks} / {traceability.total_tasks} Tasks Completed ({traceability.progress_percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
                      style={{ width: `${traceability.progress_percentage}%` }}
                    ></div>
                  </div>
                </div>

                {/* 13-Stage Timeline Cards */}
                <div className="relative border-l-2 border-slate-200 ml-4 space-y-4 pl-6">
                  {traceability.timeline.map((step: any, idx: number) => {
                    const isDone = step.is_completed || step.status === 'completed';
                    const isInProgress = step.status === 'in_progress';
                    const isPending = step.status === 'pending';

                    return (
                      <div key={step.task_id} className="relative group">
                        {/* Node bullet */}
                        <div
                          className={`absolute -left-[31px] top-1.5 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                            isDone
                              ? 'bg-emerald-500 border-white text-white shadow-2xs'
                              : isInProgress
                              ? 'bg-amber-500 border-white text-white shadow-2xs animate-pulse'
                              : 'bg-white border-slate-300 text-slate-400'
                          }`}
                        >
                          {isDone ? (
                            <Check className="w-3 h-3 stroke-[3]" />
                          ) : isInProgress ? (
                            <PlayCircle className="w-3 h-3" />
                          ) : (
                            <Lock className="w-2.5 h-2.5" />
                          )}
                        </div>

                        {/* Step Card */}
                        <div
                          className={`border rounded-xl p-4 transition shadow-2xs ${
                            isDone
                              ? 'bg-emerald-50/30 border-emerald-200'
                              : isInProgress
                              ? 'bg-amber-50/40 border-amber-300 ring-2 ring-amber-100'
                              : 'bg-white border-slate-200 opacity-80'
                          }`}
                        >
                          <div className="flex flex-col md:flex-row md:items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center space-x-2">
                                <span className="text-[10px] font-bold font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                                  Stage {idx + 1}/13
                                </span>
                                <span className="text-[10px] font-mono text-blue-600 font-semibold">{step.task_id}</span>
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                    isDone
                                      ? 'bg-emerald-100 text-emerald-800'
                                      : isInProgress
                                      ? 'bg-amber-100 text-amber-800'
                                      : 'bg-slate-100 text-slate-600'
                                  }`}
                                >
                                  {isDone ? 'COMPLETED' : isInProgress ? 'IN PROGRESS (BOTTLENECK)' : 'PENDING'}
                                </span>
                              </div>
                              <h4 className="text-xs font-bold text-slate-900 mt-1">{step.description}</h4>
                            </div>

                            <div className="flex items-center space-x-3 text-[11px] self-start md:self-auto">
                              <div className="text-right">
                                <div className="font-semibold text-slate-800">{step.assigned_to}</div>
                                <div className="text-[10px] text-slate-400">{step.department}</div>
                              </div>
                            </div>
                          </div>

                          <div className="mt-3 pt-2.5 border-t border-slate-100 flex flex-wrap items-center justify-between text-[11px] text-slate-500 gap-2">
                            <span>Assigned By: <strong className="text-slate-700">{step.assigned_by || 'System'}</strong></span>
                            {step.deadline && (
                              <span>Target Deadline: <strong className="font-mono text-slate-800">{step.deadline}</strong></span>
                            )}
                            {step.predecessor_task_id && (
                              <span className="text-[10px] text-slate-400 font-mono">
                                Predecessor: {step.predecessor_task_id} (FINISH_TO_START)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Operational Tasks Table */}
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
                              ? 'bg-amber-100 text-amber-800'
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

      {/* Tab 3: Proposals Awaiting Human Review */}
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
                <option value="Swapnali">Swapnali (Sales Ops)</option>
                <option value="Ganesh">Ganesh (Sales Ops / PO)</option>
                <option value="Vaibhav">Vaibhav (Order Booking)</option>
                <option value="Frank Engineering">Frank Engineering (Technical)</option>
                <option value="Alice Purchase">Alice Purchase (Procurement)</option>
                <option value="Bob PPC">Bob PPC (Planning)</option>
                <option value="Carol Production">Carol Production (Mfg)</option>
                <option value="David Quality">David Quality (QC)</option>
                <option value="Emma Dispatch">Emma Dispatch (Logistics)</option>
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
    </div>
  );
};

import React, { useState } from 'react';
import { Network, Ban, Plus, ArrowRight, ShieldAlert } from 'lucide-react';
import { LegacyTask, TaskDependency } from '../types';
import { api } from '../api/client';

interface DependenciesViewProps {
  dependencies: TaskDependency[];
  tasks: LegacyTask[];
  onRefresh: () => void;
}

export const DependenciesView: React.FC<DependenciesViewProps> = ({
  dependencies,
  tasks,
  onRefresh,
}) => {
  const [predTask, setPredTask] = useState(tasks[0]?.task_id || '');
  const [succTask, setSuccTask] = useState(tasks[1]?.task_id || '');
  const [reason, setReason] = useState('Downstream work requires prerequisite completion');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!predTask || !succTask) return;
    setIsSubmitting(true);
    try {
      await api.createDependency({
        predecessor_task_id: predTask,
        successor_task_id: succTask,
        reason,
      });
      onRefresh();
      alert('Dependency established successfully.');
    } catch (err: any) {
      alert(`Dependency rejected: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Task Dependency & Blocker Graph</h2>
          <p className="text-xs text-slate-500">
            Sequencing logic and downstream blocker tracking. Circular dependencies are strictly rejected by the backend.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Create Dependency Form */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-900 flex items-center">
            <Plus className="w-4 h-4 mr-1.5 text-blue-600" />
            Link Task Dependency
          </h3>

          <form onSubmit={handleCreate} className="space-y-3.5 text-xs">
            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Predecessor (Prerequisite Work)</label>
              <select
                value={predTask}
                onChange={(e) => setPredTask(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 font-mono text-slate-800"
              >
                {tasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>
                    {t.task_id} - {(t.description || '').slice(0, 35)}...
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Successor (Blocked Work)</label>
              <select
                value={succTask}
                onChange={(e) => setSuccTask(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 font-mono text-slate-800"
              >
                {tasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>
                    {t.task_id} - {(t.description || '').slice(0, 35)}...
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Justification / Reason</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg p-2 text-slate-800"
              />
            </div>

            <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-[11px] text-amber-800 flex items-start space-x-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <span>Cycle detection enabled: Attempting to link circular tasks will fail.</span>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2 rounded-lg transition"
            >
              {isSubmitting ? 'Evaluating Cycle Graph...' : 'Create Dependency'}
            </button>
          </form>
        </div>

        {/* Right Column: Existing Dependency Network */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 flex items-center">
              <Network className="w-4 h-4 mr-2 text-blue-600" />
              Active Dependencies ({dependencies.length})
            </h3>
            <span className="text-[11px] text-slate-400">Directed Relationships</span>
          </div>

          <div className="space-y-3">
            {dependencies.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">No dependencies configured yet.</p>
            ) : (
              dependencies.map((dep) => (
                <div
                  key={dep.id}
                  className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 hover:border-slate-300 transition"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono font-bold text-xs bg-white border border-slate-200 px-2 py-0.5 rounded text-blue-700">
                        {dep.predecessor_task_id}
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-400" />
                      <span className="font-mono font-bold text-xs bg-white border border-slate-200 px-2 py-0.5 rounded text-purple-700">
                        {dep.successor_task_id}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      {dep.is_blocking && (
                        <span className="text-[10px] font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200 flex items-center">
                          <Ban className="w-3 h-3 mr-1" />
                          Blocks Execution
                        </span>
                      )}
                      <span className="text-[10px] font-bold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                        {dep.dependency_type}
                      </span>
                    </div>
                  </div>

                  {dep.reason && (
                    <p className="text-xs text-slate-600 pt-1">
                      <strong className="text-slate-700">Constraint:</strong> {dep.reason}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import {
  Briefcase,
  Mail,
  CheckSquare,
  AlertTriangle,
  Clock,
  Ban,
  ArrowUpRight,
  TrendingUp,
} from 'lucide-react';
import { DashboardSummary } from '../types';

interface OverviewViewProps {
  summary: DashboardSummary | null;
  onNavigate: (tab: any) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ summary, onNavigate }) => {
  if (!summary) {
    return (
      <div className="p-8 text-center text-slate-500 text-sm">
        Loading dashboard metrics...
      </div>
    );
  }

  const { metrics, department_workload, recent_alerts, recent_cases } = summary;

  const statCards = [
    {
      label: 'Open Business Cases',
      value: metrics.open_cases_count,
      icon: Briefcase,
      color: 'text-blue-600 bg-blue-50 border-blue-200',
      action: () => onNavigate('cases'),
    },
    {
      label: 'Pending Email Reviews',
      value: metrics.pending_emails_count,
      icon: Mail,
      color: 'text-amber-600 bg-amber-50 border-amber-200',
      action: () => onNavigate('inbox'),
    },
    {
      label: 'Active Tasks',
      value: metrics.active_tasks_count,
      icon: CheckSquare,
      color: 'text-emerald-600 bg-emerald-50 border-emerald-200',
      action: () => onNavigate('tasks'),
    },
    {
      label: 'Overdue Activities',
      value: metrics.overdue_tasks_count,
      icon: Clock,
      color: 'text-rose-600 bg-rose-50 border-rose-200',
      action: () => onNavigate('tasks'),
    },
    {
      label: 'Blocked Work',
      value: metrics.blocked_tasks_count,
      icon: Ban,
      color: 'text-purple-600 bg-purple-50 border-purple-200',
      action: () => onNavigate('dependencies'),
    },
    {
      label: 'Active Risk Alerts',
      value: metrics.open_alerts_count,
      icon: AlertTriangle,
      color: 'text-orange-600 bg-orange-50 border-orange-200',
      action: () => onNavigate('orders'),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-sm flex items-center justify-between">
        <div className="space-y-1">
          <h2 className="text-xl font-bold tracking-tight">Operational Coordination Overview</h2>
          <p className="text-xs text-slate-300">
            Real-time synchronization between incoming Outlook correspondence, Sales Orders, and operational tasks.
          </p>
        </div>
        <button
          onClick={() => onNavigate('inbox')}
          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center space-x-1.5 transition shadow-sm"
        >
          <span>Review New Emails</span>
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {statCards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div
              key={i}
              onClick={card.action}
              className="bg-white border border-slate-200 p-4 rounded-xl shadow-xs hover:border-slate-300 transition cursor-pointer flex flex-col justify-between"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium text-slate-500 leading-tight">
                  {card.label}
                </span>
                <div className={`p-1.5 rounded-lg border ${card.color}`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
              </div>
              <div className="text-2xl font-bold text-slate-900">{card.value}</div>
            </div>
          );
        })}
      </div>

      {/* Middle Section: Department Workload & High-Priority Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Department Workload */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center">
              <TrendingUp className="w-4 h-4 mr-2 text-blue-600" />
              Department Workload
            </h3>
            <span className="text-[11px] text-slate-400">Active Tasks</span>
          </div>
          <div className="space-y-3">
            {Object.entries(department_workload).length === 0 ? (
              <p className="text-xs text-slate-400">No active departmental tasks recorded.</p>
            ) : (
              Object.entries(department_workload).map(([dept, count]) => {
                const max = Math.max(...Object.values(department_workload), 1);
                const pct = Math.round((count / max) * 100);
                return (
                  <div key={dept} className="space-y-1">
                    <div className="flex justify-between text-xs font-medium text-slate-700">
                      <span>{dept}</span>
                      <span className="text-slate-500">{count} tasks</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* High-Priority Risk Alerts */}
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2 text-rose-600" />
              Active Operational Risks & Shortages
            </h3>
            <span className="text-[11px] text-slate-400">Evidence Backed</span>
          </div>
          <div className="space-y-2.5">
            {recent_alerts.length === 0 ? (
              <p className="text-xs text-slate-400 py-3">No active risk alerts recorded.</p>
            ) : (
              recent_alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="p-3.5 rounded-lg border border-rose-100 bg-rose-50/40 flex items-start justify-between space-x-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-rose-100 px-2 py-0.5 rounded">
                        {alert.alert_type}
                      </span>
                      <span className="text-xs font-semibold text-slate-800">
                        {alert.description}
                      </span>
                    </div>
                    {alert.suggested_action && (
                      <p className="text-[11px] text-slate-600">
                        <strong className="text-slate-700">Suggested Action:</strong>{' '}
                        {alert.suggested_action}
                      </p>
                    )}
                  </div>
                  <span className="text-[10px] font-medium text-slate-400 whitespace-nowrap">
                    {alert.created_at.slice(0, 10)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Recent Business Cases */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center">
            <Briefcase className="w-4 h-4 mr-2 text-blue-600" />
            Connected Business Cases
          </h3>
          <button
            onClick={() => onNavigate('cases')}
            className="text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            View All Cases →
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-400 uppercase font-semibold text-[10px]">
                <th className="py-2.5 px-3">Case Number</th>
                <th className="py-2.5 px-3">Title</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Priority</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Opened</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recent_cases.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50 transition">
                  <td className="py-2.5 px-3 font-mono font-semibold text-blue-600">
                    {c.case_number}
                  </td>
                  <td className="py-2.5 px-3 font-medium text-slate-800">{c.title}</td>
                  <td className="py-2.5 px-3 text-slate-500">{c.case_type}</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        c.priority === 'CRITICAL' || c.priority === 'HIGH'
                          ? 'bg-rose-50 text-rose-700'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {c.priority}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700">
                      {c.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">{c.opened_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

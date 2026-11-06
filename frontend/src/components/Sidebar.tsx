import React from 'react';
import {
  LayoutDashboard,
  Mail,
  Briefcase,
  CheckSquare,
  Network,
  Package,
  FileEdit,
  Activity,
  Layers,
} from 'lucide-react';

export type NavTab =
  | 'overview'
  | 'inbox'
  | 'cases'
  | 'tasks'
  | 'dependencies'
  | 'orders'
  | 'drafts'
  | 'diagnostics';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  pendingEmailsCount: number;
  pendingProposalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  pendingEmailsCount,
  pendingProposalsCount,
}) => {
  const navItems = [
    { id: 'overview', label: 'Executive Overview', icon: LayoutDashboard },
    { id: 'inbox', label: 'Email Intelligence', icon: Mail, badge: pendingEmailsCount },
    { id: 'cases', label: 'Business Cases', icon: Briefcase },
    { id: 'tasks', label: 'Tasks & Proposals', icon: CheckSquare, badge: pendingProposalsCount },
    { id: 'dependencies', label: 'Dependency Graph', icon: Network },
    { id: 'orders', label: 'SO & MRP Reference', icon: Package },
    { id: 'drafts', label: 'Smart Drafts', icon: FileEdit },
    { id: 'diagnostics', label: 'AI & Diagnostics', icon: Activity },
  ];

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50/50 flex flex-col justify-between py-5 px-3 min-h-[calc(100vh-4rem)]">
      <div className="space-y-1">
        <div className="px-3 pb-3 text-[11px] font-bold text-slate-400 tracking-wider uppercase">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id as NavTab)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                    isActive ? 'bg-blue-800 text-white' : 'bg-slate-200 text-slate-700'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Integration Info Box */}
      <div className="p-3 bg-white border border-slate-200 rounded-xl space-y-1.5 shadow-xs">
        <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-800">
          <Layers className="w-3.5 h-3.5 text-blue-600" />
          <span>Task Orch Active</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-relaxed">
          Integrated with existing Supabase tables (<code className="text-slate-700">tasks</code>,{' '}
          <code className="text-slate-700">employees</code>).
        </p>
      </div>
    </aside>
  );
};

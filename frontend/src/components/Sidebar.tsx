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
  Users,
  Building2,
  ShieldAlert,
  UserCheck,
} from 'lucide-react';
import { BIRole } from '../types';

export type NavTab =
  | 'overview'
  | 'inbox'
  | 'cases'
  | 'tasks'
  | 'dependencies'
  | 'orders'
  | 'drafts'
  | 'outlook'
  | 'employees'
  | 'departments'
  | 'admin-users'
  | 'profile'
  | 'diagnostics';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  pendingEmailsCount: number;
  pendingProposalsCount: number;
  pendingApprovalsCount?: number;
  currentRole: BIRole;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  pendingEmailsCount,
  pendingProposalsCount,
  pendingApprovalsCount = 0,
  currentRole,
}) => {
  // Role-tailored labels and views
  const isEmployee = currentRole === 'EMPLOYEE';
  const isHOD = currentRole === 'DEPT_HEAD';

  const allNavItems = [
    {
      id: 'overview',
      label: isHOD ? 'Dept. Overview' : 'Executive Overview',
      icon: LayoutDashboard,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'inbox',
      label: 'Email Intelligence',
      icon: Mail,
      badge: pendingEmailsCount,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'cases',
      label: 'Business Cases',
      icon: Briefcase,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'tasks',
      label: isEmployee ? 'My Tasks' : isHOD ? 'Dept. Tasks' : 'Tasks & Proposals',
      icon: CheckSquare,
      badge: isEmployee ? undefined : pendingProposalsCount,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'EMPLOYEE', 'SYSADMIN'],
    },
    {
      id: 'dependencies',
      label: isEmployee ? 'My Workflows' : 'Workflow Graph',
      icon: Network,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'EMPLOYEE', 'SYSADMIN'],
    },
    {
      id: 'departments',
      label: 'Departments & HODs',
      icon: Building2,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'employees',
      label: isHOD ? 'Dept. Employees' : 'Employee Directory',
      icon: Users,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'orders',
      label: 'SO & MRP Reference',
      icon: Package,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'SYSADMIN'],
    },
    {
      id: 'drafts',
      label: 'Smart Drafts',
      icon: FileEdit,
      roles: ['MANAGEMENT', 'DEPT_HEAD', 'TEAM_LEADER', 'EMPLOYEE', 'SYSADMIN'],
    },
    {
      id: 'outlook',
      label: 'Email Workspace',
      icon: Mail,
      roles: ['EMPLOYEE', 'DEPT_HEAD', 'TEAM_LEADER', 'MANAGEMENT', 'SYSADMIN'],
    },
    {
      id: 'admin-users',
      label: 'User & Role Admin',
      icon: ShieldAlert,
      badge: pendingApprovalsCount,
      roles: ['SYSADMIN'],
    },
    {
      id: 'diagnostics',
      label: 'AI & Diagnostics',
      icon: Activity,
      roles: ['SYSADMIN', 'MANAGEMENT'],
    },
    {
      id: 'profile',
      label: 'My Profile',
      icon: UserCheck,
      roles: ['EMPLOYEE', 'DEPT_HEAD', 'TEAM_LEADER', 'MANAGEMENT', 'SYSADMIN'],
    },
  ];

  const navItems = allNavItems.filter((item) => item.roles.includes(currentRole));

  return (
    <aside className="w-64 border-r border-slate-200 bg-slate-50/50 flex flex-col justify-between py-5 px-3 min-h-[calc(100vh-4rem)]">
      <div className="space-y-1">
        <div className="px-3 pb-3 text-[11px] font-bold text-slate-400 tracking-wider uppercase flex items-center justify-between">
          <span>{isEmployee ? 'My Workspace' : isHOD ? 'Department Hub' : 'Navigation'}</span>
          <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.2 rounded border border-blue-200">
            {currentRole}
          </span>
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
                  ? 'bg-blue-600 text-white shadow-xs font-semibold'
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
          <span>RBAC Enforced</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-tight">
          Data isolation active for <strong>{currentRole}</strong> position.
        </p>
      </div>
    </aside>
  );
};
